"""Unified database service — uses Azure SQL for all storage.

All chat sessions, messages, insights, documents, files, filters,
and enrichment cache are stored in Azure SQL.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DbService:
    """Thin wrapper routing to sql_service (data) and chat_store (chat)."""

    def __init__(self):
        self._service = None
        self._chat = None

    def _ensure_init(self):
        if self._service is not None:
            return
        from backend.storage.sql_service import sql_service
        from backend.storage.chat_store import chat_store
        self._service = sql_service
        self._chat = chat_store
        logger.info("Database backend: Azure SQL")

    @property
    def available(self) -> bool:
        self._ensure_init()
        return self._service.available if self._service else False

    # ── Chat Sessions ──

    def create_session(self, user_id: str, title: str = "New Chat", session_id: Optional[str] = None) -> Optional[dict]:
        self._ensure_init()
        return self._chat.create_session(user_id, title, session_id)

    def list_sessions(self, user_id: str, limit: int = 50) -> list[dict]:
        self._ensure_init()
        return self._chat.list_sessions(user_id, limit)

    def update_session(self, session_id: str, user_id: str,
                       title: Optional[str] = None, message_count: Optional[int] = None) -> bool:
        self._ensure_init()
        return self._chat.update_session(session_id, user_id, title, message_count)

    def delete_session(self, session_id: str, user_id: str) -> bool:
        self._ensure_init()
        return self._chat.delete_session(session_id, user_id)

    # ── Chat Messages ──

    def add_message(self, session_id: str, role: str, content: str,
                    sources: Optional[list] = None) -> Optional[dict]:
        self._ensure_init()
        return self._chat.add_message(session_id, role, content, sources)

    def get_messages(self, session_id: str) -> list[dict]:
        self._ensure_init()
        return self._chat.get_messages(session_id)

    def save_messages_bulk(self, session_id: str, messages: list[dict]) -> bool:
        self._ensure_init()
        return self._chat.save_messages_bulk(session_id, messages)

    # ── Insights Cache ──

    def save_insights(self, cache_key: str, insights: dict) -> bool:
        self._ensure_init()
        return self._service.save_insights(cache_key, insights)

    def load_insights(self, cache_key: str) -> Optional[dict]:
        self._ensure_init()
        return self._service.load_insights(cache_key)


db_service = DbService()
