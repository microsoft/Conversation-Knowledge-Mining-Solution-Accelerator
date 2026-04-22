import csv
import json
import logging
import os
from typing import Optional

from backend.config import get_settings
from backend.modules.ingestion.models import (
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
    """Handles loading and managing documents. Uses Cosmos DB for persistence, in-memory as cache."""

    def __init__(self):
        self._documents: dict[str, Document] = {}
        self._uploaded_files: dict[str, UploadedFile] = {}
        self._filter_schema: FilterSchema = FilterSchema()
        self._loaded_from_db = False

    def _ensure_loaded(self):
        """Load persisted data from Azure SQL on first access."""
        if self._loaded_from_db:
            return
        self._loaded_from_db = True
        try:
            from backend.storage.sql_service import sql_service
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
                except Exception:
                    pass

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
                        uploaded_at=item.get("uploaded_at", ""),
                    )
                    self._uploaded_files[uf.id] = uf
                except Exception:
                    pass

            # Load filter schema
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

            if self._documents:
                logger.info(f"Loaded from Azure SQL: {len(self._documents)} docs, {len(self._uploaded_files)} files")
        except Exception as e:
            logger.warning(f"Failed to load from Azure SQL: {e}")

    @property
    def documents(self) -> dict[str, Document]:
        self._ensure_loaded()
        return self._documents

    def _persist_doc_to_cosmos(self, item: dict):
        """Persist a single document to Azure SQL (non-blocking)."""
        try:
            from backend.storage.sql_service import sql_service
            sql_service.save_document(item["id"], item)
        except Exception:
            pass

    def _persist_file_to_cosmos(self, uploaded_file: UploadedFile):
        """Persist uploaded file metadata to Azure SQL."""
        try:
            from backend.storage.sql_service import sql_service
            sql_service.save_uploaded_file(uploaded_file.dict())
        except Exception:
            pass

    def _persist_schema_to_cosmos(self):
        """Persist the current filter schema to Azure SQL."""
        try:
            from backend.storage.sql_service import sql_service
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
        except Exception:
            pass

    def _persist_to_azure(self, raw_items: list[dict]):
        """Persist documents to Azure Blob Storage + Search Index in background."""
        settings = get_settings()
        if not settings.azure_storage_account and not settings.azure_search_endpoint:
            return  # No Azure config, skip

        try:
            from backend.modules.ingestion.azure_storage import azure_storage_service
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
            from backend.modules.document_intelligence.service import ContentUnderstandingService
            cu_service = ContentUnderstandingService()
            extraction = cu_service.enrich_batch(data)

            # Store filter schema — merge with existing dimensions
            domain = extraction.get("domain", "")
            dimensions_raw = extraction.get("dimensions", [])
            existing_dims = {d.id: d for d in self._filter_schema.dimensions}
            for dim in dimensions_raw:
                values = [
                    FilterValue(value=v["value"], label=v["label"], count=v.get("count", 0))
                    for v in dim.get("values", [])
                ]
                if dim["id"] in existing_dims:
                    # Merge values into existing dimension
                    existing_vals = {v.value for v in existing_dims[dim["id"]].values}
                    for v in values:
                        if v.value not in existing_vals:
                            existing_dims[dim["id"]].values.append(v)
                        else:
                            for ev in existing_dims[dim["id"]].values:
                                if ev.value == v.value:
                                    ev.count += v.count
                else:
                    existing_dims[dim["id"]] = FilterDimension(
                        id=dim["id"], label=dim["label"],
                        type=dim.get("type", "multi_select"), values=values,
                    )
            self._filter_schema = FilterSchema(domain="", dimensions=list(existing_dims.values()))
            self._persist_schema_to_cosmos()

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

        except Exception as e:
            logger.warning(f"AI extraction failed (using fallback): {e}")
            if not summary:
                types = set(item.get("type", "unknown") for item in data)
                summary = f"{len(data)} {', '.join(sorted(types))} documents"
                keywords = sorted(types)

        uploaded_file = UploadedFile(
            id=file_id,
            filename=filename,
            doc_count=len(data),
            summary=summary,
            keywords=keywords,
            filter_values=filter_values,
            uploaded_at=datetime.utcnow().isoformat() + "Z",
        )
        self._uploaded_files[file_id] = uploaded_file
        self._persist_file_to_cosmos(uploaded_file)
        return uploaded_file

    @property
    def uploaded_files(self) -> list[UploadedFile]:
        self._ensure_loaded()
        return list(self._uploaded_files.values())

    @property
    def filter_schema(self) -> FilterSchema:
        self._ensure_loaded()
        return self._filter_schema

    def load_json_file(self, file_path: str) -> IngestionResult:
        self._ensure_loaded()
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        by_type: dict[str, int] = {}
        for item in raw_data:
            doc = Document(
                id=item["id"],
                type=item["type"],
                text=item["text"],
                metadata=DocumentMetadata(**item.get("metadata", {})),
            )
            self._documents[doc.id] = doc
            by_type[doc.type] = by_type.get(doc.type, 0) + 1

            self._persist_doc_to_cosmos(item)

        filename = os.path.basename(file_path)
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
                type=item["type"],
                text=item["text"],
                metadata=DocumentMetadata(**item.get("metadata", {})),
            )
            self._documents[doc.id] = doc
            by_type[doc.type] = by_type.get(doc.type, 0) + 1

            # Persist document to Cosmos DB
            self._persist_doc_to_cosmos(item)

        self._track_file(filename, data)
        self._persist_to_azure(data)

        return IngestionResult(
            total_loaded=len(data),
            by_type=by_type,
            sample_ids=list(self._documents.keys())[:5],
        )

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
        dataset_path = os.path.join(settings.data_dir, "Customer_service_data.json")
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
        self._documents.clear()
        self._uploaded_files.clear()
        self._filter_schema = FilterSchema()

    def delete_file(self, file_id: str) -> bool:
        """Delete an uploaded file and all its documents."""
        self._ensure_loaded()
        if file_id not in self._uploaded_files:
            return False

        uploaded_file = self._uploaded_files[file_id]

        # Remove documents belonging to this file
        doc_ids_to_remove = []
        for doc_id, doc in self._documents.items():
            source = doc.metadata.source_file or ""
            stem = source.rsplit(".", 1)[0].replace(" ", "_") if source else doc_id
            if stem == file_id or doc_id == file_id:
                doc_ids_to_remove.append(doc_id)

        for doc_id in doc_ids_to_remove:
            del self._documents[doc_id]
            # Remove from SQL
            try:
                from backend.storage.sql_service import sql_service
                if sql_service.available:
                    conn = sql_service._get_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM documents WHERE id = ?", doc_id)
                    conn.commit()
                    conn.close()
            except Exception:
                pass

        # Remove from AI Search
        try:
            from backend.config import get_settings
            from azure.identity import DefaultAzureCredential
            from azure.search.documents import SearchClient
            settings = get_settings()
            if settings.azure_search_endpoint:
                client = SearchClient(
                    endpoint=settings.azure_search_endpoint,
                    index_name=settings.azure_search_index_name,
                    credential=DefaultAzureCredential(),
                )
                client.delete_documents(documents=[{"id": did} for did in doc_ids_to_remove])
        except Exception:
            pass

        # Remove uploaded file record
        del self._uploaded_files[file_id]
        try:
            from backend.storage.sql_service import sql_service
            if sql_service.available:
                conn = sql_service._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM uploaded_files WHERE id = ?", file_id)
                conn.commit()
                conn.close()
        except Exception:
            pass

        logger.info(f"Deleted file '{file_id}' and {len(doc_ids_to_remove)} documents")
        return True


# Singleton
ingestion_service = IngestionService()
