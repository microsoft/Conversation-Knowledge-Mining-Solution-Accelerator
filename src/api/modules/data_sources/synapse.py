"""Azure Synapse Analytics data source adapter."""

import logging
import struct
import uuid
from typing import Iterator, Optional

from src.api.modules.data_sources.base import (
    BaseExternalDataSource,
    ColumnInfo,
    DataSourceConfig,
    FieldMapping,
)

logger = logging.getLogger(__name__)


class SynapseDataSource(BaseExternalDataSource):
    """Adapter for Azure Synapse Analytics SQL endpoint (serverless or dedicated)."""

    def _get_connection(self, config: DataSourceConfig):
        import pyodbc
        from azure.identity import DefaultAzureCredential

        if config.connection_string:
            return pyodbc.connect(config.connection_string, timeout=30)

        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/.default")
        token_bytes = token.token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

        conn_str = (
            f"Driver={{ODBC Driver 18 for SQL Server}};"
            f"Server={config.endpoint};"
            f"Database={config.database};"
            f"Encrypt=yes;TrustServerCertificate=no;"
        )
        return pyodbc.connect(conn_str, attrs_before={1256: token_struct})

    def connect(self, config: DataSourceConfig) -> bool:
        try:
            conn = self._get_connection(config)
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Synapse connect failed: {e}")
            return False

    def disconnect(self) -> None:
        pass

    def test_connection(self, config: DataSourceConfig) -> dict:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = config.table_or_query
            if table.strip().upper().startswith("SELECT"):
                cursor.execute(f"SELECT COUNT(*) FROM ({table}) AS q")
            else:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
            count = cursor.fetchone()[0]
            conn.close()
            return {"success": True, "row_count": count, "message": f"Connected to Synapse. {count} rows found."}
        except Exception as e:
            return {"success": False, "row_count": 0, "message": str(e)}

    def get_schema(self, config: DataSourceConfig) -> list[ColumnInfo]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = config.table_or_query
            if table.strip().upper().startswith("SELECT"):
                cursor.execute(f"SELECT TOP 0 * FROM ({table}) AS q")
            else:
                cursor.execute(f"SELECT TOP 0 * FROM [{table}]")
            columns = [
                ColumnInfo(
                    name=desc[0],
                    data_type=str(desc[1].__name__) if hasattr(desc[1], '__name__') else str(desc[1]),
                    nullable=bool(desc[6]) if len(desc) > 6 else True,
                )
                for desc in cursor.description
            ]
            conn.close()
            return columns
        except Exception as e:
            logger.warning(f"Failed to get Synapse schema: {e}")
            return []

    def search(self, config: DataSourceConfig, query: str, top_k: int = 5,
               filters: Optional[dict] = None) -> list[dict]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            mapping = config.field_mapping
            table = config.table_or_query

            select_cols = [mapping.id_field, mapping.text_field]
            if mapping.title_field:
                select_cols.append(mapping.title_field)
            if mapping.type_field:
                select_cols.append(mapping.type_field)
            for src_col in mapping.metadata_fields.values():
                select_cols.append(src_col)
            select_str = ", ".join(f"[{c}]" for c in select_cols)

            if table.strip().upper().startswith("SELECT"):
                sql = f"SELECT TOP {top_k} {select_str} FROM ({table}) AS q WHERE [{mapping.text_field}] LIKE ?"
            else:
                sql = f"SELECT TOP {top_k} {select_str} FROM [{table}] WHERE [{mapping.text_field}] LIKE ?"

            cursor.execute(sql, (f"%{query}%",))
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            conn.close()

            docs = []
            for row in rows:
                row_dict = dict(zip(col_names, row))
                doc = self._apply_field_mapping(row_dict, mapping)
                if not doc["id"]:
                    doc["id"] = str(uuid.uuid4())[:8]
                doc["score"] = 1.0
                docs.append(doc)
            return docs
        except Exception as e:
            logger.warning(f"Synapse search failed: {e}")
            return []

    def sample(self, config: DataSourceConfig, count: int = 20) -> list[dict]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = config.table_or_query
            if table.strip().upper().startswith("SELECT"):
                cursor.execute(f"SELECT TOP {count} * FROM ({table}) AS q")
            else:
                cursor.execute(f"SELECT TOP {count} * FROM [{table}]")
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            conn.close()

            docs = []
            for row in rows:
                row_dict = dict(zip(col_names, row))
                doc = self._apply_field_mapping(row_dict, config.field_mapping)
                if not doc["id"]:
                    doc["id"] = str(uuid.uuid4())[:8]
                docs.append(doc)
            return docs
        except Exception as e:
            logger.warning(f"Synapse sample failed: {e}")
            return []

    def fetch_all(self, config: DataSourceConfig, batch_size: int = 1000) -> Iterator[list[dict]]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = config.table_or_query
            if table.strip().upper().startswith("SELECT"):
                cursor.execute(f"SELECT * FROM ({table}) AS q")
            else:
                cursor.execute(f"SELECT * FROM [{table}]")
            col_names = [desc[0] for desc in cursor.description]

            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                batch = []
                for row in rows:
                    row_dict = dict(zip(col_names, row))
                    doc = self._apply_field_mapping(row_dict, config.field_mapping)
                    if not doc["id"]:
                        doc["id"] = str(uuid.uuid4())[:8]
                    batch.append(doc)
                yield batch

            conn.close()
        except Exception as e:
            logger.warning(f"Synapse fetch_all failed: {e}")
