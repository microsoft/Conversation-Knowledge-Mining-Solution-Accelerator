"""Microsoft Fabric data source adapter — uses SQL endpoint with Entra ID auth."""

import logging
import struct
import uuid
from typing import Iterator, Optional

from src.api.modules.data_sources.base import (
    BaseExternalDataSource,
    ColumnInfo,
    DataSourceConfig,
    validate_table_name,
)

logger = logging.getLogger(__name__)


class FabricDataSource(BaseExternalDataSource):
    """Adapter for Microsoft Fabric Lakehouse/Warehouse SQL endpoint."""

    def _get_connection(self, config: DataSourceConfig):
        import pyodbc
        from azure.identity import DefaultAzureCredential

        if config.connection_string:
            return pyodbc.connect(config.connection_string, timeout=30)

        # Entra ID auth for Fabric SQL endpoint
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
            logger.warning(f"Fabric connect failed: {e}")
            return False

    def disconnect(self) -> None:
        pass

    def test_connection(self, config: DataSourceConfig) -> dict:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = validate_table_name(config.table_or_query)
            
            # Test 1: Check table exists and count rows
            cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
            count = cursor.fetchone()[0]
            
            # Test 2: Check if text field is accessible
            text_field = config.field_mapping.text_field
            cursor.execute(f"SELECT COUNT(*) FROM [{table}] WHERE [{text_field}] IS NOT NULL")
            non_null_count = cursor.fetchone()[0]
            
            conn.close()
            
            msg = f"Connected to Fabric. Table has {count} rows, {non_null_count} with non-NULL text field."
            logger.info(f"Fabric connection test passed: {msg}")
            return {"success": True, "row_count": count, "message": msg}
        except Exception as e:
            error_msg = f"Connection failed: {str(e)}"
            logger.warning(f"Fabric connection test failed: {error_msg}")
            return {"success": False, "row_count": 0, "message": error_msg}

    def get_schema(self, config: DataSourceConfig) -> list[ColumnInfo]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = validate_table_name(config.table_or_query)
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
            logger.warning(f"Failed to get Fabric schema: {e}")
            return []

    def search(self, config: DataSourceConfig, query: str, top_k: int = 5,
               filters: Optional[dict] = None) -> list[dict]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            mapping = config.field_mapping
            table = validate_table_name(config.table_or_query)

            select_cols = [mapping.id_field, mapping.text_field]
            if mapping.title_field:
                select_cols.append(mapping.title_field)
            if mapping.type_field:
                select_cols.append(mapping.type_field)
            for src_col in mapping.metadata_fields.values():
                select_cols.append(src_col)
            select_str = ", ".join(f"[{c}]" for c in select_cols)

            # Use LOWER() for case-insensitive search and filter NULL values
            text_field = f"[{mapping.text_field}]"
            sql = f"""
            SELECT TOP {top_k} {select_str} 
            FROM [{table}] 
            WHERE {text_field} IS NOT NULL 
              AND LOWER(CAST({text_field} AS NVARCHAR(MAX))) LIKE ?
            """

            cursor.execute(sql, (f"%{query.lower()}%",))
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
            
            logger.debug(f"Fabric search for '{query}' returned {len(docs)} results")
            return docs
        except Exception as e:
            logger.warning(f"Fabric search failed: {e}")
            return []

    def sample(self, config: DataSourceConfig, count: int = 20) -> list[dict]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = validate_table_name(config.table_or_query)
            
            # Sample from non-NULL text field rows to avoid empty documents
            text_field = f"[{config.field_mapping.text_field}]"
            sql = f"""
            SELECT TOP {count} * FROM [{table}] 
            WHERE {text_field} IS NOT NULL 
            ORDER BY NEWID()
            """
            cursor.execute(sql)
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
            
            logger.debug(f"Fabric sample returned {len(docs)} documents")
            return docs
        except Exception as e:
            logger.warning(f"Fabric sample failed: {e}")
            return []

    def fetch_all(self, config: DataSourceConfig, batch_size: int = 1000) -> Iterator[list[dict]]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = validate_table_name(config.table_or_query)
            
            # Only fetch rows with non-NULL text field
            text_field = f"[{config.field_mapping.text_field}]"
            sql = f"SELECT * FROM [{table}] WHERE {text_field} IS NOT NULL"
            cursor.execute(sql)
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
            logger.debug(f"Fabric fetch_all completed successfully")
        except Exception as e:
            logger.warning(f"Fabric fetch_all failed: {e}")
