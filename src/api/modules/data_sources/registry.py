"""Data source registry — manages adapters, CRUD, and persistence to SQL.

Key extension points:
- _load_adapters(): register new data source types here
- _auto_detect_mapping(): customize column name detection heuristics
- get_supported_types(): add UI metadata for new source types
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.api.modules.data_sources.base import (
    BaseExternalDataSource,
    DataSourceConfig,
    DataSourceType,
    QueryMode,
    ColumnInfo,
    FieldMapping,
)

logger = logging.getLogger(__name__)

# Adapter map — type → class
_ADAPTER_CLASSES: dict[DataSourceType, type[BaseExternalDataSource]] = {}

_DEFAULT_ID_FIELDS = {"", "id"}
_DEFAULT_TEXT_FIELDS = {"", "text"}


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
        self._adapter_instances: dict[DataSourceType, BaseExternalDataSource] = {}
        self._loaded = False

    def _get_adapter(self, source_type: DataSourceType) -> BaseExternalDataSource:
        _load_adapters()
        cached = self._adapter_instances.get(source_type)
        if cached:
            return cached
        cls = _ADAPTER_CLASSES.get(source_type)
        if not cls:
            raise ValueError(f"Unsupported data source type: {source_type}")
        adapter = cls()
        self._adapter_instances[source_type] = adapter
        return adapter

    def _normalize_mapping_for_schema(
        self,
        columns: list[ColumnInfo],
        mapping: Optional[FieldMapping],
        source_type: Optional[DataSourceType] = None,
    ) -> FieldMapping:
        """Resolve field mapping against actual schema to avoid hardcoded assumptions."""
        if not columns:
            return mapping or FieldMapping()

        normalized = FieldMapping(**((mapping or FieldMapping()).model_dump()))
        if source_type == DataSourceType.FABRIC:
            suggested = self._auto_detect_mapping_schema_only(columns)
        else:
            suggested = self._auto_detect_mapping(columns)
        column_names = {c.name for c in columns}

        def _pick(current: str, suggested_value: str, default_values: set[str]) -> str:
            c = (current or "").strip()
            s = (suggested_value or "").strip()
            if c and c in column_names and c.lower() not in default_values:
                return c
            if c and c in column_names and c.lower() in default_values and not s:
                return c
            if s and s in column_names:
                return s
            if c and c in column_names:
                return c
            return ""

        normalized.id_field = _pick(
            normalized.id_field,
            suggested.get("id_field", ""),
            _DEFAULT_ID_FIELDS,
        ) or (columns[0].name if columns else "id")

        normalized.text_field = _pick(
            normalized.text_field,
            suggested.get("text_field", ""),
            _DEFAULT_TEXT_FIELDS,
        )
        if not normalized.text_field:
            for col in columns:
                dtype = (col.data_type or "").lower()
                if col.name != normalized.id_field and any(t in dtype for t in ["str", "char", "text", "nvarchar", "varchar"]):
                    normalized.text_field = col.name
                    break
        if not normalized.text_field and len(columns) > 1:
            normalized.text_field = columns[1].name
        if not normalized.text_field:
            normalized.text_field = normalized.id_field

        normalized.title_field = _pick(
            normalized.title_field,
            suggested.get("title_field", ""),
            {""},
        )
        normalized.type_field = _pick(
            normalized.type_field,
            suggested.get("type_field", ""),
            {""},
        )
        normalized.timestamp_field = _pick(
            normalized.timestamp_field,
            suggested.get("timestamp_field", ""),
            {""},
        )

        cleaned_meta: dict[str, str] = {}
        for accel_key, src_col in (normalized.metadata_fields or {}).items():
            if src_col in column_names and src_col not in {
                normalized.id_field,
                normalized.text_field,
                normalized.title_field,
                normalized.type_field,
                normalized.timestamp_field,
            }:
                cleaned_meta[accel_key] = src_col
        normalized.metadata_fields = cleaned_meta
        return normalized

    def _resolve_mapping(self, config: DataSourceConfig) -> DataSourceConfig:
        """Fetch schema and normalize mapping before querying/ingesting."""
        try:
            adapter = self._get_adapter(config.source_type)
            columns = adapter.get_schema(config)
        except Exception as e:
            logger.warning(f"Could not resolve field mapping for source '{config.name}': {e}")
            return config

        if not columns:
            return config

        normalized = self._normalize_mapping_for_schema(columns, config.field_mapping, config.source_type)
        if normalized.model_dump() != config.field_mapping.model_dump():
            config.field_mapping = normalized
        return config

    def _resolve_mapping_for_runtime(self, config: DataSourceConfig) -> DataSourceConfig:
        """Resolve mapping only for runtime-sensitive adapters to avoid hot-path overhead."""
        if config.source_type == DataSourceType.FABRIC:
            return self._resolve_mapping(config)
        return config

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

        # Normalize mapping from live schema before validation/persist.
        config = self._resolve_mapping(config)

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
                if key == "field_mapping" and isinstance(value, dict):
                    try:
                        value = FieldMapping(**value)
                    except Exception as e:
                        logger.warning(f"Invalid field_mapping update for source '{source_id}': {e}")
                        continue
                setattr(config, key, value)

        # Re-resolve mapping after config or mapping updates.
        if {"field_mapping", "table_or_query", "endpoint", "database", "connection_string"} & set(updates.keys()):
            config = self._resolve_mapping(config)

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
        except Exception as e:
            logger.warning(f"Failed to delete data source '{source_id}' from SQL: {e}")
        return True

    def clear_all_external_sources(self) -> int:
        """Delete all registered data sources from SQL and reset the in-memory cache.
        Returns the number of sources that were removed."""
        count = len(self._cache)
        self._cache = {}
        self._loaded = False
        try:
            from src.api.storage.sql_service import sql_service
            if sql_service.available:
                conn = sql_service._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM external_data_sources")
                conn.commit()
                conn.close()
        except Exception as e:
            logger.warning(f"Failed to clear external_data_sources table: {e}")
        return count

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
            if c.source_type != DataSourceType.NATIVE
            and c.status == "connected" and c.query_mode in (QueryMode.LIVE, QueryMode.BOTH)
        ]

    def register_scenario(self, name: str, use_case: str = "", doc_count: int = 0) -> DataSourceConfig:
        """Register a seeded scenario as an inert 'native' data source so its
        use-case name surfaces at runtime without a frontend rebuild."""
        self._ensure_loaded()
        config = DataSourceConfig(
            name=name,
            source_type=DataSourceType.NATIVE,
            use_case=use_case or name,
            status="seeded",
            query_mode=QueryMode.INGEST,
            doc_count=doc_count,
        )
        config.id = str(uuid.uuid4())[:12]
        self._cache[config.id] = config
        self._persist(config)
        return config

    def test_connection(self, config: DataSourceConfig) -> dict:
        adapter = self._get_adapter(config.source_type)
        # Use normalized mapping during connectivity checks.
        config = self._resolve_mapping(config)
        result = adapter.test_connection(config)
        # Also get schema for the response
        columns = []
        if result["success"]:
            try:
                columns = adapter.get_schema(config)
            except Exception as e:
                logger.warning(f"Failed to get schema for data source: {e}")
        result["columns"] = [c.model_dump() for c in columns]
        # Auto-detect field mapping from column names
        if columns:
            if config.source_type == DataSourceType.FABRIC:
                result["suggested_mapping"] = self._auto_detect_mapping_schema_only(columns)
            else:
                result["suggested_mapping"] = self._auto_detect_mapping(columns)
        return result

    @staticmethod
    def _auto_detect_mapping_schema_only(columns: list[ColumnInfo]) -> dict:
        """Schema-first mapping detection without column-name keyword assumptions."""
        if not columns:
            return {
                "id_field": "id",
                "text_field": "text",
                "title_field": "",
                "type_field": "",
                "timestamp_field": "",
                "metadata_fields": {},
            }

        def _is_textual(c: ColumnInfo) -> bool:
            dt = (c.data_type or "").lower()
            return any(t in dt for t in ["str", "char", "text", "nvarchar", "varchar"])

        def _is_temporal(c: ColumnInfo) -> bool:
            dt = (c.data_type or "").lower()
            return "date" in dt or "time" in dt

        id_field = ""
        for c in columns:
            if not _is_textual(c):
                id_field = c.name
                break
        if not id_field:
            id_field = columns[0].name

        text_field = ""
        for c in columns:
            if c.name != id_field and _is_textual(c):
                text_field = c.name
                break
        if not text_field:
            text_field = columns[1].name if len(columns) > 1 else id_field

        ts_field = ""
        for c in columns:
            if _is_temporal(c):
                ts_field = c.name
                break

        return {
            "id_field": id_field or "id",
            "text_field": text_field or "text",
            "title_field": "",
            "type_field": "",
            "timestamp_field": ts_field,
            "metadata_fields": {},
        }

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
        config = self._resolve_mapping_for_runtime(config)
        adapter = self._get_adapter(config.source_type)
        return adapter.search(config, query, top_k)

    def sample(self, source_id: str, count: int = 20) -> list[dict]:
        self._ensure_loaded()
        config = self._cache.get(source_id)
        if not config:
            return []
        config = self._resolve_mapping_for_runtime(config)
        adapter = self._get_adapter(config.source_type)
        return adapter.sample(config, count)

    def ingest(self, source_id: str) -> dict:
        """Pull all data from source and feed into ingestion pipeline."""
        self._ensure_loaded()
        config = self._cache.get(source_id)
        if not config:
            return {"success": False, "total_ingested": 0, "message": "Data source not found"}

        config = self._resolve_mapping_for_runtime(config)

        adapter = self._get_adapter(config.source_type)
        total = 0
        ingested_docs: list[dict] = []
        try:
            from src.api.modules.ingestion.service import ingestion_service

            for batch in adapter.fetch_all(config):
                # Transform to ingestion format
                ingestion_data = []
                for doc in batch:
                    normalized_doc = {
                        "id": doc.get("id", str(uuid.uuid4())[:8]),
                        "type": doc.get("type", "external"),
                        "text": doc.get("text", ""),
                        "metadata": {
                            **doc.get("metadata", {}),
                            "source": f"data_source:{config.name}",
                            "data_source_id": config.id,
                        },
                    }
                    if doc.get("summary"):
                        normalized_doc["summary"] = doc["summary"]
                    if doc.get("key_phrases"):
                        normalized_doc["key_phrases"] = doc["key_phrases"]
                    if doc.get("topics"):
                        normalized_doc["topics"] = doc["topics"]
                    ingestion_data.append(normalized_doc)
                result = ingestion_service.load_json_data(
                    ingestion_data,
                    filename=f"datasource_{config.name}.json",
                    source="external_ingest",
                )
                total += result.total_loaded
                ingested_docs.extend(ingestion_data)

            if ingested_docs:
                ingestion_service.finalize_ingestion(ingested_docs, f"datasource_{config.name}.json")

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
