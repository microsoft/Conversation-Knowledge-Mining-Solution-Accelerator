import time
import logging
from typing import BinaryIO, Optional

import httpx
from azure.identity import DefaultAzureCredential

from src.api.config import get_settings
from src.api.modules.document_intelligence.models import ExtractedDocument

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {"pdf", "docx", "xlsx", "csv", "txt", "png", "jpg", "jpeg", "tiff", "bmp", "mp3", "wav", "mp4"}

# Default CU analyzer template for generic document analysis
DEFAULT_ANALYZER_TEMPLATE = {
    "scenario": "document",
    "description": "Generic document content extraction",
    "config": {"returnDetails": True},
    "fieldSchema": {
        "name": "DocumentAnalysis",
        "descriptions": "Extract content and metadata from documents",
        "fields": {
            "content": {
                "type": "string",
                "method": "generate",
                "description": "Full text content of the document in markdown format"
            },
            "summary": {
                "type": "string",
                "method": "generate",
                "description": "Summarize the document in 2-3 sentences"
            },
            "topic": {
                "type": "string",
                "method": "generate",
                "description": "Identify the single primary topic in 6 words or less"
            },
            "keyPhrases": {
                "type": "string",
                "method": "generate",
                "description": "Identify the top 10 key phrases as comma separated string"
            },
        }
    }
}

# Audio/video analyzer for call transcripts
AUDIO_ANALYZER_ID = "km-audio"
AUDIO_ANALYZER_TEMPLATE = {
    "scenario": "audioTranscription",
    "description": "Transcribe and analyze audio call recordings",
    "config": {"returnDetails": True},
    "fieldSchema": {
        "name": "AudioAnalysis",
        "descriptions": "Transcribe and extract metadata from audio recordings",
        "fields": {
            "content": {
                "type": "string",
                "method": "generate",
                "description": "Full transcription of the audio in readable format"
            },
            "summary": {
                "type": "string",
                "method": "generate",
                "description": "Summarize the conversation in 2-3 sentences"
            },
            "topic": {
                "type": "string",
                "method": "generate",
                "description": "Identify the single primary topic in 6 words or less"
            },
            "keyPhrases": {
                "type": "string",
                "method": "generate",
                "description": "Identify the top 10 key phrases as comma separated string"
            },
        }
    }
}

AUDIO_EXTENSIONS = {"wav", "mp3", "mp4"}

_credential = DefaultAzureCredential()


