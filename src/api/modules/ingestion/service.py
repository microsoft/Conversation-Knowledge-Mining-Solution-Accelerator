import csv
import json
import logging
import os
import re
import threading
from typing import Optional

from src.api.config import get_settings
from src.api.modules.ingestion.models import (
    Document,
    DocumentMetadata,
    IngestionResult,
    IngestionStats,
    UploadedFile,
    FilterSchema,
    FilterDimension,
    FilterValue,
)
from src.api.modules.ingestion.error_messages import format_error_for_user

logger = logging.getLogger(__name__)

_CSV_TEXT_CANDIDATES = ("text", "content", "body", "description", "summary", "notes")
_CSV_ID_CANDIDATES = ("id", "document_id", "record_id", "conversation_id")
_CSV_TYPE_CANDIDATES = ("type", "document_type", "category")
_ENTITY_FALLBACK_MAX_DOCS = 30
_ENTITY_FALLBACK_TEXT_LIMIT = 6000
_ENTITY_STOPWORDS = {
    "The", "This", "That", "These", "Those", "And", "But", "For", "With", "From", "Into",
    "Without", "After", "Before", "During", "Project", "Collection", "Document", "Documents",
}


class IngestionService:
    """Handles loading and managing documents. Uses Azure SQL for persistence, in-memory as cache."""

    def __init__(self):
        self._documents: dict[str, Document] = {}
        self._uploaded_files: dict[str, UploadedFile] = {}
        self._filter_schema: FilterSchema = FilterSchema()
        self._loaded_from_db = False
        self._processing_locks: dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()  # protects _processing_locks dict

    def acquire_processing_lock(self, file_id: str) -> bool:
        """Try to acquire a per-document lock. Returns False if already locked."""
        with self._locks_lock:
            if file_id not in self._processing_locks:
                self._processing_locks[file_id] = threading.Lock()
            lock = self._processing_locks[file_id]
        return lock.acquire(blocking=False)

    def release_processing_lock(self, file_id: str):
        """Release a per-document lock."""
        with self._locks_lock:
            lock = self._processing_locks.get(file_id)
        if lock:
            try:
                lock.release()
            except RuntimeError:
                pass  # Already released

    def is_already_processed(self, file_id: str) -> bool:
        """Check if a file has already been fully indexed (status=ready)."""
        self._ensure_loaded()
        f = self._uploaded_files.get(file_id)
        return f is not None and f.status == "ready"

    def reload(self):
        """Force re-read from database on next access."""
        self._loaded_from_db = False
        self._documents.clear()
        self._uploaded_files.clear()
        self._filter_schema = FilterSchema()

    def _ensure_loaded(self):
        """Load persisted data from Azure SQL on first access."""
        if self._loaded_from_db:
            return
        self._loaded_from_db = True
        try:
            from src.api.storage.sql_service import sql_service
            if not sql_service.available:
                return

            # Load documents
            docs = sql_service.load_all_documents()
            for item in docs:
                try:
                    meta = item.get("metadata", {})
                    if isinstance(meta, dict):
                        meta = DocumentMetadata(**{k: v for k, v in meta.items()
                                                   if k in DocumentMetadata.__fields__})
                    doc = Document(
                        id=item["id"],
                        type=item.get("type", "unknown"),
                        text=item.get("text", ""),
                        metadata=meta,
                    )
                    self._documents[doc.id] = doc
                except Exception as e:
                    logger.warning(f"Failed to load document {item.get('id', '?')}: {e}")

            # Load uploaded files
            files = sql_service.load_all_uploaded_files()
            for item in files:
                try:
                    uf = UploadedFile(
                        id=item["id"],
                        filename=item.get("filename", ""),
                        doc_count=item.get("doc_count", 0),
                        summary=item.get("summary", ""),
                        keywords=item.get("keywords", []),
                        filter_values=item.get("filter_values", {}),
                        doc_ids=item.get("doc_ids", []),
                        uploaded_at=item.get("uploaded_at", ""),
                    )
                    # If doc_ids not stored in SQL, rebuild from loaded documents
                    if not uf.doc_ids:
                        uf.doc_ids = [
                            did for did, doc in self._documents.items()
                            if (doc.metadata.source_file or "") == uf.filename
                        ]
                    self._uploaded_files[uf.id] = uf
                except Exception as e:
                    logger.warning(f"Failed to load uploaded file {item.get('id', '?')}: {e}")

            # Load filter schema — only if we have files to match it against
            if self._uploaded_files:
                schema_data = sql_service.load_filter_schema()
                if schema_data and schema_data.get("dimensions"):
                    dims = []
                    for d in schema_data["dimensions"]:
                        vals = [FilterValue(**v) for v in d.get("values", [])]
                        dims.append(FilterDimension(
                            id=d["id"], label=d["label"],
                            type=d.get("type", "multi_select"), values=vals,
                        ))
                    self._filter_schema = FilterSchema(domain=schema_data.get("domain", ""), dimensions=dims)
            else:
                # No files = no filters. Clear stale schema from DB.
                self._filter_schema = FilterSchema()
                try:
                    sql_service.save_filter_schema({"domain": "", "dimensions": []})
                except Exception as e:
                    logger.warning(f"Failed to clear stale filter schema: {e}")

            # Do not auto-delete uploaded file records during reload.
            # Files should only be removed via explicit clear/delete operations.
            if self._uploaded_files:
                for file_id, uploaded in list(self._uploaded_files.items()):
                    # Keep doc_count aligned to current documents for accurate UI counts.
                    if uploaded.filename:
                        matched_count = sum(
                            1 for doc in self._documents.values()
                            if (doc.metadata.source_file or "") == uploaded.filename
                        )
                        if matched_count > 0 and matched_count != uploaded.doc_count:
                            updated = uploaded.copy(update={"doc_count": matched_count})
                            self._uploaded_files[file_id] = updated
                            self._persist_file(updated)

            if self._documents:
                logger.info(f"Loaded from Azure SQL: {len(self._documents)} docs, {len(self._uploaded_files)} files")
        except Exception as e:
            logger.warning(f"Failed to load from Azure SQL: {e}")

    @property
    def documents(self) -> dict[str, Document]:
        self._ensure_loaded()
        return self._documents

    def _persist_doc(self, item: dict):
        """Persist a single document to Azure SQL."""
        try:
            from src.api.storage.sql_service import sql_service
            sql_service.save_document(item["id"], item)
        except Exception as e:
            logger.warning(f"Failed to persist document {item.get('id', '?')}: {e}")

    def _persist_file(self, uploaded_file: UploadedFile):
        """Persist uploaded file metadata to Azure SQL."""
        try:
            from src.api.storage.sql_service import sql_service
            sql_service.save_uploaded_file(uploaded_file.dict())
        except Exception as e:
            logger.warning(f"Failed to persist file {uploaded_file.id}: {e}")

    def _persist_schema(self):
        """Persist the current filter schema to Azure SQL."""
        try:
            from src.api.storage.sql_service import sql_service
            schema_dict = {
                "domain": self._filter_schema.domain if hasattr(self._filter_schema, "domain") else "",
                "dimensions": [
                    {
                        "id": d.id, "label": d.label, "type": d.type,
                        "values": [{"value": v.value, "label": v.label, "count": v.count} for v in d.values],
                    }
                    for d in self._filter_schema.dimensions
                ],
            }
            sql_service.save_filter_schema(schema_dict)
        except Exception as e:
            logger.warning(f"Failed to persist filter schema: {e}")

    def _persist_to_azure(self, raw_items: list[dict]):
        """Persist documents to Azure Blob Storage + Search Index in background."""
        settings = get_settings()
        if not settings.azure_storage_account and not settings.azure_search_endpoint:
            return  # No Azure config, skip

        try:
            from src.api.modules.ingestion.azure_storage import azure_storage_service
            result = azure_storage_service.persist_documents(raw_items)
            logger.info(
                f"Azure persist: {result['blob_uploaded']} blobs, "
                f"{result['search_indexed']} indexed"
            )
        except Exception as e:
            logger.warning(f"Azure persist failed (non-blocking): {e}")

    @staticmethod
    def _normalize_scalar(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def _synthesize_relationships(entities: list[dict], max_edges: int = 8) -> list[dict]:
        """Create lightweight co-occurrence relationships when explicit edges are absent."""
        names = []
        seen = set()
        for e in entities:
            if not isinstance(e, dict):
                continue
            n = str(e.get("name", "")).strip()
            if not n:
                continue
            key = n.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(n)

        rels: list[dict] = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                rels.append({
                    "subject": names[i],
                    "relation": "co_occurs_with",
                    "object": names[j],
                    "context": "Entities co-mentioned in the same document",
                    "confidence": 0.55,
                })
                if len(rels) >= max_edges:
                    return rels
        return rels

    @staticmethod
    def _extract_entities_heuristic(text: str, max_entities: int = 12) -> list[dict]:
        """Deterministic fallback when AI extraction is unavailable."""
        if not text:
            return []

        matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text)
        entities: list[dict] = []
        seen = set()
        for candidate in matches:
            name = " ".join(candidate.split()).strip()
            if not name or name in _ENTITY_STOPWORDS:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            entities.append({
                "name": name,
                "type": "unknown",
                "context": "Extracted from document text",
                "confidence": 0.45,
            })
            if len(entities) >= max_entities:
                break
        return entities

    def _extract_entities_with_fallback(self, text: str, max_chars: int = _ENTITY_FALLBACK_TEXT_LIMIT) -> list[dict]:
        text = (text or "").strip()
        if not text:
            return []

        try:
            from src.api.modules.processing.service import ProcessingService

            processing_service = ProcessingService()
            entity_resp = processing_service.extract_entities(text[:max_chars])
            extracted_entities = []
            for ent in entity_resp.entities:
                if not ent.text:
                    continue
                extracted_entities.append({
                    "name": ent.text,
                    "type": ent.type or "Unknown",
                    "context": "",
                    "confidence": ent.confidence,
                })
            if extracted_entities:
                return extracted_entities
        except Exception as e:
            logger.debug(f"Entity extraction via ProcessingService failed, using heuristic fallback: {e}")

        return self._extract_entities_heuristic(text[:max_chars])

    def _extract_relationships_with_fallback(self, text: str, entities: list[dict]) -> list[dict]:
        """Extract semantic relationships via LLM; fall back to co-occurrence synthesis."""
        text = (text or "").strip()
        if not text or not entities:
            return []
        try:
            from src.api.capabilities.extract_relationships import extract_relationships
            resp = extract_relationships(text=text)
            rels = resp.get("result", [])
            if rels:
                return rels
        except Exception as e:
            logger.debug(f"LLM relationship extraction failed, using synthesis fallback: {e}")
        return self._synthesize_relationships(entities)

    def _build_csv_documents(self, file_path: str, filename: str | None = None) -> list[dict]:
        actual_filename = filename or os.path.basename(file_path)
        documents: list[dict] = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for index, row in enumerate(reader, start=1):
                normalized = {str(k).strip(): self._normalize_scalar(v) for k, v in row.items() if k}
                lowered = {k.lower(): v for k, v in normalized.items()}

                doc_id = next((lowered[key] for key in _CSV_ID_CANDIDATES if lowered.get(key)), "")
                if not doc_id:
                    doc_id = f"{actual_filename.rsplit('.', 1)[0]}_{index}"

                doc_type = next((lowered[key] for key in _CSV_TYPE_CANDIDATES if lowered.get(key)), "csv_row")

                text = next((lowered[key] for key in _CSV_TEXT_CANDIDATES if lowered.get(key)), "")
                if not text:
                    text_parts = [
                        f"{key}: {value}" for key, value in normalized.items()
                        if value and key.lower() not in set(_CSV_ID_CANDIDATES)
                    ]
                    text = "; ".join(text_parts)

                metadata = {
                    key: value for key, value in normalized.items()
                    if value and key.lower() not in set(_CSV_ID_CANDIDATES + _CSV_TYPE_CANDIDATES + _CSV_TEXT_CANDIDATES)
                }
                metadata["source_file"] = actual_filename
                metadata["source_type"] = "csv"

                documents.append({
                    "id": doc_id,
                    "type": doc_type,
                    "text": text,
                    "metadata": metadata,
                })
        return documents

    def _track_file(self, filename: str, data: list[dict]):
        """Track an uploaded file with AI-extracted summary, keywords, and filter schema.

        Uses Content Understanding service for all extraction + filter schema generation.
        """
        from datetime import datetime

        file_id = filename.rsplit(".", 1)[0].replace(" ", "_")

        summary = ""
        keywords: list[str] = []
        filter_values: dict[str, list[str]] = {}

        # Check if documents already have CU-enriched data (single-doc upload path)
        has_enrichment = any(d.get("summary") or d.get("key_phrases") for d in data)

        if has_enrichment:
            summaries = [d.get("summary", "") for d in data if d.get("summary")]
            all_phrases: set[str] = set()
            all_topics: set[str] = set()
            for d in data:
                for kp in d.get("key_phrases", []):
                    all_phrases.add(kp)
                for t in d.get("topics", []):
                    all_topics.add(t)

            summary = summaries[0] if len(summaries) == 1 else (
                f"Collection of {len(data)} documents. " + (summaries[0] if summaries else "")
            )
            keywords = sorted(all_phrases)[:10]
            if all_topics:
                filter_values["topics"] = sorted(all_topics)

        # Use CU service for batch enrichment + filter schema generation
        try:
            from src.api.modules.document_intelligence.service import ContentUnderstandingService
            cu_service = ContentUnderstandingService()

            # Gather ALL document text across all uploaded files for a complete schema
            all_docs_for_schema = list(data)  # start with current file's docs
            for other_file in self._uploaded_files.values():
                if other_file.id != file_id:
                    # Include other files' docs for complete schema generation
                    for doc_id, doc in self._documents.items():
                        source = doc.metadata.source_file or ""
                        if source == other_file.filename:
                            all_docs_for_schema.append({
                                "id": doc_id, "type": doc.type,
                                "text": self.normalize_text(doc)[:500],
                                "metadata": {"source_file": source},
                            })

            extraction = cu_service.enrich_batch(all_docs_for_schema)

            # Replace schema entirely (not merge) to prevent stale dimensions
            dimensions_raw = extraction.get("dimensions", [])
            new_dims = []
            for dim in dimensions_raw:
                values = [
                    FilterValue(value=v["value"], label=v["label"], count=v.get("count", 0))
                    for v in dim.get("values", [])
                ]
                new_dims.append(FilterDimension(
                    id=dim["id"], label=dim["label"],
                    type=dim.get("type", "multi_select"), values=values,
                ))
            self._filter_schema = FilterSchema(domain="", dimensions=new_dims)
            self._persist_schema()

            # If no CU single-doc enrichment, use batch extraction for summary/keywords
            if not has_enrichment:
                doc_extractions = extraction.get("doc_extractions", [])
                if doc_extractions:
                    sums = [d.get("summary", "") for d in doc_extractions if d.get("summary")]
                    all_kw: set[str] = set()
                    for d in doc_extractions:
                        for kw in d.get("keywords", []):
                            all_kw.add(kw)
                    summary = sums[0] if len(sums) == 1 else (
                        f"Collection of {len(data)} documents. " + (sums[0] if sums else "")
                    )
                    keywords = sorted(all_kw)[:8]

            # Merge filter mappings
            doc_filters = extraction.get("document_filters", [])
            merged: dict[str, set[str]] = {}
            for df in doc_filters:
                for dim_id, vals in df.get("values", {}).items():
                    merged.setdefault(dim_id, set()).update(vals if isinstance(vals, list) else [vals])
            for k, v in merged.items():
                filter_values[k] = sorted(v)

            # ── Write enriched metadata back to SQL documents table ──
            # The insights engine reads JSON_VALUE(metadata, '$.field') so enriched
            # fields (topics, sentiment, etc.) must be in each document's metadata.
            doc_extractions = extraction.get("doc_extractions", [])
            extraction_map = {d["id"]: d for d in doc_extractions if d.get("id")}
            filter_map = {df["id"]: df.get("values", {}) for df in doc_filters if df.get("id")}
            fallback_budget = _ENTITY_FALLBACK_MAX_DOCS

            try:
                from src.api.storage.sql_service import sql_service
                if sql_service.available:
                    for item in data:
                        doc_id = item.get("id", "")
                        if not doc_id:
                            continue

                        meta = dict(item.get("metadata", {}))

                        # Merge per-doc extraction (summary, keywords)
                        ext = extraction_map.get(doc_id, {})
                        if not isinstance(ext, dict):
                            ext = {}

                        # Deterministic fallback: if batch enrichment omitted entities,
                        # call entity extraction directly for this document (bounded budget).
                        if not ext.get("entities") and fallback_budget > 0:
                            text_for_entities = str(item.get("text", "") or "").strip()
                            if text_for_entities:
                                try:
                                    extracted_entities = self._extract_entities_with_fallback(text_for_entities)
                                    if extracted_entities:
                                        ext["entities"] = extracted_entities
                                        if not ext.get("relationships"):
                                            ext["relationships"] = self._extract_relationships_with_fallback(text_for_entities, extracted_entities)
                                except Exception as e:
                                    logger.debug(f"Entity fallback extraction failed for {doc_id}: {e}")
                                finally:
                                    fallback_budget -= 1

                        if ext.get("summary") and not meta.get("summary"):
                            meta["summary"] = ext["summary"]
                        if ext.get("keywords"):
                            meta["key_phrases"] = ext["keywords"]
                        if ext.get("topics"):
                            meta["topics"] = ext["topics"]
                        if ext.get("metadata") and isinstance(ext.get("metadata"), dict):
                            for meta_key, meta_value in ext["metadata"].items():
                                if meta_value not in (None, "", []):
                                    meta[meta_key] = meta_value
                        if ext.get("entities"):
                            entity_names = [
                                e.get("name", "").strip() for e in ext["entities"]
                                if isinstance(e, dict) and e.get("name")
                            ]
                            if entity_names:
                                meta["entities"] = entity_names
                        if ext.get("relationships"):
                            item["relationships"] = ext["relationships"]

                        # Merge filter dimension values (sentiment, topic, etc.)
                        fvals = filter_map.get(doc_id, {})
                        for dim_id, dim_vals in fvals.items():
                            if isinstance(dim_vals, list) and len(dim_vals) == 1:
                                meta[dim_id] = dim_vals[0]
                            elif isinstance(dim_vals, list):
                                meta[dim_id] = ", ".join(dim_vals)
                            else:
                                meta[dim_id] = dim_vals

                        if ext.get("keywords"):
                            item["key_phrases"] = ext["keywords"]
                        if ext.get("summary"):
                            item["summary"] = ext["summary"]
                        if ext.get("topics"):
                            item["topics"] = ext["topics"]
                        if ext.get("entities"):
                            item["entities"] = ext["entities"]
                        item["metadata"] = meta

                        sql_service.save_document(doc_id, {
                            **item,
                            "summary": ext.get("summary", item.get("summary", "")),
                            "entities": ext.get("entities", item.get("entities", [])),
                            "key_phrases": ext.get("keywords", item.get("key_phrases", [])),
                            "topics": ext.get("topics", item.get("topics", [])),
                            "metadata": meta,
                        })
                        sql_service.save_entity_graph(
                            doc_id=doc_id,
                            source_file=meta.get("source_file", ""),
                            entities=ext.get("entities", item.get("entities", [])),
                            relationships=ext.get("relationships", item.get("relationships", [])),
                        )
                    logger.info(f"Enriched metadata written to SQL for {len(data)} docs")
            except Exception as e:
                logger.warning(f"Failed to write enriched metadata to SQL: {e}")

        except Exception as e:
            logger.warning(f"AI extraction failed (using fallback): {e}")
            if not summary and data:
                types = set(d.get("type", "unknown") for d in data)
                summary = f"{len(data)} {', '.join(sorted(types))} documents"
                keywords = sorted(types)

            # Keep graph persistence working even when enrichment service is unavailable.
            try:
                from src.api.storage.sql_service import sql_service

                if sql_service.available:
                    for item in data:
                        doc_id = item.get("id", "")
                        if not doc_id:
                            continue

                        meta = dict(item.get("metadata", {}))
                        entities = item.get("entities", [])
                        text_for_graph = str(item.get("text", "") or "").strip()
                        if not entities:
                            entities = self._extract_entities_with_fallback(text_for_graph)
                        relationships = item.get("relationships", [])
                        if entities and not relationships:
                            relationships = self._extract_relationships_with_fallback(text_for_graph, entities)

                        if entities:
                            item["entities"] = entities
                            item["relationships"] = relationships
                            meta["entities"] = [
                                e.get("name", "").strip()
                                for e in entities
                                if isinstance(e, dict) and e.get("name")
                            ]
                            item["metadata"] = meta

                        sql_service.save_document(doc_id, {
                            **item,
                            "summary": item.get("summary", ""),
                            "entities": item.get("entities", []),
                            "key_phrases": item.get("key_phrases", []),
                            "topics": item.get("topics", []),
                            "metadata": item.get("metadata", {}),
                        })
                        sql_service.save_entity_graph(
                            doc_id=doc_id,
                            source_file=meta.get("source_file", ""),
                            entities=item.get("entities", []),
                            relationships=item.get("relationships", []),
                        )
            except Exception as persist_error:
                logger.warning(f"Fallback SQL graph persistence failed: {persist_error}")

        existing = self._uploaded_files.get(file_id)
        doc_ids = existing.doc_ids if existing and existing.doc_ids else [d.get("id", "") for d in data]
        doc_count = max(len(data), len(doc_ids))

        uploaded_file = UploadedFile(
            id=file_id,
            filename=filename,
            doc_count=doc_count,
            summary=summary,
            keywords=keywords,
            filter_values=filter_values,
            doc_ids=doc_ids,
            uploaded_at=existing.uploaded_at if existing else datetime.utcnow().isoformat() + "Z",
            status=existing.status if existing else "ready",
            error=existing.error if existing else "",
        )
        self._uploaded_files[file_id] = uploaded_file
        self._persist_file(uploaded_file)
        return uploaded_file

    @property
    def uploaded_files(self) -> list[UploadedFile]:
        self._ensure_loaded()
        return list(self._uploaded_files.values())

    @property
    def filter_schema(self) -> FilterSchema:
        self._ensure_loaded()
        return self._filter_schema

    def _update_file_status(self, file_id: str, status: str, error: str = ""):
        """Update the processing status of an uploaded file."""
        self._ensure_loaded()
        if file_id in self._uploaded_files:
            f = self._uploaded_files[file_id]
            # Format error message for user if present
            formatted_error = ""
            if error and status == "failed":
                formatted_error = format_error_for_user(error, filename=f.filename)
                logger.warning(f"[{file_id}] File failed: {error} (user message: {formatted_error})")
            else:
                formatted_error = error

            updates: dict = {"status": status, "error": formatted_error}
            # Recalculate doc_count when marking ready or extracted
            if status in ("ready", "extracted") and f.doc_count == 0:
                count = sum(
                    1 for doc in self._documents.values()
                    if (doc.metadata.source_file or "") == f.filename
                    or doc.id == file_id
                )
                if count > 0:
                    updates["doc_count"] = count
            self._uploaded_files[file_id] = f.copy(update=updates)
            self._persist_file(self._uploaded_files[file_id])

    def load_json_file(self, file_path: str) -> IngestionResult:
        self._ensure_loaded()
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # Known enrichment fields that should become filterable dimensions
        _ENRICHMENT_FIELDS = {"sentiment", "satisfied", "complaint", "mined_topic", "topic"}
        # Field name mapping for non-standard formats (e.g. sample data)
        _FIELD_MAP = {"ConversationId": "id", "Content": "text"}

        by_type: dict[str, int] = {}
        dim_values: dict[str, dict[str, int]] = {}  # field -> {value: count}

        for item in raw_data:
            # Normalize field names if needed
            for old_key, new_key in _FIELD_MAP.items():
                if old_key in item and new_key not in item:
                    item[new_key] = item.pop(old_key)
            if "type" not in item:
                item["type"] = "call_transcript"
            if "text" not in item:
                item["text"] = ""

            # Tag document with source file for delete tracking
            meta = item.get("metadata", {})
            if "source_file" not in meta:
                meta["source_file"] = os.path.basename(file_path)

            # Preserve enrichment fields in metadata for filter building
            for field in _ENRICHMENT_FIELDS:
                val = item.get(field, "")
                if val and isinstance(val, str) and val.strip():
                    meta[field] = val.strip()
                    dim_values.setdefault(field, {})
                    dim_values[field][val.strip()] = dim_values[field].get(val.strip(), 0) + 1

            item["metadata"] = meta
            doc = Document(
                id=item["id"],
                type=item["type"],
                text=item["text"],
                metadata=DocumentMetadata(**{k: v for k, v in meta.items()
                                             if k in DocumentMetadata.__fields__}),
            )
            self._documents[doc.id] = doc
            by_type[doc.type] = by_type.get(doc.type, 0) + 1

            self._persist_doc(item)

        # Build filter dimensions from enrichment fields
        if dim_values:
            _SKIP = {"topic"}  # topic is too free-form, keep others
            new_dims = list(self._filter_schema.dimensions)
            existing_ids = {d.id for d in new_dims}
            for field, vals in dim_values.items():
                if field in _SKIP or field in existing_ids:
                    continue
                if 2 <= len(vals) <= 20:
                    sorted_vals = sorted(vals.items(), key=lambda x: -x[1])
                    new_dims.append(FilterDimension(
                        id=field,
                        label=field.replace("_", " ").title(),
                        type="multi_select",
                        values=[FilterValue(value=v, label=v, count=c) for v, c in sorted_vals],
                    ))
            if len(new_dims) > len(self._filter_schema.dimensions):
                self._filter_schema = FilterSchema(domain=self._filter_schema.domain, dimensions=new_dims)
                self._persist_schema()

        filename = os.path.basename(file_path)

        # Track doc_ids for reliable delete
        ingested_ids = [item["id"] for item in raw_data]
        from datetime import datetime
        file_id = filename.rsplit(".", 1)[0].replace(" ", "_")
        self._uploaded_files[file_id] = UploadedFile(
            id=file_id,
            filename=filename,
            doc_count=len(raw_data),
            summary=f"{len(raw_data)} documents",
            keywords=[],
            filter_values={},
            doc_ids=ingested_ids,
            uploaded_at=datetime.utcnow().isoformat() + "Z",
        )

        self._track_file(filename, raw_data)
        self._persist_to_azure(raw_data)

        return IngestionResult(
            total_loaded=len(raw_data),
            by_type=by_type,
            sample_ids=list(self._documents.keys())[:5],
        )

    def load_json_data(self, data: list[dict], filename: str = "uploaded_data.json") -> IngestionResult:
        self._ensure_loaded()
        by_type: dict[str, int] = {}
        for item in data:
            doc = Document(
                id=item["id"],
                type=item.get("type", "unknown"),
                text=item.get("text", ""),
                metadata=DocumentMetadata(**{k: v for k, v in item.get("metadata", {}).items()
                                             if k in DocumentMetadata.__fields__}),
            )
            self._documents[doc.id] = doc
            by_type[doc.type] = by_type.get(doc.type, 0) + 1

            self._persist_doc(item)

        # Track file immediately (in-memory) so it appears in the file list right away
        from datetime import datetime
        file_id = filename.rsplit(".", 1)[0].replace(" ", "_")
        ingested_ids = [item["id"] for item in data]

        # Preserve existing status/error if file already exists (e.g., set to "processing" by upload)
        existing = self._uploaded_files.get(file_id)
        uploaded_file = UploadedFile(
            id=file_id,
            filename=filename,
            doc_count=len(data),
            summary=existing.summary if existing and existing.summary != "Processing..." else f"{len(data)} documents",
            keywords=existing.keywords if existing else [],
            filter_values=existing.filter_values if existing else {},
            doc_ids=ingested_ids,
            uploaded_at=existing.uploaded_at if existing else datetime.utcnow().isoformat() + "Z",
            status=existing.status if existing else "ready",
            error=existing.error if existing else "",
        )
        self._uploaded_files[file_id] = uploaded_file

        return IngestionResult(
            total_loaded=len(data),
            by_type=by_type,
            sample_ids=list(self._documents.keys())[:5],
        )

    def finalize_ingestion(self, data: list[dict], filename: str):
        """Background task: AI enrichment, file tracking, and Azure persistence.
        Called after the HTTP response is already sent."""
        try:
            self._track_file(filename, data)
        except Exception as e:
            logger.warning(f"Background file tracking failed: {e}")
        try:
            self._persist_to_azure(data)
        except Exception as e:
            logger.warning(f"Background Azure persist failed: {e}")

    def load_csv_file(self, file_path: str, filename: str | None = None) -> IngestionResult:
        self._ensure_loaded()
        documents = self._build_csv_documents(file_path, filename)
        actual_filename = filename or os.path.basename(file_path)
        return self.load_json_data(documents, filename=actual_filename)

    def load_default_dataset(self) -> IngestionResult:
        settings = get_settings()
        dataset_path = os.path.join(settings.data_dir, "ContactCenter_usecase", "sample_processed_data.json")
        return self.load_json_file(dataset_path)

    def get_document(self, doc_id: str) -> Optional[Document]:
        self._ensure_loaded()
        return self._documents.get(doc_id)

    def search_documents(
        self,
        doc_type: Optional[str] = None,
        product: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
    ) -> list[Document]:
        self._ensure_loaded()
        results = list(self._documents.values())
        if doc_type:
            results = [d for d in results if d.type == doc_type]
        if product:
            results = [d for d in results if d.metadata.product == product]
        if category:
            results = [d for d in results if d.metadata.category == category]
        if query:
            q = query.lower()
            results = [d for d in results if self._text_contains(d, q)]
        return results

    def get_stats(self) -> IngestionStats:
        self._ensure_loaded()
        docs = list(self._documents.values())
        by_type: dict[str, int] = {}
        for doc in docs:
            by_type[doc.type] = by_type.get(doc.type, 0) + 1

        # Build dynamic dimension stats from filter schema
        by_dimension: dict[str, dict[str, int]] = {}
        for dim in self._filter_schema.dimensions:
            dim_counts = {v.label: v.count for v in dim.values if v.count > 0}
            if dim_counts:
                by_dimension[dim.label] = dim_counts

        return IngestionStats(
            total_documents=len(docs),
            by_type=by_type,
            by_dimension=by_dimension,
        )

    def normalize_text(self, doc: Document) -> str:
        """Flatten document text to a single searchable string."""
        if isinstance(doc.text, str):
            return doc.text
        elif isinstance(doc.text, list):
            return " ".join(
                f"{seg.get('speaker', 'Unknown')}: {seg.get('text', '')}"
                for seg in doc.text
            )
        return str(doc.text)

    def _text_contains(self, doc: Document, query: str) -> bool:
        return query in self.normalize_text(doc).lower()

    def get_available_filters(self) -> dict[str, list[str]]:
        """Return all filter dimensions and their values — fully dynamic from AI-generated schema."""
        self._ensure_loaded()
        result: dict[str, list[str]] = {}

        # Primary source: AI-generated filter schema (from SQL)
        for dim in self._filter_schema.dimensions:
            values = sorted(v.label for v in dim.values)
            if values:
                result[dim.label] = values

        # Fallback: if no schema, derive from document types
        if not result:
            types = sorted(set(d.type for d in self._documents.values()))
            if types:
                result["Document Type"] = types

        return result

    def clear(self):
        """Clear all data from memory, SQL, and AI Search."""
        self._documents.clear()
        self._uploaded_files.clear()
        self._filter_schema = FilterSchema()
        self._loaded_from_db = False

        # Clear SQL tables
        try:
            from src.api.storage.sql_service import sql_service
            if sql_service.available:
                conn = sql_service._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM documents")
                cursor.execute("DELETE FROM uploaded_files")
                cursor.execute("DELETE FROM filter_schemas")
                cursor.execute("DELETE FROM enrichment_cache")
                cursor.execute("DELETE FROM document_entities")
                cursor.execute("DELETE FROM entity_relationships")
                cursor.execute("DELETE FROM entity_nodes")
                conn.commit()
                conn.close()
                logger.info("Cleared all data from SQL")
        except Exception as e:
            logger.warning(f"Failed to clear SQL tables: {e}")

        # Clear AI Search index
        try:
            from src.api.config import get_settings
            from azure.identity import DefaultAzureCredential
            from azure.search.documents.indexes import SearchIndexClient
            settings = get_settings()
            if settings.azure_search_endpoint:
                cred = DefaultAzureCredential()
                index_name = settings.azure_search_index_name
                # Delete and recreate index to clear all documents
                index_client = SearchIndexClient(
                    endpoint=settings.azure_search_endpoint, credential=cred
                )
                try:
                    index_def = index_client.get_index(index_name)
                    index_client.delete_index(index_name)
                    index_client.create_index(index_def)
                    logger.info(f"Cleared AI Search index '{index_name}'")
                except Exception as e:
                    logger.warning(f"Failed to clear AI Search index: {e}")
        except Exception as e:
            logger.warning(f"Failed to clear AI Search: {e}")

        # Purge Azure Queue so background workers can't re-inject deleted documents.
        try:
            from src.api.modules.ingestion.queue_service import (
                queue_service, EXTRACTION_QUEUE, ENRICHMENT_QUEUE,
            )
            if queue_service.available:
                for q_name in (EXTRACTION_QUEUE, ENRICHMENT_QUEUE):
                    try:
                        client = queue_service._get_client(q_name)
                        # Receive and delete all messages from the queue
                        deleted_count = 0
                        while True:
                            messages = list(client.receive_messages(max_messages=32, visibility_timeout=1))
                            if not messages:
                                break
                            for msg in messages:
                                client.delete_message(msg.id, msg.pop_receipt)
                                deleted_count += 1
                        logger.info(f"Purged queue '{q_name}': deleted {deleted_count} messages")
                    except Exception as e:
                        logger.warning(f"Failed to purge queue '{q_name}': {e}")
        except Exception as e:
            logger.warning(f"Failed to purge queues: {e}")

        # Delete all blobs (raw/, extracted/, documents/) so stale files from a
        # previous scenario are not left behind in storage.
        try:
            from src.api.modules.ingestion.azure_storage import azure_storage_service
            azure_storage_service.clear_all_blobs()
        except Exception as e:
            logger.warning(f"Failed to clear blobs: {e}")

    def delete_file(self, file_id: str) -> bool:
        """Delete an uploaded file and all its documents."""
        self._ensure_loaded()
        if file_id not in self._uploaded_files:
            return False

        uploaded_file = self._uploaded_files[file_id]

        # Use tracked doc_ids first (reliable), fall back to matching
        if uploaded_file.doc_ids:
            doc_ids_to_remove = [did for did in uploaded_file.doc_ids if did in self._documents]
        else:
            # Fallback: match by source_file metadata or doc_id
            doc_ids_to_remove = []
            file_filename = uploaded_file.filename
            file_stem = file_filename.rsplit(".", 1)[0].replace(" ", "_") if file_filename else file_id
            for doc_id, doc in self._documents.items():
                source = doc.metadata.source_file or ""
                if source == file_filename:
                    doc_ids_to_remove.append(doc_id)
                    continue
                stem = source.rsplit(".", 1)[0].replace(" ", "_") if source else ""
                if stem == file_id or stem == file_stem:
                    doc_ids_to_remove.append(doc_id)
                    continue
                if doc_id == file_id:
                    doc_ids_to_remove.append(doc_id)

        for doc_id in doc_ids_to_remove:
            if doc_id in self._documents:
                del self._documents[doc_id]

        # Remove uploaded file record from memory
        del self._uploaded_files[file_id]

        # Clear filter schema entirely — remaining files will rebuild it during enrichment
        self._filter_schema = FilterSchema()
        self._persist_schema()

        # Persist deletions to SQL (single connection, all at once)
        try:
            from src.api.storage.sql_service import sql_service
            if sql_service.available:
                conn = sql_service._get_connection()
                cursor = conn.cursor()
                for doc_id in doc_ids_to_remove:
                    cursor.execute("DELETE FROM documents WHERE id = ?", doc_id)
                for doc_id in doc_ids_to_remove:
                    cursor.execute("DELETE FROM document_entities WHERE doc_id = ?", doc_id)
                    cursor.execute("DELETE FROM entity_relationships WHERE doc_id = ?", doc_id)
                cursor.execute("DELETE FROM uploaded_files WHERE id = ?", file_id)
                cursor.execute(
                    """
                    DELETE FROM entity_nodes
                    WHERE id NOT IN (
                        SELECT DISTINCT entity_id FROM document_entities
                        UNION
                        SELECT DISTINCT subject_entity_id FROM entity_relationships
                        UNION
                        SELECT DISTINCT object_entity_id FROM entity_relationships WHERE object_entity_id IS NOT NULL
                    )
                    """
                )
                conn.commit()
                conn.close()
        except Exception as e:
            logger.warning(f"SQL cleanup failed for {file_id}: {e}")

        # Remove from blob storage, AI Search (doc entries + chunks)
        # Include file_id itself since chunks use it as doc_id
        all_ids_for_search = list(set(doc_ids_to_remove + [file_id]))
        try:
            from src.api.modules.ingestion.azure_storage import azure_storage_service
            azure_storage_service.delete_file_data(file_id, uploaded_file.filename, all_ids_for_search)
        except Exception as e:
            logger.warning(f"Storage/search cleanup failed for {file_id}: {e}")

        logger.info(f"Deleted file '{file_id}' and {len(doc_ids_to_remove)} documents")
        return True


# Singleton
ingestion_service = IngestionService()
