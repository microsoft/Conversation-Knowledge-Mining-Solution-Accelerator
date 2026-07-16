from typing import Optional, Any
import asyncio
import logging
import os
import re
from urllib.parse import unquote

from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient
from agent_framework import AgentSession
from agent_framework_foundry import FoundryAgent
from agent_framework_openai._chat_client import RawOpenAIChatClient
from cachetools import TTLCache

from src.api.config import get_settings
from src.api.modules.rag.models import QAResponse, Source
from src.api.modules.rag.agent_tools import get_sql_response, get_schema_and_sample_values

logger = logging.getLogger(__name__)

# Maps a stable conversation_id (from UI) -> Foundry conversation/thread id, so
# multi-turn chats reuse server-side history. Mirrors chat_service.py's thread cache.
_thread_cache: TTLCache = TTLCache(maxsize=1000, ttl=3600.0)


def _extract_get_urls(response: Any) -> list:
    """Extract per-document get_urls from the raw Azure AI Search stream events.

    Mirrors scripts/test_agent.py: the GA annotations payload only carries the
    root search URL for doc_N citations, so the per-document URLs must be pulled
    from the raw stream events.
    """
    get_urls: list = []
    for raw_agent_update in getattr(response, "raw_representation", None) or []:
        raw_chat_update = getattr(raw_agent_update, "raw_representation", raw_agent_update)
        event = getattr(raw_chat_update, "raw_representation", raw_chat_update)
        try:
            for url in RawOpenAIChatClient._extract_azure_ai_search_get_urls(event):
                if url not in get_urls:
                    get_urls.append(url)
        except Exception:
            continue
    return get_urls


def _collect_citations(response: Any, get_urls: list) -> list:
    """Build a citation list from the final response, enriching doc_N citations
    with the per-document get_urls extracted from the raw Azure AI Search stream.

    Mirrors scripts/test_agent.py::collect_citations.
    """
    citations: list = []
    seen: set = set()
    url_iter = iter(get_urls)
    for message in getattr(response, "messages", None) or []:
        for content in getattr(message, "contents", None) or []:
            for ann in getattr(content, "annotations", None) or []:
                if not isinstance(ann, dict) or ann.get("type") != "citation":
                    continue
                title = ann.get("title", "N/A")
                add_props = ann.get("additional_properties") or {}
                url = add_props.get("get_url") or ann.get("url")
                # GA regression: doc_N citations only carry the root search URL,
                # so fall back to the next per-document get_url from the raw stream.
                if isinstance(title, str) and title.startswith("doc_"):
                    url = add_props.get("get_url") or next(url_iter, url)
                    # Derive the real document id from the get_url so the citation
                    # label shows the actual doc id instead of the ordinal doc_N.
                    # get_url format: .../indexes/{index}/docs/{document_id}?api-version=...
                    if isinstance(url, str):
                        m = re.search(r"/docs/([^?]+)", url)
                        if m:
                            title = unquote(m.group(1))
                key = (title, url)
                if key in seen:
                    continue
                seen.add(key)
                citations.append({"title": title, "url": url or "N/A"})
    return citations


def _strip_links_from_answer(text: str) -> str:
    """Strip stray inline citation artifacts the model may leak, without touching newlines.

    Numeric citation markers ([1], [2] ...) are intentionally preserved so the UI can
    render them as clickable superscripts mapped to the sources list.
    """
    out = text
    # 1. Remove (sources: ...) / (source: ...) prose dumps
    out = re.sub(r'[ \t]*\(\s*sources?:\s*[^)]+\)', '', out, flags=re.IGNORECASE)
    # 2. Remove standalone [8-hex] doc IDs like [842c7caf]
    out = re.sub(r'[ \t]*\[[a-f0-9]{8}\][ \t]*', ' ', out, flags=re.IGNORECASE)
    # 3. Collapse any double spaces introduced by the above
    out = re.sub(r'  +', ' ', out)
    return out.strip()


