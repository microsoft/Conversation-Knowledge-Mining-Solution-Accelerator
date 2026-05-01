from typing import Optional
import logging
import os

import yaml
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from src.api.config import get_settings
from src.api.modules.embeddings.service import embeddings_service
from src.api.modules.rag.models import QAResponse, Source

logger = logging.getLogger(__name__)

# Load prompts from config file (editable without code changes)
_PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "app", "config", "prompts.yaml")
_PROMPTS: dict = {}
try:
    with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
        _PROMPTS = yaml.safe_load(f) or {}
except Exception:
    logger.warning("Could not load prompts.yaml — using built-in defaults")


def _get_prompt(key: str, fallback: str, **kwargs) -> str:
    """Load a prompt from config, falling back to the built-in default."""
    template = _PROMPTS.get(key, fallback)
    return template.format(**kwargs) if kwargs else template


class RAGService:
    """Retrieval-Augmented Generation service for question answering."""

    def __init__(self):
        self._client: Optional[AzureOpenAI] = None

    def _get_client(self) -> AzureOpenAI:
        if self._client is None:
            settings = get_settings()
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
            self._client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-10-21",
            )
        return self._client

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
            select_fields = ["id", "text", "summary", "type", "source_file"]

            results = client.search(
                search_text=query,
                vector_queries=vector_queries if vector_queries else None,
                top=top_k,
                filter=filter_str,
                select=select_fields,
            )

            docs = []
            for r in results:
                doc_id = r.get("doc_id", r["id"])
                # Strip chunk suffix to get base doc ID
                if "_c" in doc_id:
                    doc_id = doc_id.split("_c")[0]
                docs.append({
                    "doc_id": doc_id,
                    "text": r.get("text", ""),
                    "summary": r.get("summary", ""),
                    "type": r.get("type", "unknown"),
                    "source_file": r.get("source_file", ""),
                    "score": r.get("@search.score", 0),
                })
            return docs
        except Exception as e:
            logger.warning(f"Azure AI Search failed: {e}")
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

    def _answer_from_external(self, question: str, top_k: int,
                               external_index_id: str, include_sources: bool) -> QAResponse:
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
            context_parts.append(f"[Document {i+1}: {doc['doc_id']}]:\n{text}")
            sources.append(Source(
                doc_id=doc["doc_id"],
                score=round(doc.get("score", 0), 4),
                text=text[:500],
                metadata={k: v for k, v in doc.items() if k not in ("text", "score")},
            ))

        context = "\n\n---\n\n".join(context_parts)
        system_prompt = _get_prompt(
            "rag_external_prompt",
            "You are a helpful assistant. Answer based ONLY on the provided documents.\n\nDocuments:\n{context}",
            context=context,
        )

        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        return QAResponse(
            question=question,
            answer=response.choices[0].message.content,
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
    ) -> QAResponse:
        settings = get_settings()

        # External index path
        if external_index_id:
            return self._answer_from_external(question, top_k, external_index_id, include_sources)

        # 1. If filters are active, narrow document_ids to matching files
        if filters and not document_ids:
            from src.api.modules.ingestion.service import ingestion_service
            matching_ids = self._filter_document_ids(filters, ingestion_service)
            if matching_ids is not None:
                document_ids = matching_ids

        # 2. Search: try Azure AI Search first, then external data sources, then in-memory
        search_docs = self._search_azure_ai_search(question, top_k, document_ids)

        # Also search external live-query data sources
        external_docs = self._search_external_data_sources(question, top_k)
        if external_docs:
            search_docs.extend(external_docs)
            search_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
            search_docs = search_docs[:top_k]

        if not search_docs:
            logger.info("AI Search returned no results, falling back to in-memory search")
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
                f"[Document {i+1}: {doc['doc_id']}] (type: {doc['type']}, file: {doc['source_file']}):\n{text}"
            )
            sources.append(Source(
                doc_id=doc["doc_id"],
                score=round(doc.get("score", 0), 4),
                text=text[:500],
                metadata={"type": doc["type"], "source_file": doc["source_file"]},
            ))

        context = "\n\n---\n\n".join(context_parts)

        # 3. Generate answer
        system_prompt = _get_prompt(
            "rag_system_prompt",
            "You are a helpful assistant. Answer based ONLY on the provided documents.\n\nDocuments:\n{context}",
            context=context,
        )

        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        return QAResponse(
            question=question,
            answer=response.choices[0].message.content,
            sources=sources if include_sources else [],
            model=settings.azure_openai_chat_deployment,
        )

    def answer_conversation(
        self,
        messages: list[dict],
        top_k: int = 5,
        filters: Optional[dict] = None,
        document_ids: Optional[list[str]] = None,
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

        external_docs = self._search_external_data_sources(last_user_message, top_k)
        if external_docs:
            search_docs.extend(external_docs)
            search_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
            search_docs = search_docs[:top_k]

        if not search_docs:
            search_docs = self._search_in_memory(last_user_message, top_k, document_ids)

        context_parts = []
        sources = []
        for i, doc in enumerate(search_docs):
            text = doc["text"][:4000]
            context_parts.append(f"[Document {i+1}: {doc['doc_id']}]:\n{text}")
            sources.append(Source(
                doc_id=doc["doc_id"], score=round(doc.get("score", 0), 4),
                text=text[:500],
                metadata={"type": doc["type"], "source_file": doc["source_file"]},
            ))

        context = "\n\n---\n\n".join(context_parts)
        system_prompt = _get_prompt(
            "rag_conversation_prompt",
            "You are a helpful assistant. Answer based ONLY on the provided documents.\n\nDocuments:\n{context}",
            context=context,
        )

        all_messages = [{"role": "system", "content": system_prompt}] + messages

        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=all_messages,
            temperature=0.3,
            max_tokens=1000,
        )

        return QAResponse(
            question=last_user_message,
            answer=response.choices[0].message.content,
            sources=sources,
            model=settings.azure_openai_chat_deployment,
        )


rag_service = RAGService()
