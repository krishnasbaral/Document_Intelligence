import sqlite3
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConversationStore:
    """
    Stores chat conversations and messages in SQLite.
    Each conversation belongs to a user and optionally a collection or workspace.
    """

    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row  # allows dict-like access
        return conn

    def _init_db(self):
        con = self._conn()
        cur = con.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                username    TEXT NOT NULL,
                title       TEXT NOT NULL,
                collection  TEXT,
                workspace_id TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content         TEXT NOT NULL,
                sources         TEXT,        -- JSON blob of source citations
                created_at      TEXT NOT NULL
            )
        """)

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_user "
            "ON conversations(username, updated_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_conv "
            "ON messages(conversation_id, created_at ASC)"
        )

        # Enable foreign key enforcement
        cur.execute("PRAGMA foreign_keys = ON")
        con.commit()
        con.close()

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def create_conversation(
        self,
        username: str,
        title: str,
        collection: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        conv_id = uuid.uuid4().hex
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO conversations(id, username, title, collection, workspace_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (conv_id, username, title, collection, workspace_id, now, now),
        )
        con.commit()
        con.close()
        return self.get_conversation(conv_id)

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = cur.fetchone()
        con.close()
        return dict(row) if row else None

    def list_conversations(self, username: str) -> List[Dict[str, Any]]:
        """Return all conversations for a user, newest first."""
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            """
            SELECT c.*, 
                   (SELECT content FROM messages 
                    WHERE conversation_id = c.id 
                    ORDER BY created_at DESC LIMIT 1) AS last_message
            FROM conversations c
            WHERE username = ?
            ORDER BY updated_at DESC
            """,
            (username,),
        )
        rows = cur.fetchall()
        con.close()
        return [dict(r) for r in rows]

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )
        con.commit()
        con.close()

    def touch_conversation(self, conversation_id: str) -> None:
        """Update updated_at timestamp — called after each new message."""
        now = datetime.utcnow().isoformat()
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        con.commit()
        con.close()

    def delete_conversation(self, conversation_id: str) -> bool:
        con = self._conn()
        cur = con.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        deleted = cur.rowcount > 0
        con.commit()
        con.close()
        return deleted

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: Optional[str] = None,  # pass json.dumps(sources_list)
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        msg_id = uuid.uuid4().hex
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO messages(id, conversation_id, role, content, sources, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (msg_id, conversation_id, role, content, sources, now),
        )
        con.commit()
        con.close()
        self.touch_conversation(conversation_id)
        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "sources": sources,
            "created_at": now,
        }

    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Return all messages for a conversation, oldest first."""
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        rows = cur.fetchall()
        con.close()
        return [dict(r) for r in rows]

    def get_recent_messages(
        self, conversation_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return the last N messages for context window injection."""
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            """
            SELECT * FROM (
                SELECT * FROM messages 
                WHERE conversation_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ) ORDER BY created_at ASC
            """,
            (conversation_id, limit),
        )
        rows = cur.fetchall()
        con.close()
        return [dict(r) for r in rows]

    def verify_ownership(self, conversation_id: str, username: str) -> bool:
        """Check that a conversation belongs to the given user."""
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND username = ?",
            (conversation_id, username),
        )
        exists = cur.fetchone() is not None
        con.close()
        return exists