class ContentUnderstandingService:
    """Extract content from files using Azure Content Understanding."""

    def __init__(self):
        self._analyzers_ensured: set[str] = set()

    @staticmethod
    def _is_unsupported_audio_scenario_error(exc: Exception) -> bool:
        if not isinstance(exc, httpx.HTTPStatusError):
            return False
        if exc.response is None or exc.response.status_code != 400:
            return False
        body = (exc.response.text or "").lower()
        return "unsupportedpropertyvalue" in body and "audiotranscription" in body

    @staticmethod
    def _raise_cu_request_error(resp: httpx.Response, operation: str, analyzer: str):
        detail = (resp.text or "").strip()
        if len(detail) > 1200:
            detail = detail[:1200] + "..."
        raise RuntimeError(
            f"CU {operation} failed ({resp.status_code}) for analyzer '{analyzer}': {detail}"
        )

    def _get_token(self) -> str:
        token = _credential.get_token("https://cognitiveservices.azure.com/.default")
        return token.token

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def _endpoint(self) -> str:
        settings = get_settings()
        return settings.azure_content_understanding_endpoint.rstrip("/")

    def _api_version(self) -> str:
        return get_settings().azure_content_understanding_api_version

    def _default_analyzer_id(self) -> str:
        return get_settings().azure_content_understanding_analyzer_id

    def resolve_max_wait(self, file_size_bytes: int, max_cap_sec: int | None = None) -> int:
        """Compute a size-aware CU polling timeout.

        Small files fail fast; larger files get additional time up to a configurable cap.
        """
        settings = get_settings()
        cap = max_cap_sec if max_cap_sec is not None else settings.cu_poll_max_wait_sec
        size_mb = max(1, int((file_size_bytes + (1024 * 1024 - 1)) / (1024 * 1024)))
        computed = settings.cu_poll_base_wait_sec + (size_mb * settings.cu_poll_per_mb_wait_sec)
        return max(settings.cu_poll_base_wait_sec, min(computed, cap))

    def _ensure_analyzer(self, analyzer_id: str | None = None):
        """Create the CU analyzer if it doesn't exist yet."""
        if analyzer_id is None:
            analyzer_id = self._default_analyzer_id()
        if analyzer_id in self._analyzers_ensured:
            return

        template = AUDIO_ANALYZER_TEMPLATE if analyzer_id == AUDIO_ANALYZER_ID else DEFAULT_ANALYZER_TEMPLATE
        endpoint = self._endpoint()
        url = f"{endpoint}/contentunderstanding/analyzers/{analyzer_id}?api-version={self._api_version()}"
        headers = {**self._auth_headers(), "Content-Type": "application/json"}

        with httpx.Client(timeout=30) as client:
            # Check if analyzer exists
            resp = client.get(url, headers=self._auth_headers())
            if resp.status_code == 200:
                self._analyzers_ensured.add(analyzer_id)
                return

            # Create the analyzer
            resp = client.put(url, headers=headers, json=template)
            if resp.status_code >= 400:
                logger.error(f"CU Analyzer create error {resp.status_code}: {resp.text}")
            resp.raise_for_status()

            # Poll until ready
            operation_url = resp.headers.get("Operation-Location")
            if operation_url:
                self._poll_result(client, operation_url)

        self._analyzers_ensured.add(analyzer_id)

    def analyze(
        self,
        file: BinaryIO,
        filename: str,
        analyzer: str | None = None,
        max_wait_sec: int | None = None,
    ) -> ExtractedDocument:
        if analyzer is None:
            analyzer = self._default_analyzer_id()
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: .{ext}")

        # Route audio/video files to the audio analyzer when supported by CU API/version.
        if ext in AUDIO_EXTENSIONS:
            analyzer = AUDIO_ANALYZER_ID

        content = file.read()

        # Plain text files: skip CU, use content directly
        if ext in ("txt", "csv"):
            text = content.decode("utf-8", errors="replace")
            return ExtractedDocument(
                filename=filename,
                content_type=self._mime_type(ext),
                markdown=text,
                page_count=1,
                analyzer="direct-text",
            )

        # Ensure the analyzer exists. If audio analyzer schema isn't supported,
        # fall back to the default analyzer for a clearer failure mode.
        try:
            self._ensure_analyzer(analyzer)
        except httpx.HTTPStatusError as e:
            if analyzer == AUDIO_ANALYZER_ID and self._is_unsupported_audio_scenario_error(e):
                fallback = self._default_analyzer_id()
                logger.warning(
                    "CU audio analyzer template unsupported for this API/version; "
                    f"falling back to analyzer '{fallback}' for {filename}"
                )
                analyzer = fallback
                self._ensure_analyzer(analyzer)
            else:
                raise

        endpoint = self._endpoint()
        url = f"{endpoint}/contentunderstanding/analyzers/{analyzer}:analyze?api-version={self._api_version()}"

        # Send raw bytes directly to CU
        headers = {
            **self._auth_headers(),
            "Content-Type": "application/octet-stream",
        }

        with httpx.Client(timeout=300) as client:
            resp = client.post(url, headers=headers, content=content)
            if resp.status_code >= 400:
                logger.error(f"CU Error {resp.status_code}: {resp.text}")
                self._raise_cu_request_error(resp, "analyze", analyzer)
            operation_url = resp.headers.get("Operation-Location")
            if not operation_url:
                raise RuntimeError("No Operation-Location in response")

            poll_max_wait = max_wait_sec if max_wait_sec is not None else get_settings().cu_poll_max_wait_sec
            result = self._poll_result(client, operation_url, max_wait=poll_max_wait)

        return self._parse_result(result, filename, analyzer)

    def analyze_url(
        self,
        file_url: str,
        filename: str,
        analyzer: str | None = None,
        max_wait_sec: int | None = None,
    ) -> ExtractedDocument:
        if analyzer is None:
            analyzer = self._default_analyzer_id()

        # Route audio/video files to the audio analyzer (parity with byte-upload path).
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in AUDIO_EXTENSIONS:
            analyzer = AUDIO_ANALYZER_ID

        try:
            self._ensure_analyzer(analyzer)
        except httpx.HTTPStatusError as e:
            if analyzer == AUDIO_ANALYZER_ID and self._is_unsupported_audio_scenario_error(e):
                fallback = self._default_analyzer_id()
                logger.warning(
                    "CU audio analyzer template unsupported for this API/version; "
                    f"falling back to analyzer '{fallback}' for {filename}"
                )
                analyzer = fallback
                self._ensure_analyzer(analyzer)
            else:
                raise

        endpoint = self._endpoint()
        url = f"{endpoint}/contentunderstanding/analyzers/{analyzer}:analyze?api-version={self._api_version()}"

        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        body = {"url": file_url}

        with httpx.Client(timeout=300) as client:
            resp = client.post(url, headers=headers, json=body)
            if resp.status_code >= 400:
                logger.error(f"CU Error {resp.status_code}: {resp.text}")
                self._raise_cu_request_error(resp, "analyze_url", analyzer)
            operation_url = resp.headers.get("Operation-Location")
            if not operation_url:
                raise RuntimeError("No Operation-Location in response")

            poll_max_wait = max_wait_sec if max_wait_sec is not None else get_settings().cu_poll_max_wait_sec
            result = self._poll_result(client, operation_url, max_wait=poll_max_wait)

        return self._parse_result(result, filename, analyzer)

    def _poll_result(self, client: httpx.Client, operation_url: str, max_wait: int = 600) -> dict:
        elapsed = 0
        interval = 1  # Start fast, grow exponentially
        transient_errors = 0
        while elapsed < max_wait:
            try:
                # Refresh auth header per poll in case token rotates during long runs.
                resp = client.get(operation_url, headers=self._auth_headers())
                resp.raise_for_status()
                transient_errors = 0
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.TimeoutException) as e:
                # CU polling can hit intermittent transport issues; retry until max_wait.
                transient_errors += 1
                logger.warning(
                    f"CU poll transient error (attempt {transient_errors}) for {operation_url}: {e}"
                )
                sleep_for = min(interval, 15)
                time.sleep(sleep_for)
                elapsed += sleep_for
                interval = min(interval * 2, 15)
                continue

            data = resp.json()
            status = data.get("status", "").lower()
            if status == "succeeded":
                return data
            if status == "failed":
                raise RuntimeError(f"Analysis failed: {data}")
            time.sleep(interval)
            elapsed += interval
            interval = min(interval * 2, 15)  # Cap at 15s
        raise TimeoutError("Content Understanding analysis timed out")

    def _parse_result(self, data: dict, filename: str, analyzer: str) -> ExtractedDocument:
        result = data.get("result", {})
        contents = result.get("contents", [{}])

        # Concatenate markdown from ALL content entries (multi-page PDFs return one per page)
        all_markdown_parts = []
        all_fields = {}
        page_count = 1

        for entry in contents:
            entry_fields = entry.get("fields", {})
            # Merge fields from first entry that has them
            if entry_fields and not all_fields:
                all_fields = entry_fields

            # Collect text: prefer generated 'content' field, fallback to built-in 'markdown'
            text = ""
            if entry_fields.get("content", {}).get("valueString"):
                text = entry_fields["content"]["valueString"]
            elif entry.get("markdown"):
                text = entry["markdown"]
            if text.strip():
                all_markdown_parts.append(text)

            page_count = max(page_count, entry.get("endPageNumber", 1))

        markdown = "\n\n".join(all_markdown_parts)
        first = contents[0] if contents else {}

        return ExtractedDocument(
            filename=filename,
            content_type=first.get("mimeType", "application/octet-stream"),
            markdown=markdown,
            fields=all_fields,
            page_count=page_count,
            analyzer=analyzer,
        )

    def _mime_type(self, ext: str) -> str:
        mime_map = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "txt": "text/plain",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "tiff": "image/tiff",
            "bmp": "image/bmp",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "mp4": "video/mp4",
        }
        return mime_map.get(ext, "application/octet-stream")

    def enrich(self, doc: ExtractedDocument) -> ExtractedDocument:
        """Enrich a CU-extracted document with AI-generated summary, entities, key phrases, topics.
        Results are cached in Cosmos DB by content hash to avoid repeated GPT-4o calls."""
        import hashlib
        import json
        from src.api.capabilities._llm import get_llm_client

        settings = get_settings()
        if not doc.markdown.strip():
            return doc

        # If CU already extracted summary/topics/keyPhrases, use them directly
        # This avoids a redundant LLM call for data CU already provided
        if doc.fields:
            cu_summary = doc.fields.get("summary", {}).get("valueString", "")
            cu_topic = doc.fields.get("topic", {}).get("valueString", "")
            cu_phrases = doc.fields.get("keyPhrases", {}).get("valueString", "")
            if cu_summary or cu_topic or cu_phrases:
                if cu_summary and not doc.summary:
                    doc.summary = cu_summary
                if cu_topic and not doc.topics:
                    doc.topics = [cu_topic]
                if cu_phrases and not doc.key_phrases:
                    doc.key_phrases = [kp.strip() for kp in cu_phrases.split(",") if kp.strip()]
                import logging
                logging.getLogger(__name__).info(f"Using CU-extracted fields for {doc.filename}, skipping LLM enrichment")
                return doc

        # Generate content hash for cache lookup
        text = doc.markdown[:5000]
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Check SQL cache first
        try:
            from src.api.storage.sql_service import sql_service
            cached = sql_service.get_enrichment(content_hash)
            if cached:
                doc.summary = cached.get("summary", "")
                doc.entities = cached.get("entities", [])
                doc.key_phrases = cached.get("key_phrases", [])
                doc.topics = cached.get("topics", [])
                doc.metadata_extracted = cached.get("metadata", {})
                import logging
                logging.getLogger(__name__).info(f"Enrichment cache hit for {doc.filename}")
                return doc
        except Exception:
            pass  # Cache miss or Cosmos not available — proceed with GPT-4o

        try:
            client = get_llm_client()

            response = client.chat.completions.create(
                model=settings.azure_openai_chat_deployment,
                messages=[
                    {"role": "system", "content": """You extract structured intelligence from document content.
Return JSON with:
- "summary": 2-3 sentence summary of the document
- "entities": Array of {name, type, context} — people, organizations, products, locations, concepts
- "key_phrases": Array of 5-10 key phrases that capture the main topics
- "topics": Array of 3-5 high-level topic categories
- "metadata": Object of key-value pairs extracted from the content (dates, amounts, IDs, etc.)
Be specific and domain-agnostic. Output strictly valid JSON."""},
                    {"role": "user", "content": f"Extract intelligence from this document:\n\nFilename: {doc.filename}\n\n{text}"},
                ],
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            doc.summary = result.get("summary", "")
            doc.entities = result.get("entities", [])
            doc.key_phrases = result.get("key_phrases", [])
            doc.topics = result.get("topics", [])
            doc.metadata_extracted = result.get("metadata", {})

            # Save to SQL cache
            try:
                from src.api.storage.sql_service import sql_service
                sql_service.save_enrichment(content_hash, doc.filename, result)
            except Exception:
                pass  # Non-blocking

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"AI enrichment failed for {doc.filename}: {e}")

        return doc

    def enrich_batch(self, documents: list[dict]) -> dict:
        """Enrich a batch of documents and generate a unified filter schema.
        
        Returns:
            {
                "doc_extractions": [{id, summary, keywords, entities, topics, metadata, relationships}],
                "domain": str,
                "dimensions": [{id, label, type, values: [{value, label, count}]}],
                "document_filters": [{id, values: {dim_id: [values]}}]
            }
        """
        import json
        from src.api.capabilities._llm import get_llm_client

        settings = get_settings()
        client = get_llm_client()

        # Build snippets — use more text for better enrichment quality
        max_snippet = 500 if len(documents) > 20 else 1500
        snippets = []
        for doc in documents:
            text = doc.get("text", "")
            if isinstance(text, list):
                text = "\n".join(f"{s.get('speaker','')}: {s.get('text','')}" for s in text)
            snippet = text[:max_snippet] + ("..." if len(text) > max_snippet else "")

            # Include CU-extracted fields when available for richer context
            entry = {"id": doc["id"], "type": doc.get("type", ""), "text": snippet}
            if doc.get("summary"):
                entry["summary"] = doc["summary"]
            if doc.get("key_phrases"):
                entry["key_phrases"] = doc["key_phrases"]
            if doc.get("topics"):
                entry["topics"] = doc["topics"]
            snippets.append(entry)

        # Process in chunks of 25 to avoid token limits
        CHUNK_SIZE = 25
        all_extractions = []
        all_doc_filters = []
        merged_dimensions: dict[str, dict] = {}
        domain = ""

        for i in range(0, len(snippets), CHUNK_SIZE):
            chunk = snippets[i:i + CHUNK_SIZE]
            is_first = i == 0

            prompt = f"""Analyze these {len(chunk)} documents. Do TWO things:

1. For each document, extract:
    - summary (1 sentence)
    - keywords (3-5 specific terms)
    - entities: 3-8 concrete entities as objects with {{name, type, context}}
    - topics: 2-5 high-level topic labels
    - relationships: 0-8 relationship objects with {{subject, relation, object, context, confidence}}
    - metadata: key-value pairs explicitly grounded in the content such as dates, locations, products, people, organizations, amounts, events, statuses, behaviors, or other domain-specific signals
    NOTE: Some documents already have "summary", "key_phrases", or "topics" from prior extraction. Use those as-is and refine only if needed.

2. For the dataset, generate a FILTER SCHEMA:
   - Identify 4-8 filter dimensions (infer from content, NOT hardcoded)
   - Normalize values across documents
   - Map each document to its filter values

Output JSON:
{{
  "domain": "detected domain name",
  "doc_extractions": [
        {{"id": "doc_id", "summary": "...", "keywords": ["..."], "entities": [{{"name": "...", "type": "...", "context": "..."}}], "topics": ["..."], "relationships": [{{"subject": "...", "relation": "...", "object": "...", "context": "...", "confidence": 0.8}}], "metadata": {{"field": "value"}}}}
  ],
  "dimensions": [
    {{
      "id": "machine_id",
      "label": "Display Name",
      "type": "multi_select",
      "values": [{{"value": "normalized_id", "label": "Display", "count": N}}]
    }}
  ],
  "document_filters": [
    {{"id": "doc_id", "values": {{"dimension_id": ["value1"]}}}}
  ]
}}

Documents:
{json.dumps(chunk)}"""

            try:
                response = client.chat.completions.create(
                    model=settings.azure_openai_chat_deployment,
                    messages=[
                        {"role": "system", "content": "You are a data preparation system. Extract document metadata and generate filter schemas. Be domain-agnostic. Keep responses compact."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=4000,
                    response_format={"type": "json_object"},
                )
                chunk_result = json.loads(response.choices[0].message.content)

                if is_first:
                    domain = chunk_result.get("domain", "")

                all_extractions.extend(chunk_result.get("doc_extractions", []))
                all_doc_filters.extend(chunk_result.get("document_filters", []))

                # Merge dimensions across chunks
                for dim in chunk_result.get("dimensions", []):
                    dim_id = dim["id"]
                    if dim_id not in merged_dimensions:
                        merged_dimensions[dim_id] = dim
                    else:
                        existing_vals = {v["value"] for v in merged_dimensions[dim_id].get("values", [])}
                        for v in dim.get("values", []):
                            if v["value"] not in existing_vals:
                                merged_dimensions[dim_id]["values"].append(v)
                            else:
                                for ev in merged_dimensions[dim_id]["values"]:
                                    if ev["value"] == v["value"]:
                                        ev["count"] = ev.get("count", 0) + v.get("count", 0)

            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Batch enrichment chunk {i//CHUNK_SIZE} failed: {e}")

        return {
            "domain": domain,
            "doc_extractions": all_extractions,
            "dimensions": list(merged_dimensions.values()),
            "document_filters": all_doc_filters,
        }


content_understanding_service = ContentUnderstandingService()
