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
    """Manages chat sessions and message history. Uses Azure SQL when available, in-memory fallback otherwise."""

    def __init__(self):
        self._mem_sessions: dict[str, dict] = {}  # session_id -> session dict
        self._mem_messages: dict[str, list[dict]] = {}  # session_id -> [messages]

    def _get_sql(self):
        from src.api.storage.sql_service import sql_service
        return sql_service

    @property
    def available(self) -> bool:
        return True  # Always available — in-memory fallback

    # --- Sessions ---

    def create_session(self, user_id: str, title: str = "New Chat", session_id: Optional[str] = None) -> Optional[dict]:
        sql = self._get_sql()
        if not sql.available:
            return None
        conn = None
        try:
            sid = session_id or str(uuid.uuid4())
            now = datetime.utcnow().isoformat() + "Z"
            conn = sql._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_sessions (id, user_id, title, message_count, created_at, updated_at) VALUES (?,?,?,0,GETUTCDATE(),GETUTCDATE())",
                sid, user_id, title,
            )
            conn.commit()
            return {"id": sid, "user_id": user_id, "title": title, "message_count": 0, "created_at": now, "updated_at": now}
        except Exception as e:
            if conn is not None:
                conn.rollback()
            logger.warning(f"Failed to create session: {e}")
            return None
        finally:
            if conn is not None:
                conn.close()

    def get_session(self, session_id: str, user_id: str) -> Optional[dict]:
        sql = self._get_sql()
        if not sql.available:
            return None
        conn = None
        try:
            conn = sql._get_connection()
            row = conn.cursor().execute(
                "SELECT id, title, message_count FROM chat_sessions WHERE id = ? AND user_id = ?",
                session_id, user_id,
            ).fetchone()
            return {"id": row[0], "title": row[1], "message_count": row[2]} if row else None
        except Exception:
            logger.exception("Failed to read chat session")
            raise
        finally:
            if conn is not None:
                conn.close()

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
        conn = None
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
            params.extend([session_id, user_id])
            cursor.execute(f"UPDATE chat_sessions SET {', '.join(sets)} WHERE id = ? AND user_id = ?", *params)
            updated = cursor.rowcount > 0
            conn.commit()
            return updated
        except Exception:
            if conn is not None:
                conn.rollback()
            logger.exception("Failed to update chat session")
            raise
        finally:
            if conn is not None:
                conn.close()

    def delete_session(self, session_id: str, user_id: str) -> bool:
        sql = self._get_sql()
        if not sql.available:
            return False
        conn = None
        try:
            conn = sql._get_connection()
            cursor = conn.cursor()
            # Hold ownership through the message mutation and commit.
            if not cursor.execute(
                "SELECT id FROM chat_sessions WITH (UPDLOCK, HOLDLOCK) WHERE id = ? AND user_id = ?",
                session_id, user_id,
            ).fetchone():
                conn.rollback()
                return False
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", session_id)
            cursor.execute("DELETE FROM chat_sessions WHERE id = ? AND user_id = ?", session_id, user_id)
            conn.commit()
            return True
        except Exception:
            if conn is not None:
                conn.rollback()
            logger.exception("Failed to delete chat session")
            raise
        finally:
            if conn is not None:
                conn.close()

    # --- Messages ---

    def add_message(self, session_id: str, user_id: str, role: str, content: str, sources: Optional[list] = None) -> Optional[dict]:
        sql = self._get_sql()
        if not sql.available:
            return None
        conn = None
        try:
            msg_id = str(uuid.uuid4())
            conn = sql._get_connection()
            cursor = conn.cursor()
            if not cursor.execute(
                "SELECT id FROM chat_sessions WITH (UPDLOCK, HOLDLOCK) WHERE id = ? AND user_id = ?",
                session_id, user_id,
            ).fetchone():
                conn.rollback()
                return None
            cursor.execute(
                "INSERT INTO chat_messages (id, session_id, role, content, sources) VALUES (?,?,?,?,?)",
                msg_id, session_id, role, content, json.dumps(sources or []),
            )
            conn.commit()
            return {"id": msg_id, "session_id": session_id, "role": role, "content": content}
        except Exception:
            if conn is not None:
                conn.rollback()
            logger.exception("Failed to add chat message")
            raise
        finally:
            if conn is not None:
                conn.close()

    def get_messages(self, session_id: str, user_id: str) -> list[dict]:
        sql = self._get_sql()
        if not sql.available:
            return []
        conn = None
        try:
            conn = sql._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                # save_messages_bulk writes a whole session at once, so timestamps can tie; sort_order keeps the order.
                "SELECT m.id, m.role, m.content, m.sources, m.timestamp "
                "FROM chat_messages m INNER JOIN chat_sessions s ON s.id = m.session_id "
                "WHERE s.id = ? AND s.user_id = ? ORDER BY m.sort_order ASC, m.timestamp ASC",
                session_id, user_id,
            )
            rows = cursor.fetchall()
            return [{
                "id": r[0], "role": r[1], "content": r[2],
                "sources": json.loads(r[3]) if r[3] else [],
                "timestamp": str(r[4]),
            } for r in rows]
        except Exception:
            logger.exception("Failed to get chat messages")
            raise
        finally:
            if conn is not None:
                conn.close()

    def save_messages_bulk(self, session_id: str, messages: list[dict], user_id: str,
                           title: Optional[str] = None) -> bool:
        sql = self._get_sql()
        if not sql.available:
            return False
        conn = None
        try:
            conn = sql._get_connection()
            cursor = conn.cursor()
            if not cursor.execute(
                "SELECT id FROM chat_sessions WITH (UPDLOCK, HOLDLOCK) WHERE id = ? AND user_id = ?",
                session_id, user_id,
            ).fetchone():
                conn.rollback()
                return False
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", session_id)
            for i, msg in enumerate(messages):
                cursor.execute(
                    "INSERT INTO chat_messages (id, session_id, role, content, sources, sort_order) VALUES (?,?,?,?,?,?)",
                    str(uuid.uuid4()), session_id, msg.get("role", "user"),
                    msg.get("content", ""), json.dumps(msg.get("sources", [])), i,
                )
            cursor.execute(
                "UPDATE chat_sessions SET title = COALESCE(?, title), message_count = ?, "
                "updated_at = GETUTCDATE() WHERE id = ? AND user_id = ?",
                title, len(messages), session_id, user_id,
            )
            conn.commit()
            return True
        except Exception:
            if conn is not None:
                conn.rollback()
            logger.exception("Failed to save chat messages")
            raise
        finally:
            if conn is not None:
                conn.close()


chat_store = ChatStore()
