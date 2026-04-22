"""Azure SQL store for chat sessions and chat message history.

Separated from sql_service to keep concerns clean.
Reuses the shared SQL connection infrastructure from sql_service.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ChatStore:
    """Manages chat sessions and message history in Azure SQL."""

    def _get_sql(self):
        from backend.storage.sql_service import sql_service
        return sql_service

    @property
    def available(self) -> bool:
        return self._get_sql().available

    # ══════════════════════════════════════════════
    # Sessions
    # ══════════════════════════════════════════════

    def create_session(self, user_id: str, title: str = "New Chat") -> Optional[dict]:
        sql = self._get_sql()
        if not sql.available:
            return None
        try:
            session_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat() + "Z"
            conn = sql._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_sessions (id, user_id, title, message_count, created_at, updated_at) VALUES (?,?,?,0,GETUTCDATE(),GETUTCDATE())",
                session_id, user_id, title,
            )
            conn.commit()
            conn.close()
            return {"id": session_id, "user_id": user_id, "title": title, "message_count": 0, "created_at": now, "updated_at": now}
        except Exception as e:
            logger.warning(f"Failed to create session: {e}")
            sql._refresh_token()
            return None

    def list_sessions(self, user_id: str, limit: int = 50) -> list[dict]:
        sql = self._get_sql()
        if not sql.available:
            return []
        try:
            conn = sql._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT TOP (?) id, title, message_count, created_at, updated_at FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
                limit, user_id,
            )
            rows = cursor.fetchall()
            conn.close()
            return [{"id": r[0], "title": r[1], "message_count": r[2], "created_at": str(r[3]), "updated_at": str(r[4])} for r in rows]
        except Exception as e:
            logger.warning(f"Failed to list sessions: {e}")
            sql._refresh_token()
            return []

    def update_session(self, session_id: str, user_id: str, title: Optional[str] = None, message_count: Optional[int] = None) -> bool:
        sql = self._get_sql()
        if not sql.available:
            return False
        try:
            conn = sql._get_connection()
            cursor = conn.cursor()
            sets = ["updated_at = GETUTCDATE()"]
            params = []
            if title is not None:
                sets.append("title = ?")
                params.append(title)
            if message_count is not None:
                sets.append("message_count = ?")
                params.append(message_count)
            params.append(session_id)
            cursor.execute(f"UPDATE chat_sessions SET {', '.join(sets)} WHERE id = ?", *params)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to update session: {e}")
            sql._refresh_token()
            return False

    def delete_session(self, session_id: str, user_id: str) -> bool:
        sql = self._get_sql()
        if not sql.available:
            return False
        try:
            conn = sql._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", session_id)
            cursor.execute("DELETE FROM chat_sessions WHERE id = ? AND user_id = ?", session_id, user_id)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to delete session: {e}")
            sql._refresh_token()
            return False

    # ══════════════════════════════════════════════
    # Messages
    # ══════════════════════════════════════════════

    def add_message(self, session_id: str, role: str, content: str, sources: Optional[list] = None) -> Optional[dict]:
        sql = self._get_sql()
        if not sql.available:
            return None
        try:
            msg_id = str(uuid.uuid4())
            conn = sql._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (id, session_id, role, content, sources) VALUES (?,?,?,?,?)",
                msg_id, session_id, role, content, json.dumps(sources or []),
            )
            conn.commit()
            conn.close()
            return {"id": msg_id, "session_id": session_id, "role": role, "content": content}
        except Exception as e:
            logger.warning(f"Failed to add message: {e}")
            sql._refresh_token()
            return None

    def get_messages(self, session_id: str) -> list[dict]:
        sql = self._get_sql()
        if not sql.available:
            return []
        try:
            conn = sql._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, role, content, sources, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
                session_id,
            )
            rows = cursor.fetchall()
            conn.close()
            return [{
                "id": r[0], "role": r[1], "content": r[2],
                "sources": json.loads(r[3]) if r[3] else [],
                "timestamp": str(r[4]),
            } for r in rows]
        except Exception as e:
            logger.warning(f"Failed to get messages: {e}")
            sql._refresh_token()
            return []

    def save_messages_bulk(self, session_id: str, messages: list[dict]) -> bool:
        sql = self._get_sql()
        if not sql.available:
            return False
        try:
            conn = sql._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", session_id)
            for i, msg in enumerate(messages):
                cursor.execute(
                    "INSERT INTO chat_messages (id, session_id, role, content, sources, sort_order) VALUES (?,?,?,?,?,?)",
                    str(uuid.uuid4()), session_id, msg.get("role", "user"),
                    msg.get("content", ""), json.dumps(msg.get("sources", [])), i,
                )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to save messages bulk: {e}")
            sql._refresh_token()
            return False


chat_store = ChatStore()
