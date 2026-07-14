"""Azure AI Search data source adapter — wraps the existing ExternalIndexService pattern."""

import logging
import uuid
from typing import Iterator, Optional

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

from src.api.modules.data_sources.base import (
    BaseExternalDataSource,
    ColumnInfo,
    DataSourceConfig,
)

logger = logging.getLogger(__name__)


class AzureSearchDataSource(BaseExternalDataSource):
    """Adapter for Azure AI Search — enables BYOI (bring your own index)."""

    def _get_client(self, config: DataSourceConfig) -> SearchClient:
        credential = DefaultAzureCredential()
        return SearchClient(
            endpoint=config.endpoint,
            index_name=config.table_or_query,  # index name stored in table_or_query
            credential=credential,
        )

    def _normalize_row(self, row: dict, mapping) -> dict:
        doc = self._apply_field_mapping(row, mapping)

        if not doc.get("id"):
            for id_key in ("id", "key", "doc_id", "metadata_storage_path", "chunk_id"):
                if row.get(id_key):
                    doc["id"] = str(row.get(id_key))
                    break
        if not doc.get("id"):
            doc["id"] = str(uuid.uuid4())[:8]

        if not doc.get("text"):
            for text_key in (
                "text", "content", "chunk", "body", "summary", "description", "title"
            ):
                val = row.get(text_key)
                if isinstance(val, str) and val.strip():
                    doc["text"] = val
                    break

        if not doc.get("text"):
            for key, val in row.items():
                if isinstance(val, str) and val.strip() and not key.startswith("@"):
                    doc["text"] = val
                    break

        # Carry over enrichment fields produced by the processing pipeline so
        # that extraction_facets can use persisted data instead of re-mining text.
        metadata = doc.setdefault("metadata", {})
        for enrich_key in ("topics", "key_phrases", "entities", "summary", "sentiment"):
            val = row.get(enrich_key)
            if val is not None:
                doc[enrich_key] = val
                metadata[enrich_key] = val

        return doc

    def connect(self, config: DataSourceConfig) -> bool:
        try:
            client = self._get_client(config)
            client.get_document_count()
            return True
        except Exception as e:
            logger.warning(f"Azure Search connect failed: {e}")
            return False

    def disconnect(self) -> None:
        pass

    def test_connection(self, config: DataSourceConfig) -> dict:
        try:
            client = self._get_client(config)
            count = client.get_document_count()
            return {"success": True, "row_count": count, "message": f"Connected to index. {count} documents found."}
        except Exception as e:
            return {"success": False, "row_count": 0, "message": str(e)}

    def get_schema(self, config: DataSourceConfig) -> list[ColumnInfo]:
        try:
            client = self._get_client(config)
            results = client.search(search_text="*", top=1)
            columns = []
            for doc in results:
                for key, value in doc.items():
                    if key.startswith("@"):
                        continue
                    columns.append(ColumnInfo(
                        name=key,
                        data_type=type(value).__name__ if value is not None else "str",
                    ))
                break
            return columns
        except Exception as e:
            logger.warning(f"Failed to get Azure Search schema: {e}")
            return []

    def search(self, config: DataSourceConfig, query: str, top_k: int = 5,
               filters: Optional[dict] = None) -> list[dict]:
        try:
            client = self._get_client(config)
            mapping = config.field_mapping
            # Use schema-agnostic search to avoid brittle failures across heterogeneous indexes.
            results = list(client.search(search_text=query, top=top_k))

            docs = []
            for r in results:
                row = dict(r)
                doc = self._normalize_row(row, mapping)

                doc["score"] = r.get("@search.score", 0)
                docs.append(doc)
            return docs
        except Exception as e:
            logger.warning(f"Azure Search search failed: {e}")
            return []

    def sample(self, config: DataSourceConfig, count: int = 20) -> list[dict]:
        try:
            client = self._get_client(config)
            results = client.search(search_text="*", top=count)

            docs = []
            for r in results:
                doc = self._normalize_row(dict(r), config.field_mapping)
                docs.append(doc)
            return docs
        except Exception as e:
            logger.warning(f"Azure Search sample failed: {e}")
            return []

    def fetch_all(self, config: DataSourceConfig, batch_size: int = 1000) -> Iterator[list[dict]]:
        """Azure AI Search doesn't support cursor-based pagination natively.
        We use search with * and page through results."""
        try:
            client = self._get_client(config)
            results = client.search(search_text="*", top=batch_size)

            batch = []
            for r in results:
                doc = self._apply_field_mapping(dict(r), config.field_mapping)
                if not doc["id"]:
                    doc["id"] = r.get("id", str(uuid.uuid4())[:8])
                batch.append(doc)
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch
        except Exception as e:
            logger.warning(f"Azure Search fetch_all failed: {e}")
