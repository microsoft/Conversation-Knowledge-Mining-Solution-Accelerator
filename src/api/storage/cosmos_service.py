"""Azure Cosmos DB service for persisting chat sessions, messages, and document insights.

Containers:
  - chat_sessions: session metadata (id, title, created_at, updated_at, message_count)
  - chat_messages: individual messages per session (session_id, role, content, sources, timestamp)
  - insights:      generated insights per dataset (dataset_id, insights, generated_at)
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from azure.core import MatchConditions

from src.api.config import get_settings
from src.api.storage.db_service import ChatHistoryMigrationRequired

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

    # --- Chat Sessions ---

    @staticmethod
    def _history_prefix(session_id: str, user_id: str) -> str:
        identity = json.dumps([user_id, session_id], separators=(",", ":")).encode()
        return "owner-" + hashlib.sha256(identity).hexdigest() + "-"

    def _message_partition(self, session: dict, user_id: str) -> str:
        partition = session.get("message_partition")
        if not isinstance(partition, str) or not partition.startswith(
            self._history_prefix(session["id"], user_id)
        ):
            raise ChatHistoryMigrationRequired(
                "Legacy Cosmos chat history requires an administrator-approved ownership migration."
            )
        return partition

    def get_session(self, session_id: str, user_id: str) -> Optional[dict]:
        if not self.available:
            return None
        try:
            container = self._db.get_container_client(self.SESSIONS_CONTAINER)
            return container.read_item(item=session_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            return None
        except CosmosHttpResponseError:
            logger.exception("Failed to read chat session")
            raise

    def create_session(self, user_id: str, title: str = "New Chat", session_id: Optional[str] = None) -> Optional[dict]:
        """Create a new chat session. Returns session metadata."""
        if not self.available:
            return None
        try:
            container = self._db.get_container_client(self.SESSIONS_CONTAINER)
            session = {
                "id": session_id or str(uuid.uuid4()),
                "user_id": user_id,
                "title": title,
                "message_count": 0,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
            session["message_partition"] = self._history_prefix(session["id"], user_id) + str(uuid.uuid4())
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
            container.replace_item(
                item=session_id, body=item, etag=item["_etag"],
                match_condition=MatchConditions.IfNotModified,
            )
            return True
        except CosmosResourceNotFoundError:
            return False
        except CosmosHttpResponseError:
            logger.exception("Failed to update chat session")
            raise

    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a session and all its messages."""
        if not self.available:
            return False
        session = self.get_session(session_id, user_id)
        if session is None:
            return False
        partition = self._message_partition(session, user_id) if "message_partition" in session else None
        try:
            sessions = self._db.get_container_client(self.SESSIONS_CONTAINER)
            sessions.delete_item(
                item=session_id, partition_key=user_id, etag=session["_etag"],
                match_condition=MatchConditions.IfNotModified,
            )
            # Legacy message partitions may be shared by multiple owners; never delete them.
            if partition is not None:
                self._delete_message_partition(partition)
            return True
        except CosmosResourceNotFoundError:
            return False
        except CosmosHttpResponseError:
            logger.exception("Failed to delete chat session")
            raise

    # --- Chat Messages ---

    def _delete_message_partition(self, partition: str):
        container = self._db.get_container_client(self.MESSAGES_CONTAINER)
        items = list(container.query_items(
            "SELECT c.id FROM c WHERE c.session_id = @sid",
            parameters=[{"name": "@sid", "value": partition}],
            partition_key=partition,
        ))
        for item in items:
            container.delete_item(item=item["id"], partition_key=partition)

    def add_message(self, session_id: str, user_id: str, role: str, content: str,
                    sources: Optional[list[dict]] = None) -> Optional[dict]:
        """Add a single message to a session."""
        if not self.available:
            return None
        if self.get_session(session_id, user_id) is None:
            return None
        messages = self.get_messages(session_id, user_id)
        msg = {
            "id": str(uuid.uuid4()), "role": role, "content": content,
            "sources": sources or [], "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if self.save_messages_bulk(session_id, messages + [msg], user_id):
            return msg
        return None

    def get_messages(self, session_id: str, user_id: str) -> list[dict]:
        """Get all messages in a session, in saved order."""
        if not self.available:
            return []
        session = self.get_session(session_id, user_id)
        if session is None:
            return []
        partition = self._message_partition(session, user_id)
        try:
            container = self._db.get_container_client(self.MESSAGES_CONTAINER)
            query = (
                "SELECT c.id, c.role, c.content, c.sources, c.timestamp, c[\"order\"] AS position "
                "FROM c WHERE c.session_id = @sid"
            )
            items = list(container.query_items(
                query,
                parameters=[{"name": "@sid", "value": partition}],
                partition_key=partition,
            ))
            # Sort by the saved position (timestamps can tie or come from the client), then timestamp.
            items.sort(key=lambda m: (m.get("position") if isinstance(m.get("position"), int) else 0,
                                      str(m.get("timestamp") or "")))
            for m in items:
                m.pop("position", None)
            return items
        except CosmosHttpResponseError:
            logger.exception("Failed to get chat messages")
            raise

    def save_messages_bulk(self, session_id: str, messages: list[dict], user_id: str,
                           title: Optional[str] = None) -> bool:
        """Save multiple messages at once (for batch save from frontend)."""
        if not self.available:
            return False
        session = self.get_session(session_id, user_id)
        if session is None:
            return False
        old_partition = self._message_partition(session, user_id)
        partition = self._history_prefix(session_id, user_id) + str(uuid.uuid4())
        publishing = False
        try:
            container = self._db.get_container_client(self.MESSAGES_CONTAINER)
            # Publish a complete snapshot with an ETag check; never expose partial replacement.
            for i, msg in enumerate(messages):
                container.create_item({
                    "id": str(uuid.uuid4()),
                    "session_id": partition,
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "sources": msg.get("sources", []),
                    "timestamp": msg.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                    "order": i,
                })
            session["message_partition"] = partition
            session["message_count"] = len(messages)
            session["updated_at"] = datetime.utcnow().isoformat() + "Z"
            if title is not None:
                session["title"] = title
            publishing = True
            self._db.get_container_client(self.SESSIONS_CONTAINER).replace_item(
                item=session_id, body=session, etag=session["_etag"],
                match_condition=MatchConditions.IfNotModified,
            )
        except CosmosHttpResponseError as exc:
            logger.exception("Failed to save chat messages")
            # A timeout may occur after publication committed; preserve that snapshot.
            if not publishing or exc.status_code in (400, 401, 403, 404, 409, 412, 413):
                self._delete_message_partition(partition)
            else:
                logger.warning("Chat publication outcome is uncertain; snapshot retained: %s", partition)
            raise
        try:
            self._delete_message_partition(old_partition)
        except CosmosHttpResponseError:
            logger.exception("Chat saved, but obsolete history cleanup failed")
        return True

    # --- Document Insights ---

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
        except Exception as e:
            logger.warning(f"Failed to load insights for {dataset_id}: {e}")
            return None

    def delete_insights(self, dataset_id: str) -> bool:
        """Delete cached insights."""
        if not self.available:
            return False
        try:
            container = self._db.get_container_client(self.INSIGHTS_CONTAINER)
            container.delete_item(item=dataset_id, partition_key=dataset_id)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete insights for {dataset_id}: {e}")
            return False

    # --- Enrichment Cache ---

    def get_enrichment(self, doc_hash: str) -> Optional[dict]:
        """Look up cached enrichment result by content hash."""
        if not self.available:
            return None
        try:
            container = self._db.get_container_client(self.ENRICHMENT_CONTAINER)
            item = container.read_item(item=doc_hash, partition_key=doc_hash)
            return item.get("enrichment")
        except Exception as e:
            logger.warning(f"Failed to get enrichment for {doc_hash}: {e}")
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

    # --- Document Persistence ---

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
                    f"{s.get('speaker', '')}: {s.get('text', '')}" for s in item["text"]
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
        except Exception as e:
            logger.warning(f"Failed to load filter schema: {e}")
            return None


cosmos_service = CosmosService()
