"""Data source registry — manages adapters, CRUD, and persistence to SQL.

Key extension points:
- _load_adapters(): register new data source types here
- _auto_detect_mapping(): customize column name detection heuristics
- get_supported_types(): add UI metadata for new source types
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.api.modules.data_sources.base import (
    BaseExternalDataSource,
    DataSourceConfig,
    DataSourceType,
    FieldMapping,
    QueryMode,
    AuthMethod,
    ColumnInfo,
)

logger = logging.getLogger(__name__)

# Adapter map — type → class
_ADAPTER_CLASSES: dict[DataSourceType, type[BaseExternalDataSource]] = {}


def _load_adapters():
    """Register all data source adapters. To add a new type, import it and add to the dict."""
    global _ADAPTER_CLASSES
    if _ADAPTER_CLASSES:
        return
    from src.api.modules.data_sources.fabric import FabricDataSource
    from src.api.modules.data_sources.sql import SqlDataSource
    from src.api.modules.data_sources.synapse import SynapseDataSource
    from src.api.modules.data_sources.odbc import OdbcDataSource
    from src.api.modules.data_sources.azure_search import AzureSearchDataSource

    _ADAPTER_CLASSES = {
        DataSourceType.FABRIC: FabricDataSource,
        DataSourceType.SQL: SqlDataSource,
        DataSourceType.SYNAPSE: SynapseDataSource,
        DataSourceType.ODBC: OdbcDataSource,
        DataSourceType.AZURE_SEARCH: AzureSearchDataSource,
    }


class DataSourceRegistry:
    """Manages data source connections with SQL persistence."""

    def __init__(self):
        self._cache: dict[str, DataSourceConfig] = {}
        self._loaded = False

    def _get_adapter(self, source_type: DataSourceType) -> BaseExternalDataSource:
        _load_adapters()
        cls = _ADAPTER_CLASSES.get(source_type)
        if not cls:
            raise ValueError(f"Unsupported data source type: {source_type}")
        return cls()

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        try:
            from src.api.storage.sql_service import sql_service
            if not sql_service.available:
                return
            configs = sql_service.load_data_sources()
            for cfg in configs:
                self._cache[cfg["id"]] = DataSourceConfig(**cfg)
        except Exception as e:
            logger.warning(f"Failed to load data sources from SQL: {e}")

    def create(self, config: DataSourceConfig) -> DataSourceConfig:
        self._ensure_loaded()
        config.id = str(uuid.uuid4())[:12]
        config.status = "disconnected"

        # Test connection
        adapter = self._get_adapter(config.source_type)
        result = adapter.test_connection(config)
        if result["success"]:
            config.status = "connected"
            config.doc_count = result["row_count"]
        else:
            config.status = "error"
            config.error_message = result["message"]

        self._cache[config.id] = config
        self._persist(config)

        # Auto-ingest for ingest/both modes on successful connection
        if config.status == "connected" and config.query_mode in (QueryMode.INGEST, QueryMode.BOTH):
            try:
                ingest_result = self.ingest(config.id)
                if ingest_result["success"]:
                    logger.info(f"Auto-ingested {ingest_result['total_ingested']} docs from {config.name}")
            except Exception as e:
                logger.warning(f"Auto-ingest failed for {config.name}: {e}")

        return config

    def update(self, source_id: str, updates: dict) -> Optional[DataSourceConfig]:
        self._ensure_loaded()
        config = self._cache.get(source_id)
        if not config:
            return None

        for key, value in updates.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)

        # Re-test connection if connection params changed
        conn_keys = {"connection_string", "endpoint", "database", "table_or_query", "auth_method"}
        if conn_keys & set(updates.keys()):
            adapter = self._get_adapter(config.source_type)
            result = adapter.test_connection(config)
            config.status = "connected" if result["success"] else "error"
            config.doc_count = result.get("row_count", 0)
            config.error_message = "" if result["success"] else result["message"]

        self._cache[source_id] = config
        self._persist(config)
        return config

    def delete(self, source_id: str) -> bool:
        self._ensure_loaded()
        if source_id not in self._cache:
            return False
        del self._cache[source_id]
        try:
            from src.api.storage.sql_service import sql_service
            sql_service.delete_data_source(source_id)
        except Exception:
            pass
        return True

    def get(self, source_id: str) -> Optional[DataSourceConfig]:
        self._ensure_loaded()
        return self._cache.get(source_id)

    def list_all(self) -> list[DataSourceConfig]:
        self._ensure_loaded()
        return list(self._cache.values())

    def list_live_sources(self) -> list[DataSourceConfig]:
        """Return sources configured for live query (live or both)."""
        self._ensure_loaded()
        return [
            c for c in self._cache.values()
            if c.status == "connected" and c.query_mode in (QueryMode.LIVE, QueryMode.BOTH)
        ]

    def test_connection(self, config: DataSourceConfig) -> dict:
        adapter = self._get_adapter(config.source_type)
        result = adapter.test_connection(config)
        # Also get schema for the response
        columns = []
        if result["success"]:
            try:
                columns = adapter.get_schema(config)
            except Exception:
                pass
        result["columns"] = [c.model_dump() for c in columns]
        # Auto-detect field mapping from column names
        if columns:
            result["suggested_mapping"] = self._auto_detect_mapping(columns)
        return result

    @staticmethod
    def _auto_detect_mapping(columns: list[ColumnInfo]) -> dict:
        """Guess field mapping from column names. Covers 90%+ of datasets."""
        col_names = [c.name.lower() for c in columns]
        col_lookup = {c.name.lower(): c.name for c in columns}

        def _find(candidates: list[str]) -> str:
            for c in candidates:
                if c in col_names:
                    return col_lookup[c]
            # Partial match
            for c in candidates:
                for cn in col_names:
                    if c in cn:
                        return col_lookup[cn]
            return ""

        # ID: exact or partial match
        id_field = _find(["id", "_id", "key", "pk", "doc_id", "document_id", "record_id"])
        if not id_field and columns:
            id_field = columns[0].name  # fallback to first column

        # Text: the main content column
        text_field = _find([
            "text", "content", "body", "transcript", "message",
            "description", "summary", "conversation", "note", "comment",
            "text_content", "full_text",
        ])
        if not text_field:
            # Fallback: pick the first string-like column that isn't the ID
            for c in columns:
                dtype = c.data_type.lower()
                if c.name != id_field and any(t in dtype for t in ["str", "nvarchar", "text", "varchar"]):
                    text_field = c.name
                    break
        if not text_field and len(columns) > 1:
            text_field = columns[1].name

        # Title
        title_field = _find(["title", "name", "subject", "filename", "heading", "topic"])

        # Type
        type_field = _find(["type", "category", "kind", "doc_type", "document_type", "label", "class"])

        # Timestamp
        ts_field = _find(["timestamp", "created_at", "date", "datetime", "updated_at", "time"])

        return {
            "id_field": id_field or "id",
            "text_field": text_field or "text",
            "title_field": title_field,
            "type_field": type_field,
            "timestamp_field": ts_field,
            "metadata_fields": {},
        }

    def get_schema(self, source_id: str) -> list[ColumnInfo]:
        self._ensure_loaded()
        config = self._cache.get(source_id)
        if not config:
            return []
        adapter = self._get_adapter(config.source_type)
        return adapter.get_schema(config)

    def search(self, source_id: str, query: str, top_k: int = 5) -> list[dict]:
        self._ensure_loaded()
        config = self._cache.get(source_id)
        if not config or config.status != "connected":
            return []
        adapter = self._get_adapter(config.source_type)
        return adapter.search(config, query, top_k)

    def sample(self, source_id: str, count: int = 20) -> list[dict]:
        self._ensure_loaded()
        config = self._cache.get(source_id)
        if not config:
            return []
        adapter = self._get_adapter(config.source_type)
        return adapter.sample(config, count)

    def ingest(self, source_id: str) -> dict:
        """Pull all data from source and feed into ingestion pipeline."""
        self._ensure_loaded()
        config = self._cache.get(source_id)
        if not config:
            return {"success": False, "total_ingested": 0, "message": "Data source not found"}

        adapter = self._get_adapter(config.source_type)
        total = 0
        try:
            from src.api.modules.ingestion.service import ingestion_service

            for batch in adapter.fetch_all(config):
                # Transform to ingestion format
                ingestion_data = []
                for doc in batch:
                    ingestion_data.append({
                        "id": doc.get("id", str(uuid.uuid4())[:8]),
                        "type": doc.get("type", "external"),
                        "text": doc.get("text", ""),
                        "metadata": {
                            **doc.get("metadata", {}),
                            "source": f"data_source:{config.name}",
                            "data_source_id": config.id,
                        },
                    })
                result = ingestion_service.load_json_data(
                    ingestion_data,
                    filename=f"datasource_{config.name}",
                )
                total += result.total_loaded

            config.last_sync = datetime.now(timezone.utc).isoformat()
            config.doc_count = total
            self._cache[source_id] = config
            self._persist(config)

            return {"success": True, "total_ingested": total, "message": f"Ingested {total} documents from {config.name}"}
        except Exception as e:
            logger.error(f"Ingest from {config.name} failed: {e}")
            return {"success": False, "total_ingested": total, "message": str(e)}

    def _persist(self, config: DataSourceConfig):
        try:
            from src.api.storage.sql_service import sql_service
            sql_service.save_data_source(config.model_dump())
        except Exception as e:
            logger.warning(f"Failed to persist data source config: {e}")

    @staticmethod
    def get_supported_types() -> list[dict]:
        return [
            {
                "source_type": "fabric",
                "label": "Microsoft Fabric",
                "description": "Connect to a Fabric Lakehouse or Warehouse via SQL endpoint",
                "requires_connection_string": False,
                "requires_endpoint": True,
                "supports_live_query": True,
            },
            {
                "source_type": "sql",
                "label": "SQL Database",
                "description": "Connect to SQL Server, PostgreSQL, MySQL, or any SQL database via connection string",
                "requires_connection_string": True,
                "requires_endpoint": False,
                "supports_live_query": True,
            },
            {
                "source_type": "synapse",
                "label": "Azure Synapse Analytics",
                "description": "Connect to Synapse serverless or dedicated SQL pools",
                "requires_connection_string": False,
                "requires_endpoint": True,
                "supports_live_query": True,
            },
            {
                "source_type": "odbc",
                "label": "ODBC / JDBC",
                "description": "Connect to any database with an ODBC driver using a connection string",
                "requires_connection_string": True,
                "requires_endpoint": False,
                "supports_live_query": True,
            },
            {
                "source_type": "azure_search",
                "label": "Azure AI Search",
                "description": "Connect to an existing Azure AI Search index",
                "requires_connection_string": False,
                "requires_endpoint": True,
                "supports_live_query": True,
            },
        ]


data_source_registry = DataSourceRegistry()
