import csv
import json
import logging
import os
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

logger = logging.getLogger(__name__)


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

    def _track_file(self, filename: str, data: list[dict]):
        """Track an uploaded file with AI-extracted summary, keywords, and filter schema.
        
        Uses Content Understanding service for all extraction + filter schema generation.
        """
        from datetime import datetime

        file_id = filename.rsplit(".", 1)[0]

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
                        if ext.get("summary") and not meta.get("summary"):
                            meta["summary"] = ext["summary"]
                        if ext.get("keywords"):
                            meta["key_phrases"] = ext["keywords"]

                        # Merge filter dimension values (sentiment, topic, etc.)
                        fvals = filter_map.get(doc_id, {})
                        for dim_id, dim_vals in fvals.items():
                            if isinstance(dim_vals, list) and len(dim_vals) == 1:
                                meta[dim_id] = dim_vals[0]
                            elif isinstance(dim_vals, list):
                                meta[dim_id] = ", ".join(dim_vals)
                            else:
                                meta[dim_id] = dim_vals

                        sql_service.save_document(doc_id, {
                            **item,
                            "summary": ext.get("summary", item.get("summary", "")),
                            "key_phrases": ext.get("keywords", item.get("key_phrases", [])),
                            "metadata": meta,
                        })
                    logger.info(f"Enriched metadata written to SQL for {len(data)} docs")
            except Exception as e:
                logger.warning(f"Failed to write enriched metadata to SQL: {e}")

        except Exception as e:
            logger.warning(f"AI extraction failed (using fallback): {e}")
            if not summary:
                types = set(item.get("type", "unknown") for item in data)
                summary = f"{len(data)} {', '.join(sorted(types))} documents"
                keywords = sorted(types)

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
            updates: dict = {"status": status, "error": error}
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
        file_id = filename.rsplit(".", 1)[0]
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
        file_id = filename.rsplit(".", 1)[0]
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

    def load_csv_file(self, file_path: str) -> IngestionResult:
        by_type: dict[str, int] = {}
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                doc = Document(
                    id=str(row["id"]),
                    type=row.get("type", "unknown"),
                    text=row.get("text", ""),
                    metadata=DocumentMetadata(
                        product=row.get("product"),
                        category=row.get("category"),
                        timestamp=row.get("timestamp"),
                    ),
                )
                self._documents[doc.id] = doc
                by_type[doc.type] = by_type.get(doc.type, 0) + 1

        return IngestionResult(
            total_loaded=len(by_type) and sum(by_type.values()),
            by_type=by_type,
            sample_ids=list(self._documents.keys())[:5],
        )

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
                conn.commit()
                conn.close()
                logger.info("Cleared all data from SQL")
        except Exception as e:
            logger.warning(f"Failed to clear SQL tables: {e}")

        # Clear AI Search index
        try:
            from src.api.config import get_settings
            from azure.identity import DefaultAzureCredential
            from azure.search.documents import SearchClient
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
                cursor.execute("DELETE FROM uploaded_files WHERE id = ?", file_id)
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
