"""Azure Cosmos DB service for persisting chat sessions, messages, and document insights.

Containers:
  - chat_sessions: session metadata (id, title, created_at, updated_at, message_count)
  - chat_messages: individual messages per session (session_id, role, content, sources, timestamp)
  - insights:      generated insights per dataset (dataset_id, insights, generated_at)
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from backend.config import get_settings

logger = logging.getLogger(__name__)


class CosmosService:
    """Manages Cosmos DB containers for chat and insights persistence."""

    SESSIONS_CONTAINER = "chat_sessions"
    MESSAGES_CONTAINER = "chat_messages"
    INSIGHTS_CONTAINER = "document_insights"
    ENRICHMENT_CONTAINER = "enrichment_cache"
    DOCUMENTS_CONTAINER = "documents"
    FILES_CONTAINER = "uploaded_files"
    SCHEMA_CONTAINER = "filter_schemas"

    def __init__(self):
        self._client: Optional[CosmosClient] = None
        self._db = None
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return
        settings = get_settings()
        if not settings.azure_cosmos_endpoint:
            logger.info("Cosmos DB not configured — persistence disabled")
            return

        try:
            credential = DefaultAzureCredential()
            self._client = CosmosClient(settings.azure_cosmos_endpoint, credential=credential)
            self._db = self._client.create_database_if_not_exists(settings.azure_cosmos_database)

            self._db.create_container_if_not_exists(
                id=self.SESSIONS_CONTAINER,
                partition_key=PartitionKey(path="/user_id"),
            )
            self._db.create_container_if_not_exists(
                id=self.MESSAGES_CONTAINER,
                partition_key=PartitionKey(path="/session_id"),
            )
            self._db.create_container_if_not_exists(
                id=self.INSIGHTS_CONTAINER,
                partition_key=PartitionKey(path="/dataset_id"),
            )
            self._db.create_container_if_not_exists(
                id=self.ENRICHMENT_CONTAINER,
                partition_key=PartitionKey(path="/doc_hash"),
            )
            self._db.create_container_if_not_exists(
                id=self.DOCUMENTS_CONTAINER,
                partition_key=PartitionKey(path="/id"),
            )
            self._db.create_container_if_not_exists(
                id=self.FILES_CONTAINER,
                partition_key=PartitionKey(path="/id"),
            )
            self._db.create_container_if_not_exists(
                id=self.SCHEMA_CONTAINER,
                partition_key=PartitionKey(path="/id"),
            )
            self._initialized = True
            logger.info("Cosmos DB initialized with 7 containers")
        except Exception as e:
            logger.warning(f"Cosmos DB init failed: {e}")

    @property
    def available(self) -> bool:
        self._ensure_init()
        return self._initialized and self._db is not None

    # ══════════════════════════════════════════════
    # Chat Sessions
    # ══════════════════════════════════════════════

    def create_session(self, user_id: str, title: str = "New Chat") -> Optional[dict]:
        """Create a new chat session. Returns session metadata."""
        if not self.available:
            return None
        try:
            container = self._db.get_container_client(self.SESSIONS_CONTAINER)
            session = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "title": title,
                "message_count": 0,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
            container.create_item(session)
            return session
        except Exception as e:
            logger.warning(f"Failed to create session: {e}")
            return None

    def list_sessions(self, user_id: str, limit: int = 50) -> list[dict]:
        """List chat sessions for a user, most recent first."""
        if not self.available:
            return []
        try:
            container = self._db.get_container_client(self.SESSIONS_CONTAINER)
            query = (
                "SELECT c.id, c.title, c.message_count, c.created_at, c.updated_at "
                "FROM c WHERE c.user_id = @user_id "
                "ORDER BY c.updated_at DESC OFFSET 0 LIMIT @limit"
            )
            items = list(container.query_items(
                query,
                parameters=[
                    {"name": "@user_id", "value": user_id},
                    {"name": "@limit", "value": limit},
                ],
                partition_key=user_id,
            ))
            return items
        except Exception as e:
            logger.warning(f"Failed to list sessions: {e}")
            return []

    def update_session(self, session_id: str, user_id: str, title: Optional[str] = None,
                       message_count: Optional[int] = None) -> bool:
        """Update session metadata (title, message count)."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.SESSIONS_CONTAINER)
            item = container.read_item(item=session_id, partition_key=user_id)
            if title is not None:
                item["title"] = title
            if message_count is not None:
                item["message_count"] = message_count
            item["updated_at"] = datetime.utcnow().isoformat() + "Z"
            container.replace_item(item=session_id, body=item)
            return True
        except Exception as e:
            logger.warning(f"Failed to update session: {e}")
            return False

    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a session and all its messages."""
        if not self.available:
            return False
        try:
            # Delete session
            sessions = self._db.get_container_client(self.SESSIONS_CONTAINER)
            sessions.delete_item(item=session_id, partition_key=user_id)

            # Delete all messages in session
            messages = self._db.get_container_client(self.MESSAGES_CONTAINER)
            query = "SELECT c.id FROM c WHERE c.session_id = @sid"
            items = list(messages.query_items(
                query, parameters=[{"name": "@sid", "value": session_id}],
                partition_key=session_id,
            ))
            for item in items:
                messages.delete_item(item=item["id"], partition_key=session_id)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete session: {e}")
            return False

    # ══════════════════════════════════════════════
    # Chat Messages
    # ══════════════════════════════════════════════

    def add_message(self, session_id: str, role: str, content: str,
                    sources: Optional[list[dict]] = None) -> Optional[dict]:
        """Add a single message to a session."""
        if not self.available:
            return None
        try:
            container = self._db.get_container_client(self.MESSAGES_CONTAINER)
            msg = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": role,
                "content": content,
                "sources": sources or [],
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            container.create_item(msg)
            return msg
        except Exception as e:
            logger.warning(f"Failed to add message: {e}")
            return None

    def get_messages(self, session_id: str) -> list[dict]:
        """Get all messages in a session, ordered by timestamp."""
        if not self.available:
            return []
        try:
            container = self._db.get_container_client(self.MESSAGES_CONTAINER)
            query = (
                "SELECT c.id, c.role, c.content, c.sources, c.timestamp "
                "FROM c WHERE c.session_id = @sid "
                "ORDER BY c.timestamp ASC"
            )
            items = list(container.query_items(
                query,
                parameters=[{"name": "@sid", "value": session_id}],
                partition_key=session_id,
            ))
            return items
        except Exception as e:
            logger.warning(f"Failed to get messages: {e}")
            return []

    def save_messages_bulk(self, session_id: str, messages: list[dict]) -> bool:
        """Save multiple messages at once (for batch save from frontend)."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.MESSAGES_CONTAINER)

            # Clear existing messages for this session
            existing = "SELECT c.id FROM c WHERE c.session_id = @sid"
            old = list(container.query_items(
                existing, parameters=[{"name": "@sid", "value": session_id}],
                partition_key=session_id,
            ))
            for item in old:
                try:
                    container.delete_item(item=item["id"], partition_key=session_id)
                except Exception:
                    pass

            # Insert new messages
            for i, msg in enumerate(messages):
                container.create_item({
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "sources": msg.get("sources", []),
                    "timestamp": msg.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                    "order": i,
                })
            return True
        except Exception as e:
            logger.warning(f"Failed to save messages bulk: {e}")
            return False

    # ══════════════════════════════════════════════
    # Document Insights
    # ══════════════════════════════════════════════

    def save_insights(self, dataset_id: str, insights: dict) -> bool:
        """Save generated insights for a dataset."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.INSIGHTS_CONTAINER)
            container.upsert_item({
                "id": dataset_id,
                "dataset_id": dataset_id,
                "insights": insights,
                "generated_at": datetime.utcnow().isoformat() + "Z",
            })
            return True
        except Exception as e:
            logger.warning(f"Failed to save insights: {e}")
            return False

    def load_insights(self, dataset_id: str) -> Optional[dict]:
        """Load cached insights for a dataset."""
        if not self.available:
            return None
        try:
            container = self._db.get_container_client(self.INSIGHTS_CONTAINER)
            item = container.read_item(item=dataset_id, partition_key=dataset_id)
            return item.get("insights")
        except Exception:
            return None

    def delete_insights(self, dataset_id: str) -> bool:
        """Delete cached insights."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.INSIGHTS_CONTAINER)
            container.delete_item(item=dataset_id, partition_key=dataset_id)
            return True
        except Exception:
            return False

    # ══════════════════════════════════════════════
    # Enrichment Cache
    # ══════════════════════════════════════════════

    def get_enrichment(self, doc_hash: str) -> Optional[dict]:
        """Look up cached enrichment result by content hash."""
        if not self.available:
            return None
        try:
            container = self._db.get_container_client(self.ENRICHMENT_CONTAINER)
            item = container.read_item(item=doc_hash, partition_key=doc_hash)
            return item.get("enrichment")
        except Exception:
            return None

    def save_enrichment(self, doc_hash: str, filename: str, enrichment: dict) -> bool:
        """Cache enrichment result keyed by content hash."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.ENRICHMENT_CONTAINER)
            container.upsert_item({
                "id": doc_hash,
                "doc_hash": doc_hash,
                "filename": filename,
                "enrichment": enrichment,
                "cached_at": datetime.utcnow().isoformat() + "Z",
            })
            return True
        except Exception as e:
            logger.warning(f"Failed to cache enrichment: {e}")
            return False

    # ══════════════════════════════════════════════
    # Document Persistence
    # ══════════════════════════════════════════════

    def save_document(self, doc_id: str, doc_data: dict) -> bool:
        """Save a document record to Cosmos DB."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.DOCUMENTS_CONTAINER)
            item = {"id": doc_id, **doc_data}
            # Cosmos can't store complex text types; normalize
            if isinstance(item.get("text"), list):
                item["text"] = "\n".join(
                    f"{s.get('speaker','')}: {s.get('text','')}" for s in item["text"]
                )
            container.upsert_item(item)
            return True
        except Exception as e:
            logger.warning(f"Failed to save document {doc_id}: {e}")
            return False

    def load_all_documents(self) -> list[dict]:
        """Load all documents from Cosmos DB."""
        if not self.available:
            return []
        try:
            container = self._db.get_container_client(self.DOCUMENTS_CONTAINER)
            return list(container.read_all_items())
        except Exception as e:
            logger.warning(f"Failed to load documents: {e}")
            return []

    def save_uploaded_file(self, file_data: dict) -> bool:
        """Save uploaded file metadata."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.FILES_CONTAINER)
            container.upsert_item(file_data)
            return True
        except Exception as e:
            logger.warning(f"Failed to save file metadata: {e}")
            return False

    def load_all_uploaded_files(self) -> list[dict]:
        """Load all uploaded file records."""
        if not self.available:
            return []
        try:
            container = self._db.get_container_client(self.FILES_CONTAINER)
            return list(container.read_all_items())
        except Exception as e:
            logger.warning(f"Failed to load uploaded files: {e}")
            return []

    def save_filter_schema(self, schema_data: dict) -> bool:
        """Save the merged filter schema."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.SCHEMA_CONTAINER)
            container.upsert_item({"id": "global_schema", **schema_data})
            return True
        except Exception as e:
            logger.warning(f"Failed to save filter schema: {e}")
            return False

    def load_filter_schema(self) -> Optional[dict]:
        """Load the filter schema."""
        if not self.available:
            return None
        try:
            container = self._db.get_container_client(self.SCHEMA_CONTAINER)
            item = container.read_item(item="global_schema", partition_key="global_schema")
            return item
        except Exception:
            return None


cosmos_service = CosmosService()
