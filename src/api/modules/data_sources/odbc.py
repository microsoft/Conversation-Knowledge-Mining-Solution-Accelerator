"""Generic ODBC/JDBC data source adapter."""

import logging
import uuid
from typing import Iterator, Optional

from src.api.modules.data_sources.base import (
    BaseExternalDataSource,
    ColumnInfo,
    DataSourceConfig,
    FieldMapping,
)

logger = logging.getLogger(__name__)


class OdbcDataSource(BaseExternalDataSource):
    """Generic ODBC adapter — works with any database that has an ODBC driver."""

    def _get_connection(self, config: DataSourceConfig):
        import pyodbc
        return pyodbc.connect(config.connection_string, timeout=30)

    def connect(self, config: DataSourceConfig) -> bool:
        try:
            conn = self._get_connection(config)
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"ODBC connect failed: {e}")
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
            return {"success": True, "row_count": count, "message": f"Connected via ODBC. {count} rows found."}
        except Exception as e:
            return {"success": False, "row_count": 0, "message": str(e)}

    def get_schema(self, config: DataSourceConfig) -> list[ColumnInfo]:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = config.table_or_query
            if table.strip().upper().startswith("SELECT"):
                cursor.execute(f"SELECT TOP 1 * FROM ({table}) AS q WHERE 1=0")
            else:
                cursor.execute(f"SELECT TOP 1 * FROM [{table}] WHERE 1=0")
            columns = [
                ColumnInfo(
                    name=desc[0],
                    data_type=str(desc[1].__name__) if hasattr(desc[1], '__name__') else str(desc[1]),
                    nullable=bool(desc[6]) if len(desc) > 6 else True,
                )
                for desc in cursor.description
            ] if cursor.description else []
            conn.close()
            return columns
        except Exception as e:
            logger.warning(f"Failed to get ODBC schema: {e}")
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
            logger.warning(f"ODBC search failed: {e}")
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
            logger.warning(f"ODBC sample failed: {e}")
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
            logger.warning(f"ODBC fetch_all failed: {e}")
