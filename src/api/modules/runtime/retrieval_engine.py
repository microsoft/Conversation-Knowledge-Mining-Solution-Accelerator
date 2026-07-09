from __future__ import annotations

import logging
from typing import Optional

from azure.identity import DefaultAzureCredential

from src.api.config import get_settings
from src.api.modules.runtime.registry import runtime_registry

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """Unified retrieval orchestration across all registered knowledge sources."""

    @staticmethod
    def _normalize_doc(doc: dict, source_kind: str, source_name: str) -> dict:
        return {
            "id": str(doc.get("id") or doc.get("doc_id") or ""),
            "doc_id": str(doc.get("doc_id") or doc.get("id") or ""),
            "text": str(doc.get("text") or ""),
            "summary": str(doc.get("summary") or ""),
            "type": str(doc.get("type") or "unknown"),
            "source_file": str(doc.get("source_file") or source_name),
            "source_id": source_kind,
            "source_name": source_name,
            "source_kind": source_kind,
            "metadata": doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {},
            "score": float(doc.get("score") or 0.0),
        }

    def _search_azure_ai_search(self, query: str, top_k: int = 5, document_ids: Optional[list[str]] = None) -> list[dict]:
        settings = get_settings()
        if not settings.azure_search_endpoint or not settings.azure_search_index_name:
            return []

        try:
            from azure.search.documents import SearchClient
            from azure.search.documents.models import VectorizedQuery
            from src.api.modules.embeddings.service import EmbeddingsService

            client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index_name,
                credential=DefaultAzureCredential(),
            )

            filter_str = None
            if document_ids:
                ids_csv = ",".join(document_ids[:50])
                filter_str = f"search.in(id, '{ids_csv}')"

            vector_queries = []
            try:
                emb_service = EmbeddingsService()
                query_emb = emb_service.generate_embedding(query)
                vector_queries.append(
                    VectorizedQuery(
                        vector=query_emb.embedding,
                        k=top_k,
                        fields="text_vector",
                    )
                )
            except Exception as ex:
                logger.debug("Vector search unavailable in retrieval engine: %s", ex)

            results = client.search(
                search_text=query,
                vector_queries=vector_queries if vector_queries else None,
                top=top_k,
                filter=filter_str,
            )

            out = []
            for r in results:
                doc_id = r.get("doc_id") or r.get("id") or ""
                if "_c" in str(doc_id):
                    doc_id = str(doc_id).split("_c")[0]
                out.append(
                    self._normalize_doc(
                        {
                            "id": doc_id,
                            "doc_id": doc_id,
                            "text": r.get("text") or r.get("content") or r.get("summary") or r.get("title") or "",
                            "summary": r.get("summary", ""),
                            "type": r.get("type", "unknown"),
                            "source_file": r.get("source_file") or r.get("title") or "Uploaded Documents",
                            "score": r.get("@search.score", 0.0),
                        },
                        source_kind="uploaded",
                        source_name="Uploaded Documents",
                    )
                )
            return out
        except Exception as ex:
            logger.warning("Azure AI Search retrieval failed: %s", ex)
            return []

    def _search_sql(self, query: str, top_k: int = 5, document_ids: Optional[list[str]] = None) -> list[dict]:
        try:
            from src.api.storage.sql_service import sql_service

            sql_service._ensure_init()
            if not sql_service._initialized:
                return []

            conn = sql_service._get_connection()
            cursor = conn.cursor()

            words = [w for w in query.lower().split() if w]
            where_clauses = ["text_content IS NOT NULL AND LEN(text_content) > 0"]
            if document_ids:
                ids_csv = ",".join([f"'{did}'" for did in document_ids[:50]])
                where_clauses.append(f"id IN ({ids_csv})")
            where = " AND ".join(where_clauses)

            cursor.execute(
                f"SELECT TOP {max(top_k * 4, top_k)} id, text_content, summary, source_file, doc_type FROM documents WHERE {where}"
            )

            docs = []
            for row in cursor.fetchall():
                doc_id, text, summary, source_file, doc_type = row
                text_val = str(text or "")
                if not text_val.strip():
                    continue
                score = 0.05
                if words:
                    text_lower = text_val.lower()
                    matches = sum(1 for w in words if w in text_lower)
                    score = matches / max(len(words), 1) if matches > 0 else 0.05

                docs.append(
                    self._normalize_doc(
                        {
                            "id": str(doc_id),
                            "doc_id": str(doc_id),
                            "text": text_val[:8000],
                            "summary": str(summary or ""),
                            "type": str(doc_type or "document"),
                            "source_file": str(source_file or "Uploaded Documents"),
                            "score": score,
                        },
                        source_kind="uploaded",
                        source_name="Uploaded Documents",
                    )
                )

            conn.close()
            docs.sort(key=lambda d: float(d.get("score") or 0.0), reverse=True)
            return docs[:top_k]
        except Exception as ex:
            logger.warning("SQL retrieval failed: %s", ex)
            return []

    @staticmethod
    def _filter_doc_ids(docs: list[dict], document_ids: Optional[list[str]]) -> list[dict]:
        if not document_ids:
            return docs
        allowed = set(document_ids)
        return [d for d in docs if (d.get("doc_id") or d.get("id")) in allowed]

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
        document_ids: Optional[list[str]] = None,
        source: Optional[str] = None,
    ) -> list[dict]:
        docs: list[dict] = []

        resolved_source = source
        effective_filters = dict(filters or {})
        requested_source = str(effective_filters.get("source") or "").strip()
        if (resolved_source in (None, "all")) and requested_source:
            canonical_id, _ = runtime_registry.resolve_external_source(requested_source)
            if canonical_id:
                resolved_source = canonical_id
                effective_filters.pop("source", None)
            elif requested_source.lower() in ("uploaded", "seed"):
                resolved_source = requested_source.lower()
                effective_filters.pop("source", None)

        include_internal = resolved_source in (None, "all", "uploaded", "seed")
        include_external = resolved_source not in ("uploaded", "seed")

        if include_internal:
            docs.extend(self._search_azure_ai_search(query=query, top_k=max(top_k * 2, top_k), document_ids=document_ids))
            if not docs:
                docs.extend(self._search_sql(query=query, top_k=max(top_k * 2, top_k), document_ids=document_ids))

            # Always blend in normalized in-memory source to keep seeded data first-class.
            docs.extend(runtime_registry.search(query=query, filters=effective_filters, source="uploaded", top_k=max(top_k * 2, top_k)))
            docs.extend(runtime_registry.search(query=query, filters=effective_filters, source="seed", top_k=max(top_k * 2, top_k)))

        if include_external:
            external_source = resolved_source if resolved_source not in (None, "all") else "all"
            docs.extend(runtime_registry.search(query=query, filters=effective_filters, source=external_source, top_k=max(top_k * 2, top_k)))

        docs = self._filter_doc_ids(docs, document_ids)

        dedup: dict[str, dict] = {}
        for doc in docs:
            doc_id = str(doc.get("doc_id") or doc.get("id") or "")
            if not doc_id:
                continue
            if doc_id not in dedup or float(doc.get("score") or 0.0) > float(dedup[doc_id].get("score") or 0.0):
                dedup[doc_id] = doc

        merged = list(dedup.values())
        merged.sort(key=lambda d: float(d.get("score") or 0.0), reverse=True)
        return merged[:top_k]


retrieval_engine = RetrievalEngine()
