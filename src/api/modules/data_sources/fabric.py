"""Microsoft Fabric data source adapter — uses SQL endpoint with Entra ID auth."""

import logging
import struct
import uuid
from typing import Any, Iterator, Optional

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

    @staticmethod
    def _resolve_field(actual_columns: list[str], preferred: str) -> str:
        """Pick preferred field if it exists (case-insensitive)."""
        lookup = {c.lower(): c for c in actual_columns}
        c = (preferred or "").strip().lower()
        if c and c in lookup:
            return lookup[c]
        return ""

    @staticmethod
    def _is_textual_type(data_type: str) -> bool:
        dt = (data_type or "").lower()
        return any(t in dt for t in ["str", "char", "text", "nvarchar", "varchar"])

    @staticmethod
    def _is_temporal_type(data_type: str) -> bool:
        dt = (data_type or "").lower()
        return "date" in dt or "time" in dt

    def _infer_runtime_mapping(self, cursor, table: str, mapping):
        """Infer robust runtime mapping from schema and sampled values, without name-based rules."""
        cursor.execute(f"SELECT TOP 0 * FROM [{table}]")
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        if not columns:
            return mapping, []

        dtype_by_col: dict[str, str] = {}
        try:
            schema_rows = cursor.columns(table=table).fetchall()
            for r in schema_rows:
                col_name = getattr(r, "column_name", None)
                type_name = getattr(r, "type_name", "") or ""
                if col_name:
                    dtype_by_col[col_name] = str(type_name)
        except Exception:
            # Best-effort only; if unavailable, continue with empty type hints.
            dtype_by_col = {}

        cursor.execute(f"SELECT TOP 200 * FROM [{table}]")
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]

        stats: dict[str, dict[str, Any]] = {
            c: {
                "non_null": 0,
                "str_non_empty": 0,
                "str_total_len": 0,
                "distinct": set(),
                "dtype": dtype_by_col.get(c, ""),
            }
            for c in col_names
        }

        for row in rows:
            row_dict = dict(zip(col_names, row))
            for c, v in row_dict.items():
                if v is None:
                    continue
                s = stats[c]
                s["non_null"] += 1
                sv = str(v)
                if sv.strip():
                    s["distinct"].add(sv[:256])
                if isinstance(v, str) and v.strip():
                    s["str_non_empty"] += 1
                    s["str_total_len"] += len(v)

        for c in col_names:
            s = stats[c]
            non_null = s["non_null"] or 0
            s["avg_len"] = (s["str_total_len"] / s["str_non_empty"]) if s["str_non_empty"] else 0.0
            s["distinct_ratio"] = (len(s["distinct"]) / non_null) if non_null else 0.0

        def _best_text_column() -> str:
            explicit = self._resolve_field(col_names, mapping.text_field)
            if explicit:
                return explicit

            candidates = []
            for c in col_names:
                s = stats[c]
                if s["str_non_empty"] <= 0 and not self._is_textual_type(s["dtype"]):
                    continue
                candidates.append((s["avg_len"], s["str_non_empty"], c))
            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][2]
            return col_names[1] if len(col_names) > 1 else col_names[0]

        def _best_id_column(text_col: str) -> str:
            explicit = self._resolve_field(col_names, mapping.id_field)
            if explicit:
                return explicit

            candidates = []
            for c in col_names:
                if c == text_col:
                    continue
                s = stats[c]
                avg_len = float(s["avg_len"] or 0.0)
                compactness = 1.0 / (1.0 + avg_len)
                score = (s["distinct_ratio"] * 0.7) + (compactness * 0.3)
                if self._is_temporal_type(s["dtype"]):
                    score -= 0.1
                candidates.append((score, c))
            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][1]
            return col_names[0]

        text_col = _best_text_column()
        id_col = _best_id_column(text_col)

        title_col = self._resolve_field(col_names, mapping.title_field)
        if not title_col:
            title_candidates = []
            for c in col_names:
                if c in {id_col, text_col}:
                    continue
                s = stats[c]
                if s["str_non_empty"] <= 0:
                    continue
                # Prefer medium-length descriptive text over long body text.
                if 5 <= s["avg_len"] <= 120:
                    title_candidates.append((s["str_non_empty"], -abs(40 - s["avg_len"]), c))
            if title_candidates:
                title_candidates.sort(reverse=True)
                title_col = title_candidates[0][2]

        type_col = self._resolve_field(col_names, mapping.type_field)
        if not type_col:
            type_candidates = []
            for c in col_names:
                if c in {id_col, text_col, title_col}:
                    continue
                s = stats[c]
                card = len(s["distinct"])
                if s["non_null"] and 2 <= card <= 25:
                    type_candidates.append((s["non_null"], -card, c))
            if type_candidates:
                type_candidates.sort(reverse=True)
                type_col = type_candidates[0][2]

        ts_col = self._resolve_field(col_names, mapping.timestamp_field)
        if not ts_col:
            for c in col_names:
                if self._is_temporal_type(stats[c]["dtype"]):
                    ts_col = c
                    break

        valid_cols = set(col_names)
        metadata_fields = {
            k: v for k, v in (mapping.metadata_fields or {}).items()
            if v in valid_cols and v not in {id_col, text_col, title_col, type_col, ts_col}
        }

        runtime_mapping = mapping.model_copy(update={
            "id_field": id_col,
            "text_field": text_col,
            "title_field": title_col or "",
            "type_field": type_col or "",
            "timestamp_field": ts_col or "",
            "metadata_fields": metadata_fields,
        })
        return runtime_mapping, col_names

    def test_connection(self, config: DataSourceConfig) -> dict:
        try:
            conn = self._get_connection(config)
            cursor = conn.cursor()
            table = validate_table_name(config.table_or_query)

            # Test 1: Check table exists and count rows
            cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
            count = cursor.fetchone()[0]

            runtime_mapping, _ = self._infer_runtime_mapping(cursor, table, config.field_mapping)
            text_field = runtime_mapping.text_field

            if not text_field:
                conn.close()
                return {
                    "success": False,
                    "row_count": 0,
                    "message": "No suitable text/content column found. Update field mapping.",
                }

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
            table = validate_table_name(config.table_or_query)

            runtime_mapping, _ = self._infer_runtime_mapping(cursor, table, config.field_mapping)

            select_cols = [runtime_mapping.id_field, runtime_mapping.text_field]
            if runtime_mapping.title_field:
                select_cols.append(runtime_mapping.title_field)
            if runtime_mapping.type_field:
                select_cols.append(runtime_mapping.type_field)
            for src_col in runtime_mapping.metadata_fields.values():
                select_cols.append(src_col)
            select_str = ", ".join(f"[{c}]" for c in select_cols)

            # Use LOWER() for case-insensitive search and filter NULL values
            text_field = f"[{runtime_mapping.text_field}]"
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
                doc = self._apply_field_mapping(row_dict, runtime_mapping)
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

            runtime_mapping, _ = self._infer_runtime_mapping(cursor, table, config.field_mapping)
            text_col = runtime_mapping.text_field
            if not text_col:
                conn.close()
                return []

            # Sample from non-NULL text field rows to avoid empty documents
            text_field = f"[{text_col}]"
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
                doc = self._apply_field_mapping(row_dict, runtime_mapping)
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

            runtime_mapping, _ = self._infer_runtime_mapping(cursor, table, config.field_mapping)
            text_col = runtime_mapping.text_field
            if not text_col:
                conn.close()
                logger.warning("Fabric fetch_all skipped: no usable text column found")
                return

            # Only fetch rows with non-NULL text field
            text_field = f"[{text_col}]"
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
                    doc = self._apply_field_mapping(row_dict, runtime_mapping)
                    if not doc["id"]:
                        doc["id"] = str(uuid.uuid4())[:8]
                    batch.append(doc)
                yield batch

            conn.close()
            logger.debug("Fabric fetch_all completed successfully")
        except Exception as e:
            logger.warning(f"Fabric fetch_all failed: {e}")
