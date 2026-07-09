"""Azure SQL service for persisting documents, uploaded files, filter schemas, and enrichment cache.

Uses pyodbc with Azure AD token-based auth (passwordless).
Tables are auto-created on first use.
"""

import json
import logging
from typing import Optional

from src.api.config import get_settings

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
            from azure.identity import DefaultAzureCredential
            import struct
            import time

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
            self._token_acquired_at = time.time()

            # Create tables
            self._create_tables()
            self._initialized = True
            logger.info(f"Azure SQL initialized: {server}/{database}")
        except Exception as e:
            self._init_failed = True
            logger.warning(f"Azure SQL init failed (will not retry): {e}")

    def _get_connection(self):
        import pyodbc
        import time
        # Refresh token if it's older than 50 minutes (tokens expire after 60 min)
        if hasattr(self, '_token_acquired_at') and (time.time() - self._token_acquired_at) > 3000:
            self._refresh_token()
        conn = pyodbc.connect(self._conn_str, attrs_before={1256: self._token_struct})
        return conn

    def _refresh_token(self):
        """Refresh the AAD token for long-running connections."""
        import struct
        import time
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/.default")
        token_bytes = token.token.encode("utf-16-le")
        self._token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
        self._token_acquired_at = time.time()

    def _create_tables(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'documents')
            CREATE TABLE documents (
                id NVARCHAR(255) PRIMARY KEY,
                source_type NVARCHAR(50) DEFAULT 'uploaded',
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
                doc_ids NVARCHAR(MAX),
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
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'external_data_sources')
            CREATE TABLE external_data_sources (
                id NVARCHAR(255) PRIMARY KEY,
                name NVARCHAR(500),
                source_type NVARCHAR(50),
                use_case NVARCHAR(100) DEFAULT '',
                connection_string NVARCHAR(MAX),
                endpoint NVARCHAR(500),
                database_name NVARCHAR(500),
                table_or_query NVARCHAR(MAX),
                auth_method NVARCHAR(50),
                field_mapping NVARCHAR(MAX),
                query_mode NVARCHAR(50),
                status NVARCHAR(50),
                doc_count INT DEFAULT 0,
                last_sync NVARCHAR(100),
                error_message NVARCHAR(MAX),
                created_at DATETIME2 DEFAULT GETUTCDATE(),
                updated_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """)
        cursor.execute("""
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'external_data_sources')
            AND NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('external_data_sources') AND name = 'use_case')
            ALTER TABLE external_data_sources ADD use_case NVARCHAR(100) DEFAULT ''
        """)
        cursor.execute("""
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'uploaded_files')
            AND NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('uploaded_files') AND name = 'doc_ids')
            ALTER TABLE uploaded_files ADD doc_ids NVARCHAR(MAX) DEFAULT ''
        """)
        cursor.execute("""
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'uploaded_files')
            AND NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('uploaded_files') AND name = 'source')
            ALTER TABLE uploaded_files ADD source NVARCHAR(50) DEFAULT 'uploaded'
        """)
        cursor.execute("""
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'documents')
            AND NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('documents') AND name = 'source_type')
            ALTER TABLE documents ADD source_type NVARCHAR(50) DEFAULT 'uploaded'
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'entity_nodes')
            CREATE TABLE entity_nodes (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(500) NOT NULL,
                normalized_name NVARCHAR(500) NOT NULL,
                entity_type NVARCHAR(100) NOT NULL,
                first_seen DATETIME2 DEFAULT GETUTCDATE(),
                last_seen DATETIME2 DEFAULT GETUTCDATE()
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'document_entities')
            CREATE TABLE document_entities (
                doc_id NVARCHAR(255) NOT NULL,
                entity_id INT NOT NULL,
                context NVARCHAR(MAX) NULL,
                confidence FLOAT NULL,
                created_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'entity_relationships')
            CREATE TABLE entity_relationships (
                id INT IDENTITY(1,1) PRIMARY KEY,
                doc_id NVARCHAR(255) NOT NULL,
                subject_entity_id INT NOT NULL,
                relation NVARCHAR(120) NOT NULL,
                object_entity_id INT NULL,
                object_value NVARCHAR(500) NULL,
                evidence NVARCHAR(MAX) NULL,
                confidence FLOAT NULL,
                created_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """)

        # ── Indexes for frequently queried columns ──
        for idx_sql in [
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_documents_source_file') CREATE INDEX IX_documents_source_file ON documents(source_file)",
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_chat_messages_session_id') CREATE INDEX IX_chat_messages_session_id ON chat_messages(session_id)",
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_chat_sessions_user_id') CREATE INDEX IX_chat_sessions_user_id ON chat_sessions(user_id)",
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_external_data_sources_status') CREATE INDEX IX_external_data_sources_status ON external_data_sources(status)",
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'UX_entity_nodes_normalized_type') CREATE UNIQUE INDEX UX_entity_nodes_normalized_type ON entity_nodes(normalized_name, entity_type)",
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_document_entities_doc') CREATE INDEX IX_document_entities_doc ON document_entities(doc_id)",
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_document_entities_entity') CREATE INDEX IX_document_entities_entity ON document_entities(entity_id)",
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_entity_relationships_doc') CREATE INDEX IX_entity_relationships_doc ON entity_relationships(doc_id)",
            "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_entity_relationships_subject') CREATE INDEX IX_entity_relationships_subject ON entity_relationships(subject_entity_id)",
        ]:
            cursor.execute(idx_sql)

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
                text = "\n".join(f"{s.get('speaker', '')}: {s.get('text', '')}" for s in text)

            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                MERGE documents AS target
                USING (SELECT ? AS id) AS source ON target.id = source.id
                WHEN MATCHED THEN UPDATE SET
                    source_type=?, doc_type=?, text_content=?, summary=?, entities=?,
                    key_phrases=?, topics=?, metadata=?, source_file=?
                WHEN NOT MATCHED THEN INSERT
                    (id, source_type, doc_type, text_content, summary, entities, key_phrases, topics, metadata, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                doc_id,
                doc_data.get("metadata", {}).get("source_type", "uploaded"),
                doc_data.get("type", ""), text, doc_data.get("summary", ""),
                json.dumps(doc_data.get("entities", [])),
                json.dumps(doc_data.get("key_phrases", [])),
                json.dumps(doc_data.get("topics", [])),
                json.dumps(doc_data.get("metadata", {})),
                doc_data.get("metadata", {}).get("source_file", ""),
                # INSERT values
                doc_id,
                doc_data.get("metadata", {}).get("source_type", "uploaded"),
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

    def load_all_documents(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        if not self.available:
            return []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, source_type, doc_type, text_content, summary, entities, key_phrases, topics, metadata, source_file "
                "FROM documents ORDER BY created_at DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
                [offset, limit])
            rows = cursor.fetchall()
            conn.close()
            results = []
            for row in rows:
                metadata = json.loads(row[8]) if row[8] else {}
                if not isinstance(metadata, dict):
                    metadata = {}
                if row[1] and not metadata.get("source_type"):
                    metadata["source_type"] = row[1]
                if row[9] and not metadata.get("source_file"):
                    metadata["source_file"] = row[9]
                results.append({
                    "id": row[0],
                    "type": row[2],
                    "text": row[3],
                    "summary": row[4],
                    "entities": json.loads(row[5]) if row[5] else [],
                    "key_phrases": json.loads(row[6]) if row[6] else [],
                    "topics": json.loads(row[7]) if row[7] else [],
                    "metadata": metadata,
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
            cursor.execute(
                """
                MERGE uploaded_files AS target
                USING (SELECT ? AS id) AS source ON target.id = source.id
                WHEN MATCHED THEN UPDATE SET
                    filename=?, doc_count=?, summary=?, keywords=?, filter_values=?, doc_ids=?, uploaded_at=?, source=?
                WHEN NOT MATCHED THEN INSERT
                    (id, filename, doc_count, summary, keywords, filter_values, doc_ids, uploaded_at, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                file_data["id"],
                file_data.get("filename", ""), file_data.get("doc_count", 0),
                file_data.get("summary", ""), json.dumps(file_data.get("keywords", [])),
                json.dumps(file_data.get("filter_values", {})),
                json.dumps(file_data.get("doc_ids", [])),
                file_data.get("uploaded_at", ""),
                file_data.get("source", "uploaded"),
                # INSERT
                file_data["id"],
                file_data.get("filename", ""), file_data.get("doc_count", 0),
                file_data.get("summary", ""), json.dumps(file_data.get("keywords", [])),
                json.dumps(file_data.get("filter_values", {})),
                json.dumps(file_data.get("doc_ids", [])),
                file_data.get("uploaded_at", ""),
                file_data.get("source", "uploaded"),
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
            cursor.execute("SELECT id, filename, doc_count, summary, keywords, filter_values, doc_ids, uploaded_at, source FROM uploaded_files")
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "id": r[0], "filename": r[1], "doc_count": r[2],
                    "summary": r[3],
                    "keywords": json.loads(r[4]) if r[4] else [],
                    "filter_values": json.loads(r[5]) if r[5] else {},
                    "doc_ids": json.loads(r[6]) if r[6] else [],
                    "uploaded_at": r[7] or "",
                    "source": r[8] or "uploaded",
                }
                for r in rows
            ]
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
            cursor.execute(
                """
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
            cursor.execute(
                """
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
        except Exception as e:
            logger.warning(f"Failed to get document count: {e}")
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
        except Exception as e:
            logger.warning(f"Failed to get document types: {e}")
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
        except Exception as e:
            logger.warning(f"Failed to load insights: {e}")
            return None

    # ══════════════════════════════════════════════
    # External Data Sources
    # ══════════════════════════════════════════════

    def save_data_source(self, data: dict) -> bool:
        if not self.available:
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                MERGE external_data_sources AS target
                USING (SELECT ? AS id) AS source ON target.id = source.id
                WHEN MATCHED THEN UPDATE SET
                    name=?, source_type=?, use_case=?, connection_string=?, endpoint=?,
                    database_name=?, table_or_query=?, auth_method=?,
                    field_mapping=?, query_mode=?, status=?, doc_count=?,
                    last_sync=?, error_message=?, updated_at=GETUTCDATE()
                WHEN NOT MATCHED THEN INSERT
                    (id, name, source_type, use_case, connection_string, endpoint,
                     database_name, table_or_query, auth_method,
                     field_mapping, query_mode, status, doc_count,
                     last_sync, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                data["id"],
                data.get("name", ""), data.get("source_type", ""),
                data.get("use_case", ""),
                data.get("connection_string", ""), data.get("endpoint", ""),
                data.get("database", ""), data.get("table_or_query", ""),
                data.get("auth_method", ""), json.dumps(data.get("field_mapping", {})),
                data.get("query_mode", "both"), data.get("status", "disconnected"),
                data.get("doc_count", 0), data.get("last_sync", ""),
                data.get("error_message", ""),
                # INSERT values
                data["id"],
                data.get("name", ""), data.get("source_type", ""),
                data.get("use_case", ""),
                data.get("connection_string", ""), data.get("endpoint", ""),
                data.get("database", ""), data.get("table_or_query", ""),
                data.get("auth_method", ""), json.dumps(data.get("field_mapping", {})),
                data.get("query_mode", "both"), data.get("status", "disconnected"),
                data.get("doc_count", 0), data.get("last_sync", ""),
                data.get("error_message", ""),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to save data source: {e}")
            self._refresh_token()
            return False

    def load_data_sources(self) -> list[dict]:
        if not self.available:
            return []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, source_type, use_case, connection_string, endpoint,
                       database_name, table_or_query, auth_method,
                       field_mapping, query_mode, status, doc_count,
                       last_sync, error_message
                FROM external_data_sources
            """)
            rows = cursor.fetchall()
            conn.close()
            results = []
            for r in rows:
                fm = json.loads(r[9]) if r[9] else {}
                results.append({
                    "id": r[0], "name": r[1], "source_type": r[2],
                    "use_case": r[3] or "",
                    "connection_string": r[4], "endpoint": r[5],
                    "database": r[6], "table_or_query": r[7],
                    "auth_method": r[8], "field_mapping": fm,
                    "query_mode": r[10], "status": r[11],
                    "doc_count": r[12] or 0, "last_sync": r[13] or "",
                    "error_message": r[14] or "",
                })
            return results
        except Exception as e:
            logger.warning(f"Failed to load data sources: {e}")
            self._refresh_token()
            return []

    def delete_data_source(self, source_id: str) -> bool:
        if not self.available:
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM external_data_sources WHERE id = ?", source_id)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to delete data source: {e}")
            self._refresh_token()
            return False

    # ══════════════════════════════════════════════
    # Entity Graph (nodes + relationships)
    # ══════════════════════════════════════════════

    @staticmethod
    def _normalize_entity_name(name: str) -> str:
        normalized = " ".join((name or "").strip().lower().split())
        return normalized[:500]

    @staticmethod
    def _entity_type(value: str) -> str:
        typed = (value or "unknown").strip().lower() or "unknown"
        return typed[:100]

    def _upsert_entity_node(self, cursor, name: str, entity_type: str) -> Optional[int]:
        if not name:
            return None
        normalized = self._normalize_entity_name(name)
        if not normalized:
            return None
        etype = self._entity_type(entity_type)

        # Atomic MERGE to avoid duplicate-key races under concurrent inserts.
        cursor.execute(
            """
            MERGE entity_nodes WITH (HOLDLOCK) AS target
            USING (SELECT ? AS normalized_name, ? AS entity_type) AS src
                ON target.normalized_name = src.normalized_name
               AND target.entity_type     = src.entity_type
            WHEN MATCHED THEN
                UPDATE SET last_seen = GETUTCDATE(), name = ?
            WHEN NOT MATCHED THEN
                INSERT (name, normalized_name, entity_type) VALUES (?, ?, ?);
            """,
            normalized,
            etype,
            name[:500],
            name[:500],
            normalized,
            etype,
        )

        cursor.execute(
            "SELECT id FROM entity_nodes WHERE normalized_name = ? AND entity_type = ?",
            normalized,
            etype,
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None

    def save_entity_graph(self, doc_id: str, source_file: str, entities: list[dict], relationships: list[dict]) -> bool:
        if not self.available:
            return False
        if not doc_id:
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM document_entities WHERE doc_id = ?", doc_id)
            cursor.execute("DELETE FROM entity_relationships WHERE doc_id = ?", doc_id)

            entity_id_map: dict[str, int] = {}
            for entity in entities or []:
                if not isinstance(entity, dict):
                    continue
                name = str(entity.get("name", "")).strip()
                if not name:
                    continue
                node_id = self._upsert_entity_node(cursor, name, str(entity.get("type", "unknown")))
                if not node_id:
                    continue
                entity_id_map[self._normalize_entity_name(name)] = node_id
                context = str(entity.get("context", "") or "")
                confidence = entity.get("confidence")
                conf_val = float(confidence) if isinstance(confidence, (int, float)) else None
                cursor.execute(
                    "INSERT INTO document_entities (doc_id, entity_id, context, confidence) VALUES (?, ?, ?, ?)",
                    doc_id,
                    node_id,
                    context[:4000],
                    conf_val,
                )

            for rel in relationships or []:
                if not isinstance(rel, dict):
                    continue
                subject_name = str(rel.get("subject", "") or rel.get("source", "") or rel.get("from", "")).strip()
                relation = str(rel.get("relation", "") or rel.get("predicate", "") or rel.get("type", "")).strip()
                if not subject_name or not relation:
                    continue

                subject_id = entity_id_map.get(self._normalize_entity_name(subject_name))
                if not subject_id:
                    subject_id = self._upsert_entity_node(cursor, subject_name, str(rel.get("subject_type", "unknown")))
                    if not subject_id:
                        continue

                object_name = str(rel.get("object", "") or rel.get("target", "") or rel.get("to", "")).strip()
                object_id = None
                object_value = None
                if object_name:
                    object_id = entity_id_map.get(self._normalize_entity_name(object_name))
                    if not object_id:
                        object_id = self._upsert_entity_node(cursor, object_name, str(rel.get("object_type", "unknown")))
                    if not object_id:
                        object_value = object_name[:500]

                evidence = str(rel.get("context", "") or rel.get("evidence", "") or rel.get("snippet", ""))
                confidence = rel.get("confidence")
                conf_val = float(confidence) if isinstance(confidence, (int, float)) else None

                cursor.execute(
                    """
                    INSERT INTO entity_relationships
                        (doc_id, subject_entity_id, relation, object_entity_id, object_value, evidence, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    doc_id,
                    subject_id,
                    relation[:120],
                    object_id,
                    object_value,
                    evidence[:4000],
                    conf_val,
                )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to save entity graph for {doc_id}: {e}")
            self._refresh_token()
            return False

    def delete_entity_graph_for_docs(self, doc_ids: list[str]) -> bool:
        if not self.available or not doc_ids:
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            for doc_id in doc_ids:
                cursor.execute("DELETE FROM document_entities WHERE doc_id = ?", doc_id)
                cursor.execute("DELETE FROM entity_relationships WHERE doc_id = ?", doc_id)

            cursor.execute(
                """
                DELETE FROM entity_nodes
                WHERE id NOT IN (
                    SELECT DISTINCT entity_id FROM document_entities
                    UNION
                    SELECT DISTINCT subject_entity_id FROM entity_relationships
                    UNION
                    SELECT DISTINCT object_entity_id FROM entity_relationships WHERE object_entity_id IS NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to delete entity graph docs: {e}")
            self._refresh_token()
            return False


sql_service = AzureSqlService()
