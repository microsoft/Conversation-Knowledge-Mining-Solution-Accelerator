from typing import Optional
import asyncio
import logging
import os
import re

import yaml
from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient
from agent_framework import AgentSession
from agent_framework_foundry import FoundryAgent
from cachetools import TTLCache

from src.api.config import get_settings
from src.api.modules.rag.models import QAResponse, Source

logger = logging.getLogger(__name__)

# Maps a stable conversation_id (from UI) -> Foundry conversation/thread id, so
# multi-turn chats reuse server-side history. Mirrors chat_service.py's thread cache.
_thread_cache: TTLCache = TTLCache(maxsize=1000, ttl=3600.0)

# Load prompts from config file (editable without code changes)
_PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "prompts.yaml")
_PROMPTS: dict = {}
try:
    with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
        _PROMPTS = yaml.safe_load(f) or {}
except Exception:
    logger.warning("Could not load prompts.yaml — using built-in defaults")


def _get_prompt(key: str, fallback: str, **kwargs) -> str:
    """Load a prompt from config, falling back to the built-in default."""
    template = _PROMPTS.get(key, fallback)
    if not kwargs:
        return template

    # Use literal token replacement (e.g., {context}) so JSON examples in prompts
    # do not trigger str.format() KeyError on keys like {"type": ...}.
    rendered = template
    for token, value in kwargs.items():
        rendered = rendered.replace("{" + token + "}", str(value))
    return rendered


