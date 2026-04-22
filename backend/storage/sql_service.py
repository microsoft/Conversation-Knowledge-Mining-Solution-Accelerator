"""Azure SQL service for persisting documents, uploaded files, filter schemas, and enrichment cache.

Uses pyodbc with Azure AD token-based auth (passwordless).
Tables are auto-created on first use.
"""

import json
import logging
from typing import Optional

from backend.config import get_settings

logger = logging.getLogger(__name__)


class AzureSqlService:
    """Manages Azure SQL persistence for the knowledge mining platform."""

    def __init__(self):
        self._conn_str: Optional[str] = None
        self._initialized = False
        self._init_failed = False

    def _ensure_init(self):
        if self._initialized or self._init_failed:
            return
        settings = get_settings()
        if not settings.azure_sql_server:
            logger.info("Azure SQL not configured — SQL persistence disabled")
            self._init_failed = True
            return

        try:
            import pyodbc
            from azure.identity import DefaultAzureCredential
            import struct

            credential = DefaultAzureCredential()
            token = credential.get_token("https://database.windows.net/.default")
            token_bytes = token.token.encode("utf-16-le")
            token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

            server = settings.azure_sql_server
            database = settings.azure_sql_database
            self._conn_str = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server={server};"
                f"Database={database};"
                f"Encrypt=yes;TrustServerCertificate=no;"
            )
            self._token_struct = token_struct

            # Create tables
            self._create_tables()
            self._initialized = True
            logger.info(f"Azure SQL initialized: {server}/{database}")
        except Exception as e:
            self._init_failed = True
            logger.warning(f"Azure SQL init failed (will not retry): {e}")

    def _get_connection(self):
        import pyodbc
        conn = pyodbc.connect(self._conn_str, attrs_before={1256: self._token_struct})
        return conn

    def _refresh_token(self):
        """Refresh the AAD token for long-running connections."""
        import struct
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/.default")
        token_bytes = token.token.encode("utf-16-le")
        self._token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    def _create_tables(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'documents')
            CREATE TABLE documents (
                id NVARCHAR(255) PRIMARY KEY,
                doc_type NVARCHAR(50),
                text_content NVARCHAR(MAX),
                summary NVARCHAR(MAX),
                entities NVARCHAR(MAX),
                key_phrases NVARCHAR(MAX),
                topics NVARCHAR(MAX),
                metadata NVARCHAR(MAX),
                source_file NVARCHAR(500),
                created_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'uploaded_files')
            CREATE TABLE uploaded_files (
                id NVARCHAR(255) PRIMARY KEY,
                filename NVARCHAR(500),
                doc_count INT,
                summary NVARCHAR(MAX),
                keywords NVARCHAR(MAX),
                filter_values NVARCHAR(MAX),
                uploaded_at NVARCHAR(50)
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'filter_schemas')
            CREATE TABLE filter_schemas (
                id NVARCHAR(50) PRIMARY KEY,
                domain NVARCHAR(200),
                dimensions NVARCHAR(MAX)
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'enrichment_cache')
            CREATE TABLE enrichment_cache (
                doc_hash NVARCHAR(50) PRIMARY KEY,
                filename NVARCHAR(500),
                enrichment NVARCHAR(MAX),
                cached_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'chat_sessions')
            CREATE TABLE chat_sessions (
                id NVARCHAR(255) PRIMARY KEY,
                user_id NVARCHAR(255) NOT NULL,
                title NVARCHAR(500),
                message_count INT DEFAULT 0,
                created_at DATETIME2 DEFAULT GETUTCDATE(),
                updated_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'chat_messages')
            CREATE TABLE chat_messages (
                id NVARCHAR(255) PRIMARY KEY,
                session_id NVARCHAR(255) NOT NULL,
                role NVARCHAR(20) NOT NULL,
                content NVARCHAR(MAX),
                sources NVARCHAR(MAX),
                timestamp DATETIME2 DEFAULT GETUTCDATE(),
                sort_order INT DEFAULT 0
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'insights_cache')
            CREATE TABLE insights_cache (
                id NVARCHAR(255) PRIMARY KEY,
                insights NVARCHAR(MAX),
                generated_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """)
        conn.commit()
        conn.close()

    @property
    def available(self) -> bool:
        self._ensure_init()
        return self._initialized

    # ══════════════════════════════════════════════
    # Documents
    # ══════════════════════════════════════════════

    def save_document(self, doc_id: str, doc_data: dict) -> bool:
        if not self.available:
            return False
        try:
            text = doc_data.get("text", "")
            if isinstance(text, list):
                text = "\n".join(f"{s.get('speaker','')}: {s.get('text','')}" for s in text)

            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                MERGE documents AS target
                USING (SELECT ? AS id) AS source ON target.id = source.id
                WHEN MATCHED THEN UPDATE SET
                    doc_type=?, text_content=?, summary=?, entities=?,
                    key_phrases=?, topics=?, metadata=?, source_file=?
                WHEN NOT MATCHED THEN INSERT
                    (id, doc_type, text_content, summary, entities, key_phrases, topics, metadata, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
                doc_id,
                doc_data.get("type", ""), text, doc_data.get("summary", ""),
                json.dumps(doc_data.get("entities", [])),
                json.dumps(doc_data.get("key_phrases", [])),
                json.dumps(doc_data.get("topics", [])),
                json.dumps(doc_data.get("metadata", {})),
                doc_data.get("metadata", {}).get("source_file", ""),
                # INSERT values
                doc_id,
                doc_data.get("type", ""), text, doc_data.get("summary", ""),
                json.dumps(doc_data.get("entities", [])),
                json.dumps(doc_data.get("key_phrases", [])),
                json.dumps(doc_data.get("topics", [])),
                json.dumps(doc_data.get("metadata", {})),
                doc_data.get("metadata", {}).get("source_file", ""),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to save document {doc_id}: {e}")
            self._refresh_token()
            return False

    def load_all_documents(self) -> list[dict]:
        if not self.available:
            return []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, doc_type, text_content, summary, entities, key_phrases, topics, metadata FROM documents")
            rows = cursor.fetchall()
            conn.close()
            results = []
            for row in rows:
                results.append({
                    "id": row[0],
                    "type": row[1],
                    "text": row[2],
                    "summary": row[3],
                    "entities": json.loads(row[4]) if row[4] else [],
                    "key_phrases": json.loads(row[5]) if row[5] else [],
                    "topics": json.loads(row[6]) if row[6] else [],
                    "metadata": json.loads(row[7]) if row[7] else {},
                })
            return results
        except Exception as e:
            logger.warning(f"Failed to load documents: {e}")
            self._refresh_token()
            return []

    # ══════════════════════════════════════════════
    # Uploaded Files
    # ══════════════════════════════════════════════

    def save_uploaded_file(self, file_data: dict) -> bool:
        if not self.available:
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                MERGE uploaded_files AS target
                USING (SELECT ? AS id) AS source ON target.id = source.id
                WHEN MATCHED THEN UPDATE SET
                    filename=?, doc_count=?, summary=?, keywords=?, filter_values=?, uploaded_at=?
                WHEN NOT MATCHED THEN INSERT
                    (id, filename, doc_count, summary, keywords, filter_values, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
                file_data["id"],
                file_data.get("filename", ""), file_data.get("doc_count", 0),
                file_data.get("summary", ""), json.dumps(file_data.get("keywords", [])),
                json.dumps(file_data.get("filter_values", {})),
                file_data.get("uploaded_at", ""),
                # INSERT
                file_data["id"],
                file_data.get("filename", ""), file_data.get("doc_count", 0),
                file_data.get("summary", ""), json.dumps(file_data.get("keywords", [])),
                json.dumps(file_data.get("filter_values", {})),
                file_data.get("uploaded_at", ""),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to save file metadata: {e}")
            self._refresh_token()
            return False

    def load_all_uploaded_files(self) -> list[dict]:
        if not self.available:
            return []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, filename, doc_count, summary, keywords, filter_values, uploaded_at FROM uploaded_files")
            rows = cursor.fetchall()
            conn.close()
            return [{
                "id": r[0], "filename": r[1], "doc_count": r[2],
                "summary": r[3],
                "keywords": json.loads(r[4]) if r[4] else [],
                "filter_values": json.loads(r[5]) if r[5] else {},
                "uploaded_at": r[6] or "",
            } for r in rows]
        except Exception as e:
            logger.warning(f"Failed to load uploaded files: {e}")
            self._refresh_token()
            return []

    # ══════════════════════════════════════════════
    # Filter Schema
    # ══════════════════════════════════════════════

    def save_filter_schema(self, schema_data: dict) -> bool:
        if not self.available:
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                MERGE filter_schemas AS target
                USING (SELECT 'global_schema' AS id) AS source ON target.id = source.id
                WHEN MATCHED THEN UPDATE SET domain=?, dimensions=?
                WHEN NOT MATCHED THEN INSERT (id, domain, dimensions) VALUES ('global_schema', ?, ?);
            """,
                schema_data.get("domain", ""), json.dumps(schema_data.get("dimensions", [])),
                schema_data.get("domain", ""), json.dumps(schema_data.get("dimensions", [])),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to save filter schema: {e}")
            self._refresh_token()
            return False

    def load_filter_schema(self) -> Optional[dict]:
        if not self.available:
            return None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT domain, dimensions FROM filter_schemas WHERE id = 'global_schema'")
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "domain": row[0] or "",
                    "dimensions": json.loads(row[1]) if row[1] else [],
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to load filter schema: {e}")
            self._refresh_token()
            return None

    # ══════════════════════════════════════════════
    # Enrichment Cache
    # ══════════════════════════════════════════════

    def get_enrichment(self, doc_hash: str) -> Optional[dict]:
        if not self.available:
            return None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT enrichment FROM enrichment_cache WHERE doc_hash = ?", doc_hash)
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger.warning(f"Failed to get enrichment cache: {e}")
            self._refresh_token()
            return None

    def save_enrichment(self, doc_hash: str, filename: str, enrichment: dict) -> bool:
        if not self.available:
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                MERGE enrichment_cache AS target
                USING (SELECT ? AS doc_hash) AS source ON target.doc_hash = source.doc_hash
                WHEN MATCHED THEN UPDATE SET filename=?, enrichment=?, cached_at=GETUTCDATE()
                WHEN NOT MATCHED THEN INSERT (doc_hash, filename, enrichment) VALUES (?, ?, ?);
            """,
                doc_hash, filename, json.dumps(enrichment),
                doc_hash, filename, json.dumps(enrichment),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to cache enrichment: {e}")
            self._refresh_token()
            return False

    # ══════════════════════════════════════════════
    # Structured Queries (for chat)
    # ══════════════════════════════════════════════

    def query_documents(self, sql_where: str = "", params: list = None) -> list[dict]:
        """Run a filtered query against the documents table.
        Used by the RAG system to support structured queries."""
        if not self.available:
            return []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = "SELECT id, doc_type, text_content, summary, source_file FROM documents"
            if sql_where:
                query += f" WHERE {sql_where}"
            cursor.execute(query, params or [])
            rows = cursor.fetchall()
            conn.close()
            return [{"id": r[0], "type": r[1], "text": r[2], "summary": r[3], "source_file": r[4]} for r in rows]
        except Exception as e:
            logger.warning(f"Structured query failed: {e}")
            self._refresh_token()
            return []

    def get_document_count(self) -> int:
        if not self.available:
            return 0
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def get_document_types(self) -> dict[str, int]:
        if not self.available:
            return {}
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type")
            rows = cursor.fetchall()
            conn.close()
            return {r[0]: r[1] for r in rows}
        except Exception:
            return {}

    # ══════════════════════════════════════════════
    # Insights Cache
    # ══════════════════════════════════════════════

    def save_insights(self, cache_key: str, insights: dict) -> bool:
        if not self.available:
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                MERGE insights_cache AS target
                USING (SELECT ? AS id) AS source ON target.id = source.id
                WHEN MATCHED THEN UPDATE SET insights=?, generated_at=GETUTCDATE()
                WHEN NOT MATCHED THEN INSERT (id, insights) VALUES (?, ?);
            """, cache_key, json.dumps(insights), cache_key, json.dumps(insights))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to save insights: {e}")
            self._refresh_token()
            return False

    def load_insights(self, cache_key: str) -> Optional[dict]:
        if not self.available:
            return None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT insights FROM insights_cache WHERE id = ?", cache_key)
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return json.loads(row[0])
            return None
        except Exception:
            return None


sql_service = AzureSqlService()
