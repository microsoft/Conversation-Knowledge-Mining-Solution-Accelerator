import time
from typing import BinaryIO, Optional

import httpx
from azure.identity import DefaultAzureCredential

from src.api.config import get_settings
from src.api.modules.document_intelligence.models import ExtractedDocument

API_VERSION = "2025-11-01"
SUPPORTED_EXTENSIONS = {"pdf", "docx", "xlsx", "csv", "txt", "png", "jpg", "jpeg", "tiff", "bmp", "mp3", "wav", "mp4"}

_credential = DefaultAzureCredential()


class ContentUnderstandingService:
    """Extract content from files using Azure Content Understanding."""

    def _get_token(self) -> str:
        token = _credential.get_token("https://cognitiveservices.azure.com/.default")
        return token.token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def analyze(
        self, file: BinaryIO, filename: str, analyzer: str = "prebuilt-document"
    ) -> ExtractedDocument:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: .{ext}")

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

        # For binary files: upload to Blob → get SAS URL → CU analyze
        blob_url = self._upload_temp_blob(filename, content)

        settings = get_settings()
        endpoint = settings.azure_content_understanding_endpoint.rstrip("/")
        url = f"{endpoint}/contentunderstanding/analyzers/{analyzer}:analyze?api-version={API_VERSION}"

        body = {"inputs": [{"url": blob_url}]}

        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers=self._headers(), json=body)
            resp.raise_for_status()
            operation_url = resp.headers.get("Operation-Location")
            if not operation_url:
                raise RuntimeError("No Operation-Location in response")

            result = self._poll_result(client, operation_url)

        return self._parse_result(result, filename, analyzer)

    def _upload_temp_blob(self, filename: str, content: bytes) -> str:
        """Upload file to Azure Blob Storage and return a SAS URL for CU to access."""
        from datetime import datetime, timedelta, timezone
        from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions

        settings = get_settings()
        account = settings.azure_storage_account
        container_name = "cu-temp"
        blob_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{filename}"

        blob_url = f"https://{account}.blob.core.windows.net"
        blob_service = BlobServiceClient(account_url=blob_url, credential=_credential)

        # Ensure container exists
        container = blob_service.get_container_client(container_name)
        try:
            container.create_container()
        except Exception:
            pass  # Already exists

        # Upload
        blob = container.get_blob_client(blob_name)
        ext = filename.rsplit(".", 1)[-1].lower()
        blob.upload_blob(
            content, overwrite=True,
            content_settings=ContentSettings(content_type=self._mime_type(ext)),
        )

        # Generate SAS URL (valid for 10 minutes)
        from azure.storage.blob import UserDelegationKey
        delegation_key = blob_service.get_user_delegation_key(
            key_start_time=datetime.now(timezone.utc),
            key_expiry_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        sas = generate_blob_sas(
            account_name=account,
            container_name=container_name,
            blob_name=blob_name,
            user_delegation_key=delegation_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(minutes=10),
        )

        return f"https://{account}.blob.core.windows.net/{container_name}/{blob_name}?{sas}"

    def analyze_url(
        self, file_url: str, filename: str, analyzer: str = "prebuilt-document"
    ) -> ExtractedDocument:
        settings = get_settings()
        endpoint = settings.azure_content_understanding_endpoint.rstrip("/")
        url = f"{endpoint}/contentunderstanding/analyzers/{analyzer}:analyze?api-version={API_VERSION}"

        body = {"inputs": [{"url": file_url}]}

        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=self._headers(), json=body)
            resp.raise_for_status()
            operation_url = resp.headers.get("Operation-Location")
            if not operation_url:
                raise RuntimeError("No Operation-Location in response")

            result = self._poll_result(client, operation_url)

        return self._parse_result(result, filename, analyzer)

    def _poll_result(self, client: httpx.Client, operation_url: str, max_wait: int = 120) -> dict:
        headers = self._headers()
        elapsed = 0
        interval = 2
        while elapsed < max_wait:
            resp = client.get(operation_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")
            if status == "Succeeded":
                return data
            if status == "Failed":
                raise RuntimeError(f"Analysis failed: {data}")
            time.sleep(interval)
            elapsed += interval
        raise TimeoutError("Content Understanding analysis timed out")

    def _parse_result(self, data: dict, filename: str, analyzer: str) -> ExtractedDocument:
        result = data.get("result", {})
        contents = result.get("contents", [{}])
        first = contents[0] if contents else {}
        return ExtractedDocument(
            filename=filename,
            content_type=first.get("mimeType", "application/octet-stream"),
            markdown=first.get("markdown", ""),
            fields=first.get("fields"),
            page_count=first.get("endPageNumber", 1),
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
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        settings = get_settings()
        if not doc.markdown.strip():
            return doc

        # Generate content hash for cache lookup
        text = doc.markdown[:3000]
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
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
            client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-10-21",
            )

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
                "doc_extractions": [{id, summary, keywords, entities, topics}],
                "domain": str,
                "dimensions": [{id, label, type, values: [{value, label, count}]}],
                "document_filters": [{id, values: {dim_id: [values]}}]
            }
        """
        import json
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        settings = get_settings()
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        )

        # Build snippets — shorter for large batches
        max_snippet = 200 if len(documents) > 20 else 500
        snippets = []
        for doc in documents:
            text = doc.get("text", "")
            if isinstance(text, list):
                text = "\n".join(f"{s.get('speaker','')}: {s.get('text','')}" for s in text)
            snippet = text[:max_snippet] + ("..." if len(text) > max_snippet else "")
            snippets.append({"id": doc["id"], "type": doc.get("type", ""), "text": snippet})

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

2. For the dataset, generate a FILTER SCHEMA:
   - Identify 4-8 filter dimensions (infer from content, NOT hardcoded)
   - Normalize values across documents
   - Map each document to its filter values

Output JSON:
{{
  "domain": "detected domain name",
  "doc_extractions": [
    {{"id": "doc_id", "summary": "...", "keywords": ["..."]}}
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