def _strip_links_from_answer(text: str) -> str:
    # Keep citation labels, remove markdown link destinations and raw URL/path targets.
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\1]", text)
    out = re.sub(r"\bhttps?://\S+", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\((?:sandbox/|/sandbox/|file://)[^)]+\)", "", out, flags=re.IGNORECASE)
    return out


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
            citations: list = []
            marker_map: dict[str, int] = {}

            def _replace_marker(match):
                marker = match.group(0)
                if marker not in marker_map:
                    marker_map[marker] = len(marker_map) + 1
                return f"[{marker_map[marker]}]"

            async with (
                AsyncDefaultAzureCredential() as credential,
                AIProjectClient(
                    endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT", settings.azure_ai_agent_endpoint),
                    credential=credential,
                ) as project_client,
            ):
                agent = FoundryAgent(project_client=project_client, agent_name=os.getenv("AGENT_NAME_CHAT", settings.agent_name_chat))

                # Reuse or create a server-side conversation thread for continuity
                thread_id = _thread_cache.get(conversation_id) if conversation_id else None
                if not thread_id:
                    openai_client = project_client.get_openai_client()
                    conversation = await openai_client.conversations.create()
                    thread_id = conversation.id
                    if conversation_id:
                        _thread_cache[conversation_id] = thread_id

                session = AgentSession(service_session_id=thread_id)
                out = ""
                async for chunk in agent.run(user_input, stream=True, session=session):
                    for content in getattr(chunk, "contents", []) or []:
                        annotations = getattr(content, "annotations", []) or []
                        if annotations:
                            citations.extend(annotations)
                    text = str(chunk.text) if chunk.text else ""
                    text = re.sub(r"【\d+:\d+†?[^】]*】", _replace_marker, text)
                    out += text

            sources: list[Source] = []
            seen: set[str] = set()
            for c in citations:
                add_props = (c.get("additional_properties") or {}) if isinstance(c, dict) else {}
                url = add_props.get("get_url") or c.get("url") or add_props.get("url") or "N/A"
                title = c.get("title", "N/A") if isinstance(c, dict) else "N/A"
                if title in seen:
                    continue
                seen.add(title)
                sources.append(Source(doc_id=title, score=0.0, text=title, metadata={"url": url}))
            return out, sources

        return asyncio.run(_run())

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
                    k_nearest_neighbors=top_k,
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
            return docs
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

        context_parts = []
        sources = []
        for i, doc in enumerate(search_docs):
            text = doc["text"][:4000]
            context_parts.append(f"[Source {i + 1} | id={doc['doc_id']}]:\n{text}")
            sources.append(Source(
                doc_id=doc["doc_id"],
                score=round(doc.get("score", 0), 4),
                text=text[:500],
                metadata={k: v for k, v in doc.items() if k not in ("text", "score")},
            ))

        context = "\n\n---\n\n".join(context_parts)

        answer, agent_sources = self._run_agent(question, conversation_id)
        sources = sources + agent_sources
        return QAResponse(
            question=question,
            answer=_strip_links_from_answer(answer),
            sources=sources if include_sources else [],
            model=settings.azure_openai_chat_deployment,
        )

    def answer_question(
        self,
        question: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
        include_sources: bool = True,
        document_ids: Optional[list[str]] = None,
        external_index_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> QAResponse:
        settings = get_settings()

        # External index path
        if external_index_id:
            return self._answer_from_external(question, top_k, external_index_id, include_sources, conversation_id)

        # 1. If filters are active, narrow document_ids to matching files
        if filters and not document_ids:
            from src.api.modules.ingestion.service import ingestion_service
            matching_ids = self._filter_document_ids(filters, ingestion_service)
            if matching_ids is not None:
                document_ids = matching_ids

        # 2. Search: try Azure AI Search first, then external data sources, then in-memory
        try:
            search_docs = self._search_azure_ai_search(question, top_k, document_ids)
        except RuntimeError:
            logger.warning("Azure AI Search unavailable, falling back to in-memory search")
            search_docs = []

        # For files in 'extracted' state (not yet indexed), inject blob text directly
        if document_ids:
            extracted_docs = self._build_extracted_context(document_ids, question)
            if extracted_docs:
                # Merge: extracted docs fill gaps for files not yet in AI Search
                indexed_file_ids = {d["doc_id"] for d in search_docs}
                for doc in extracted_docs:
                    if doc["doc_id"] not in indexed_file_ids:
                        search_docs.append(doc)
        else:
            # No specific document scope — check if any uploaded files are only extracted
            from src.api.modules.ingestion.service import ingestion_service
            ingestion_service._ensure_loaded()
            extracted_ids = [
                f.id for f in ingestion_service._uploaded_files.values()
                if f.status == "extracted"
            ]
            if extracted_ids:
                extracted_docs = self._build_extracted_context(extracted_ids, question)
                search_docs.extend(extracted_docs)

        # Only include external live-query sources when user is not explicitly scoped to selected documents.
        if not document_ids:
            external_docs = self._search_external_data_sources(question, top_k)
            if external_docs:
                search_docs.extend(external_docs)

        # Normalize mixed result shapes (AI Search, extracted context, external data sources)
        normalized_docs = []
        for doc in search_docs:
            doc_id = doc.get("doc_id") or doc.get("id")
            if not doc_id:
                doc_id = str(doc.get("source_file") or f"doc-{len(normalized_docs) + 1}")
            normalized_docs.append({
                **doc,
                "doc_id": doc_id,
                "text": doc.get("text", ""),
                "type": doc.get("type", "unknown"),
                "source_file": doc.get("source_file", "unknown"),
            })
        search_docs = normalized_docs

        # Deduplicate by doc_id (keep highest score per document)
        seen = {}
        deduped = []
        for doc in search_docs:
            did = doc["doc_id"]
            if did in seen:
                if doc.get("score", 0) > deduped[seen[did]].get("score", 0):
                    deduped[seen[did]] = doc
                continue
            seen[did] = len(deduped)
            deduped.append(doc)
        search_docs = sorted(deduped, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

        if not search_docs:
            logger.info("AI Search returned no results, falling back to SQL search")
            search_docs = self._search_sql(question, top_k, document_ids)

        if not search_docs:
            logger.info("SQL search returned no results, falling back to in-memory search")
            search_docs = self._search_in_memory(question, top_k, document_ids)

        # 3. Build context
        context_parts = []
        sources = []
        for i, doc in enumerate(search_docs):
            text = doc["text"]
            # Truncate very long texts to fit context window
            if len(text) > 4000:
                text = text[:4000] + "..."
            context_parts.append(
                f"[Source {i + 1} | id={doc['doc_id']}] (type: {doc['type']}, file: {doc['source_file']}):\n{text}"
            )
            sources.append(Source(
                doc_id=doc["doc_id"],
                score=round(doc.get("score", 0), 4),
                text=text[:500],
                metadata={"type": doc["type"], "source_file": doc["source_file"]},
            ))

        context = "\n\n---\n\n".join(context_parts)

        # 3. Generate answer
        answer, agent_sources = self._run_agent(question, conversation_id)

        return QAResponse(
            question=question,
            answer=_strip_links_from_answer(answer),
            sources=agent_sources if include_sources else [],
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

        # Search: AI Search first, then external sources, fallback to in-memory
        search_docs = self._search_azure_ai_search(last_user_message, top_k, document_ids)

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

        if not document_ids:
            external_docs = self._search_external_data_sources(last_user_message, top_k)
            if external_docs:
                search_docs.extend(external_docs)
                search_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
                search_docs = search_docs[:top_k]

        if not search_docs:
            logger.info("AI Search returned no results, falling back to SQL search")
            search_docs = self._search_sql(last_user_message, top_k, document_ids)

        if not search_docs:
            search_docs = self._search_in_memory(last_user_message, top_k, document_ids)

        context_parts = []
        sources = []
        for i, doc in enumerate(search_docs):
            text = doc["text"][:4000]
            context_parts.append(f"[Source {i + 1} | id={doc['doc_id']}]:\n{text}")
            sources.append(Source(
                doc_id=doc["doc_id"], score=round(doc.get("score", 0), 4),
                text=text[:500],
                metadata={"type": doc["type"], "source_file": doc["source_file"]},
            ))

        context = "\n\n---\n\n".join(context_parts)

        all_messages = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        answer, agent_sources = self._run_agent(all_messages, conversation_id)

        return QAResponse(
            question=last_user_message,
            answer=_strip_links_from_answer(answer),
            sources=agent_sources,
            model=settings.azure_openai_chat_deployment,
        )


rag_service = RAGService()