def _is_unhelpful_answer(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return True
    patterns = [
        "i cannot answer this question",
        "cannot answer this question from the data available",
        "please rephrase",
        "add more details",
        "i don't have enough information",
        "i do not have enough information",
        "unable to answer",
    ]
    return any(p in t for p in patterns)


class RAGService:
    """Retrieval-Augmented Generation service for question answering."""

    def __init__(self):
        pass

    def _run_agent(self, user_input: str, conversation_id: Optional[str] = None) -> tuple[str, list[Source]]:
        """Invoke the single pre-created Foundry agent and return (text, citations).

        Reuses a cached Foundry conversation/thread per conversation_id so multi-turn
        history is kept server-side, matching the reference chat_service.py.
        """
        settings = get_settings()

        async def _run() -> tuple[str, list[Source]]:
            agent_endpoint = (os.getenv("AZURE_AI_AGENT_ENDPOINT") or settings.azure_ai_agent_endpoint).strip()
            agent_name = (os.getenv("AGENT_NAME_CHAT") or settings.agent_name_chat).strip()
            if not agent_name:
                raise ValueError("AGENT_NAME_CHAT is not configured. Set AGENT_NAME_CHAT in .env or environment.")
            if not agent_endpoint:
                raise ValueError("AZURE_AI_AGENT_ENDPOINT is not configured. Set AZURE_AI_AGENT_ENDPOINT in .env or environment.")

            marker_map: dict[str, int] = {}

            def _replace_marker(match):
                marker = match.group(0)
                if marker not in marker_map:
                    marker_map[marker] = len(marker_map) + 1
                return f"[{marker_map[marker]}]"

            async with (
                AsyncDefaultAzureCredential() as credential,
                AIProjectClient(
                    endpoint=agent_endpoint,
                    credential=credential,
                ) as project_client,
            ):
                # Attach the SQL tool only when the agent was created with it
                # (USE_SQL is scenario-dependent and set at agent-creation time).
                use_sql = (os.getenv("USE_SQL") or str(settings.use_sql)).strip().lower() in ("1", "true", "yes", "on")
                agent = FoundryAgent(
                    project_client=project_client,
                    agent_name=agent_name,
                    tools=[get_schema_and_sample_values, get_sql_response] if use_sql else [],
                )

                # Reuse or create a server-side conversation thread for continuity
                thread_id = _thread_cache.get(conversation_id) if conversation_id else None
                if not thread_id:
                    openai_client = project_client.get_openai_client()
                    try:
                        conversation = await openai_client.conversations.create()
                        thread_id = conversation.id
                        if conversation_id:
                            _thread_cache[conversation_id] = thread_id
                    finally:
                        try:
                            await openai_client.close()
                        except Exception:
                            pass

                session = AgentSession(service_session_id=thread_id)
                out = ""
                stream = agent.run(user_input, stream=True, session=session)
                async for chunk in stream:
                    out += str(chunk.text) if chunk.text else ""

                # Convert the agent's raw AI Search citation markers (e.g. 【4:0†source】)
                # into sequential [N] markers on the FULL text — doing it per-chunk lets
                # markers split across stream boundaries leak through as raw text.
                out = re.sub(r"【\d+(?::\d+)?†?[^】]*】", _replace_marker, out)
                # Drop any residual raw markers that didn't match the expected form so no
                # search citation artifacts remain in the answer (only [N] markers stay).
                out = re.sub(r"【[^】]*】", "", out)

                # Citations come from the final response, matching test_agent.py:
                # collect annotations + recover per-document get_urls from the raw stream.
                response = await stream.get_final_response()
                get_urls = _extract_get_urls(response)
                citation_dicts = _collect_citations(response, get_urls)

            sources: list[Source] = []
            for c in citation_dicts:
                title = c["title"]
                url = c["url"]
                sources.append(Source(
                    doc_id=title,
                    score=0.0,
                    text="",
                    source_file=title,
                    url=url,
                ))
            return out, sources

        return asyncio.run(_run())

    def generate_title(self, messages: list[dict]) -> Optional[str]:
        """Generate a short conversation title using the configured title agent."""
        settings = get_settings()

        # Filter user messages and combine their content.
        user_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
            if msg.get("role") == "user"
        ]
        combined_content = "\n".join([msg["content"] for msg in user_messages])
        final_prompt = f"Generate a title for:\n{combined_content}"

        async def _run() -> str:
            agent_endpoint = (os.getenv("AZURE_AI_AGENT_ENDPOINT") or settings.azure_ai_agent_endpoint).strip()
            title_agent_name = (os.getenv("AGENT_NAME_TITLE") or "SummaryAgent").strip()
            async with (
                AsyncDefaultAzureCredential() as credential,
                AIProjectClient(
                    endpoint=agent_endpoint,
                    credential=credential,
                ) as project_client,
            ):
                agent = FoundryAgent(project_client=project_client, agent_name=title_agent_name)
                result = await agent.run(final_prompt)
                title = str(result.text).strip() if result is not None else "New Conversation"
                return title

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.exception("Error generating title: %s", str(e))
            # Fallback to last user message or default.
            if user_messages:
                return user_messages[-1]["content"][:50]
            return "New Conversation"

    @staticmethod
    def _merge_sources(primary: list[Source], fallback: list[Source]) -> list[Source]:
        """Merge sources while preserving order and removing duplicates."""
        merged: list[Source] = []
        seen: set[tuple[str, str]] = set()
        for src in [*primary, *fallback]:
            key = (src.doc_id, src.source_file or "")
            if key in seen:
                continue
            seen.add(key)
            merged.append(src)
        return merged

    @staticmethod
    def _build_fallback_answer(question: str, docs: list[dict]) -> str:
        """Return a non-empty deterministic answer when agent output is unavailable."""
        if not docs:
            return (
                "I could not generate an answer right now. "
                "No relevant content was found in the current data scope."
            )

        lines = [
            "I could not generate a full agent response right now, but here are the top relevant findings:",
        ]
        for i, doc in enumerate(docs[:3], 1):
            source_name = doc.get("source_file") or doc.get("doc_id") or f"Source {i}"
            snippet = (doc.get("summary") or doc.get("text") or "").strip()
            snippet = re.sub(r"\s+", " ", snippet)
            if len(snippet) > 220:
                snippet = snippet[:220].rstrip() + "..."
            if not snippet:
                snippet = "Relevant content found, but no preview text is available."
            lines.append(f"{i}. {source_name}: {snippet}")

        lines.append("You can retry the same question or narrow filters for a more specific answer.")
        return "\n".join(lines)

    @staticmethod
    def _build_grounded_answer(question: str, docs: list[dict]) -> str:
        """Build an AI-synthesised, actionable answer from retrieved docs.

        Uses the LLM to produce a structured, insightful response with numbered
        citations when possible. Falls back to a structured snippet list if the
        LLM call fails.
        """
        if not docs:
            return (
                "I could not find enough relevant evidence in the current scope to answer that confidently. "
                "Try narrowing filters or selecting specific sources."
            )

        top_docs = docs[:5]

        # Build a compact context block with numbered sources for citation anchoring.
        context_parts: list[str] = []
        for i, doc in enumerate(top_docs, 1):
            source_name = str(doc.get("source_file") or doc.get("doc_id") or f"Source {i}")
            blob = str(doc.get("summary") or doc.get("text") or "").strip()
            blob = re.sub(r"\s+", " ", blob)[:600]
            if blob:
                context_parts.append(f"[{i}] {source_name}\n{blob}")

        if not context_parts:
            return (
                "I could not extract readable content from the matching records. "
                "Try selecting a specific source or broadening your filters."
            )

        context_block = "\n\n".join(context_parts)
        system_prompt = (
            "You are an intelligent data analyst assistant. "
            "Answer the user's question concisely and analytically based only on the provided records. "
            "Structure your response with: a direct answer, key observations, and actionable implications. "
            "Do NOT include inline citation markers like [1], [2], or [1-5] anywhere in your response. "
            "Do not hallucinate or reference sources not provided. "
            "Keep the total response under 300 words."
        )
        user_prompt = (
            f"Question: {question}\n\n"
            f"Records:\n{context_block}\n\n"
            "Provide a structured, insightful answer without any citation markers."
        )

        try:
            from src.api.capabilities._llm import get_llm_client
            from src.api.config import get_settings
            settings = get_settings()
            client = get_llm_client()
            resp = client.chat.completions.create(
                model=settings.azure_openai_chat_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_completion_tokens=600,
            )
            answer = (resp.choices[0].message.content or "").strip()
            if answer:
                return _strip_links_from_answer(answer)
        except Exception as e:
            logger.warning(f"LLM synthesis in grounded answer failed: {e}")

        # Structured fallback without LLM
        lines = ["**Based on the available records:**\n"]
        for i, doc in enumerate(top_docs[:4], 1):
            source_name = str(doc.get("source_file") or doc.get("doc_id") or f"Source {i}")
            blob = str(doc.get("summary") or doc.get("text") or "").strip()
            blob = re.sub(r"\s+", " ", blob)[:220]
            if blob:
                lines.append(f"**[{i}] {source_name}**\n{blob}")
        lines.append("\n*Try asking a follow-up question to drill into a specific finding.*")
        return "\n\n".join(lines)

    @staticmethod
    def _is_noise_doc(doc: dict) -> bool:
        """Detect ingestion/error blobs that should not be used for QA grounding."""
        text = str(doc.get("text") or "")
        summary = str(doc.get("summary") or "")
        source_file = str(doc.get("source_file") or "").lower()
        doc_type = str(doc.get("type") or "").lower()
        blob = f"{summary} {text}".lower()

        # Noise signatures from failed audio extraction and upload-status artifacts.
        hard_markers = [
            "automatic transcription is not available",
            "cu analyze_url failed",
            "errorprocessingfile",
            "file is corrupted or format is unsupported",
        ]
        if any(marker in blob for marker in hard_markers):
            return True

        # Audio-transcription fallback docs are operational status artifacts, not business knowledge.
        if "audio/transcription-fallback" in doc_type:
            return True

        # WAV upload status snippets with no semantic content are low-signal for QA.
        # Keep this broad to catch truncated or partially indexed variants.
        if source_file.endswith(".wav") and (
            "uploaded successfully" in blob
            or "audio uploaded:" in blob
            or "automatic transcription" in blob
        ):
            return True

        return False

    def _filter_noise_sources(self, sources: list[Source], phase: str) -> list[Source]:
        """Filter noisy source entries before returning them to the UI."""
        if not sources:
            return sources
        filtered: list[Source] = []
        removed = 0
        for src in sources:
            doc = {
                "text": src.text,
                "summary": "",
                "source_file": src.source_file,
                "type": "",
            }
            if self._is_noise_doc(doc):
                removed += 1
                continue
            filtered.append(src)
        if removed > 0:
            logger.info(f"Filtered {removed} noisy sources during {phase}")
        return filtered

    def _filter_noise_docs(self, docs: list[dict], phase: str) -> list[dict]:
        """Remove noisy retrieval results while preserving order of useful documents."""
        if not docs:
            return docs
        filtered = [d for d in docs if not self._is_noise_doc(d)]
        removed = len(docs) - len(filtered)
        if removed > 0:
            logger.info(f"Filtered {removed} noisy docs during {phase}")
        return filtered

    def _get_blob_text_for_file(self, file_id: str) -> str:
        """Read extracted text from blob storage for 'extracted'-status files."""
        try:
            from src.api.modules.ingestion.azure_storage import azure_storage_service
            from src.api.config import get_settings
            settings = get_settings()
            blob_client = azure_storage_service._get_blob_client()
            container = blob_client.get_container_client(settings.azure_storage_container)
            blob = container.get_blob_client(f"extracted/{file_id}/content.txt")
            return blob.download_blob().readall().decode("utf-8")
        except Exception as e:
            logger.warning(f"Could not read blob text for {file_id}: {e}")
            return ""

    def _build_extracted_context(self, document_ids: list[str], query: str) -> list[dict]:
        """For files in 'extracted' state, read full text from blob and return as context docs."""
        from src.api.modules.ingestion.service import ingestion_service
        ingestion_service._ensure_loaded()

        results = []
        for file_id in document_ids:
            f = ingestion_service._uploaded_files.get(file_id)
            if f and f.status == "extracted":
                text = self._get_blob_text_for_file(file_id)
                if text:
                    # Simple keyword relevance score
                    q_words = query.lower().split()
                    score = sum(1 for w in q_words if w in text.lower()) / max(len(q_words), 1)
                    results.append({
                        "doc_id": file_id,
                        "text": text[:8000],  # cap at 8K chars for context window
                        "summary": "",
                        "type": f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else "doc",
                        "source_file": f.filename,
                        "score": max(score, 0.1),
                    })
        return results

    def _filter_document_ids(self, filters: dict, ingestion_service) -> Optional[list[str]]:
        """Given active filters (dimension_id -> comma-separated values),
        return list of document IDs that match all filters.
        Supports special dimensions: _doc_type, _document, _keywords."""
        if not filters:
            return None

        matching_file_ids: Optional[set[str]] = None
        for dim_id, value_str in filters.items():
            if not value_str:
                continue
            filter_values = set(v.strip() for v in value_str.split(","))
            dim_matches = set()

            for f in ingestion_service.uploaded_files:
                if dim_id == "_document":
                    # Direct file ID match
                    if f.id in filter_values:
                        dim_matches.add(f.id)
                elif dim_id == "_doc_type":
                    # Match by file extension
                    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else "unknown"
                    if ext in filter_values:
                        dim_matches.add(f.id)
                elif dim_id == "_keywords":
                    if any(kw in filter_values for kw in f.keywords):
                        dim_matches.add(f.id)
                else:
                    file_vals = f.filter_values.get(dim_id, [])
                    if any(v in filter_values for v in file_vals):
                        dim_matches.add(f.id)

            if matching_file_ids is None:
                matching_file_ids = dim_matches
            else:
                matching_file_ids &= dim_matches  # AND logic

        if matching_file_ids is not None and len(matching_file_ids) == 0:
            return []

        # Convert file IDs to document IDs
        if matching_file_ids is not None:
            doc_ids = []
            for doc in ingestion_service.documents.values():
                source_file = doc.metadata.source_file or ""
                file_stem = source_file.rsplit(".", 1)[0].replace(" ", "_") if source_file else doc.id
                if file_stem in matching_file_ids or doc.id in matching_file_ids:
                    doc_ids.append(doc.id)
            return doc_ids if doc_ids else list(matching_file_ids)

        return None

    def _search_azure_ai_search(self, query: str, top_k: int = 5,
                                document_ids: Optional[list[str]] = None) -> list[dict]:
        """Hybrid search using Azure AI Search (keyword + vector)."""
        settings = get_settings()
        if not settings.azure_search_endpoint:
            return []

        try:
            from azure.search.documents import SearchClient
            from azure.search.documents.models import VectorizedQuery
            credential = DefaultAzureCredential()
            client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index_name,
                credential=credential,
            )

            # Build filter string for scoped search
            filter_str = None
            if document_ids:
                ids_csv = ",".join(document_ids[:50])
                # Try doc_id first (chunked index), fall back to id (legacy)
                filter_str = f"search.in(id, '{ids_csv}')"

            # Generate query embedding for vector search
            vector_queries = []
            try:
                from src.api.modules.embeddings.service import EmbeddingsService
                emb_service = EmbeddingsService()
                query_emb = emb_service.generate_embedding(query)
                vector_queries.append(VectorizedQuery(
                    vector=query_emb.embedding,
                    k=top_k,
                    fields="text_vector",
                ))
            except Exception as e:
                logger.debug(f"Vector search unavailable, using keyword only: {e}")

            # Use fields that exist in both legacy and chunked index schemas
            select_fields = ["id", "doc_id", "text", "summary", "type", "source_file"]

            results = client.search(
                search_text=query,
                vector_queries=vector_queries if vector_queries else None,
                top=top_k,
                filter=filter_str,
                select=select_fields,
            )

            docs = []
            seen = {}  # doc_id -> index in docs (dedup chunks from same document)
            for r in results:
                doc_id = r.get("doc_id") or r["id"]
                # Strip chunk suffix to get base doc ID
                if "_c" in doc_id:
                    doc_id = doc_id.split("_c")[0]
                score = r.get("@search.score", 0)
                if doc_id in seen:
                    # Keep the higher-scoring chunk's text, accumulate score context
                    existing = docs[seen[doc_id]]
                    if score > existing["score"]:
                        existing["text"] = r.get("text", "")
                        existing["summary"] = r.get("summary", "")
                        existing["score"] = score
                    continue
                seen[doc_id] = len(docs)
                docs.append({
                    "doc_id": doc_id,
                    "text": r.get("text", ""),
                    "summary": r.get("summary", ""),
                    "type": r.get("type", "unknown"),
                    "source_file": r.get("source_file", ""),
                    "score": score,
                })
            return self._filter_noise_docs(docs, "azure-ai-search")
        except Exception as e:
            logger.error(f"Azure AI Search failed: {e}", exc_info=True)
            raise RuntimeError("Search service unavailable") from e

    def _search_sql(self, query: str, top_k: int = 5,
                    document_ids: Optional[list[str]] = None) -> list[dict]:
        """Search documents in Azure SQL database by text matching."""
        try:
            from src.api.storage.sql_service import sql_service
            sql_service._ensure_init()
            if not sql_service._initialized:
                logger.warning("SQL service not initialized, skipping SQL search")
                return []

            conn = sql_service._get_connection()
            cursor = conn.cursor()

            q = query.lower()
            words = q.split()

            # Build WHERE clause
            where_clauses = ["text_content IS NOT NULL AND LEN(text_content) > 0"]

            if document_ids:
                ids_csv = ",".join([f"'{did}'" for did in document_ids[:50]])
                where_clauses.append(f"id IN ({ids_csv})")

            where = " AND ".join(where_clauses)

            # Query all documents with text
            cursor.execute(
                f"SELECT id, text_content, summary, source_file, doc_type FROM documents WHERE {where}"
            )

            scored = []
            for row in cursor.fetchall():
                doc_id, text, summary, source_file, doc_type = row
                if not text or not text.strip():
                    continue

                # Simple relevance: count query word matches
                text_lower = text.lower()
                matches = sum(1 for w in words if w in text_lower)
                score = matches / max(len(words), 1) if matches > 0 else 0.05

                scored.append({
                    "doc_id": doc_id,
                    "text": text[:8000],  # Limit to 8K chars for context
                    "summary": summary or "",
                    "type": doc_type or "document",
                    "source_file": source_file or "unknown",
                    "score": score,
                })

            conn.close()

            # If no keyword matches, return all docs as context
            if not scored:
                conn = sql_service._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT TOP {top_k} id, text_content, summary, source_file, doc_type FROM documents WHERE {where}"
                )
                for row in cursor.fetchall():
                    doc_id, text, summary, source_file, doc_type = row
                    if text and text.strip():
                        scored.append({
                            "doc_id": doc_id,
                            "text": text[:8000],
                            "summary": summary or "",
                            "type": doc_type or "document",
                            "source_file": source_file or "unknown",
                            "score": 0.1,
                        })
                conn.close()

            scored = self._filter_noise_docs(scored, "sql-search")
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:top_k]
        except Exception as e:
            logger.warning(f"SQL search failed: {e}")
            return []

    def _search_in_memory(self, query: str, top_k: int = 5,
                          document_ids: Optional[list[str]] = None) -> list[dict]:
        """Fallback: search in-memory documents by text matching."""
        from src.api.modules.ingestion.service import ingestion_service
        ingestion_service._ensure_loaded()

        q = query.lower()
        scored = []
        for doc_id, doc in ingestion_service.documents.items():
            if document_ids and doc_id not in document_ids:
                continue
            text = ingestion_service.normalize_text(doc)
            # Simple relevance: count query word matches
            words = q.split()
            text_lower = text.lower()
            score = sum(1 for w in words if w in text_lower) / max(len(words), 1)
            if score > 0:
                scored.append({
                    "doc_id": doc_id,
                    "text": text,
                    "summary": "",
                    "type": doc.type,
                    "source_file": doc.metadata.source_file or "",
                    "score": score,
                })

        # If no keyword matches, return first N docs as context
        if not scored:
            for doc_id, doc in list(ingestion_service.documents.items())[:top_k]:
                if document_ids and doc_id not in document_ids:
                    continue
                text = ingestion_service.normalize_text(doc)
                scored.append({
                    "doc_id": doc_id,
                    "text": text,
                    "summary": "",
                    "type": doc.type,
                    "source_file": doc.metadata.source_file or "",
                    "score": 0.1,
                })

        scored = self._filter_noise_docs(scored, "in-memory-search")
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _search_external_data_sources(self, query: str, top_k: int = 5) -> list[dict]:
        """Search all live-query data sources and merge results."""
        try:
            from src.api.modules.data_sources.registry import data_source_registry
            live_sources = data_source_registry.list_live_sources()
            if not live_sources:
                return []

            all_docs = []
            for source in live_sources:
                docs = data_source_registry.search(source.id, query, top_k)
                for doc in docs:
                    doc["source_file"] = doc.get("title", source.name)
                    doc["data_source_name"] = source.name
                    doc["data_source_id"] = source.id
                    if "type" not in doc:
                        doc["type"] = "external"
                all_docs.extend(docs)

            # Sort by score descending, take top_k
            all_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
            return all_docs[:top_k]
        except Exception as e:
            logger.warning(f"External data source search failed: {e}")
            return []

    def _answer_from_external(
        self, question: str, top_k: int,
        external_index_id: str, include_sources: bool,
        conversation_id: Optional[str] = None,
    ) -> QAResponse:
        """Answer a question using an external Azure AI Search index."""
        from src.api.modules.ingestion.external_index import external_index_service
        settings = get_settings()

        search_docs = external_index_service.search(external_index_id, question, top_k)
        if not search_docs:
            return QAResponse(
                question=question,
                answer="No results found in the connected index. Try a different query.",
                sources=[], model=settings.azure_openai_chat_deployment,
            )

        sources = []
        for i, doc in enumerate(search_docs):
            text = doc["text"][:4000]
            sources.append(Source(
                doc_id=doc["doc_id"],
                score=round(doc.get("score", 0), 4),
                text=text[:500],
                source_file=doc.get("source_file", ""),
            ))

        try:
            answer, agent_sources = self._run_agent(question, conversation_id)
        except Exception as e:
            logger.warning(f"Agent call failed in external index path, using fallback answer: {e}")
            answer = self._build_fallback_answer(question, search_docs)
            agent_sources = []

        if not (answer or "").strip():
            logger.warning("Agent returned empty answer in external index path, using fallback answer")
            answer = self._build_fallback_answer(question, search_docs)

        sources = sources + agent_sources
        return QAResponse(
            question=question,
            answer=_strip_links_from_answer(answer),
            sources=sources if include_sources else [],
            model=settings.azure_openai_chat_deployment,
        )

    def fetch_citation_content(self, url: str) -> dict:
        """Fetch a cited document's content directly from Azure AI Search using the
        citation's get_url.

        Fetches the cited document's content from Azure AI Search using our
        index field names (``text``/``source_file`` instead of ``content``/``sourceurl``).
        The get_url points at ``.../indexes/{index}/docs/{key}?api-version=...`` and is
        fetched with an Entra bearer token scoped to Azure Cognitive Search.
        """
        import requests

        credential = DefaultAzureCredential()
        token = credential.get_token("https://search.azure.com/.default")
        try:
            response = requests.get(
                url,
                headers={
                    "Authorization": f"Bearer {token.token}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                content = data.get("text") or data.get("content") or ""
                title = data.get("source_file") or data.get("sourceurl") or ""
                return {"content": content, "title": title}
            logger.warning(f"Citation content fetch failed: url={url}, status={response.status_code}")
            return {"error": f"HTTP {response.status_code}"}
        except Exception:
            logger.exception("Exception while fetching citation content")
            return {"error": "Unable to fetch content"}

    def answer_question(
        self,
        question: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
        include_sources: bool = True,
        document_ids: Optional[list[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> QAResponse:
        settings = get_settings()

        # Agent-only flow: the Foundry agent performs its own retrieval through its
        # configured tools (Azure AI Search / SQL) and returns the answer together
        # with its citations. No backend retrieval, merge, or grounded fallback is
        # used — the response and sources come solely from the agent.
        answer, agent_sources = self._run_agent(question, conversation_id)

        sources = self._filter_noise_sources(agent_sources, "answer-question-response")
        return QAResponse(
            question=question,
            answer=_strip_links_from_answer(answer),
            sources=sources if include_sources else [],
            model=settings.azure_openai_chat_deployment,
        )

    def answer_conversation(
        self,
        messages: list[dict],
        top_k: int = 5,
        filters: Optional[dict] = None,
        document_ids: Optional[list[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> QAResponse:
        """Multi-turn conversation with RAG context."""
        settings = get_settings()

        last_user_message = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_message = msg["content"]
                break

        if not last_user_message:
            return QAResponse(
                question="", answer="No user message found.", sources=[], model=settings.azure_openai_chat_deployment
            )

        # Filter scoping
        if filters and not document_ids:
            from src.api.modules.ingestion.service import ingestion_service
            matching_ids = self._filter_document_ids(filters, ingestion_service)
            if matching_ids is not None:
                document_ids = matching_ids

        from src.api.modules.runtime.retrieval_engine import retrieval_engine
        search_docs = retrieval_engine.retrieve(
            query=last_user_message,
            top_k=top_k,
            filters=filters,
            document_ids=document_ids,
            source="all",
        )

        # Also inject blob text for 'extracted'-status files not yet in AI Search
        if document_ids:
            extracted_docs = self._build_extracted_context(document_ids, last_user_message)
            indexed_ids = {d["doc_id"] for d in search_docs}
            for doc in extracted_docs:
                if doc["doc_id"] not in indexed_ids:
                    search_docs.append(doc)
        else:
            from src.api.modules.ingestion.service import ingestion_service
            ingestion_service._ensure_loaded()
            extracted_ids = [
                f.id for f in ingestion_service._uploaded_files.values()
                if f.status == "extracted"
            ]
            if extracted_ids:
                search_docs.extend(self._build_extracted_context(extracted_ids, last_user_message))

        search_docs = self._filter_noise_docs(search_docs, "answer-conversation-post-merge")

        sources = []
        for i, doc in enumerate(search_docs):
            text = doc["text"][:4000]
            sources.append(Source(
                doc_id=doc["doc_id"], score=round(doc.get("score", 0), 4),
                text=text[:500],
                source_file=doc.get("source_file", ""),
            ))

        all_messages = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        try:
            answer, agent_sources = self._run_agent(all_messages, conversation_id)
        except Exception as e:
            logger.warning(f"Agent call failed in answer_conversation, using fallback answer: {e}")
            answer = self._build_fallback_answer(last_user_message, search_docs)
            agent_sources = []

        if not (answer or "").strip() or _is_unhelpful_answer(answer):
            logger.warning("Agent answer was empty/unhelpful in answer_conversation, using grounded fallback")
            answer = self._build_grounded_answer(last_user_message, search_docs)

        combined_sources = self._merge_sources(agent_sources, sources)
        combined_sources = self._filter_noise_sources(combined_sources, "answer-conversation-response")
        return QAResponse(
            question=last_user_message,
            answer=_strip_links_from_answer(answer),
            sources=combined_sources,
            model=settings.azure_openai_chat_deployment,
        )


rag_service = RAGService()



