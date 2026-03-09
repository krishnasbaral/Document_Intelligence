import sqlite3
import uuid
import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class FeedbackStore:
    """
    Stores user feedback (thumbs up/down) on AI responses.
    Each record captures everything needed for quality analysis:
    query, answer, retrieved chunks, collection, user context, and rating.
    """

    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        con = self._conn()
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id                  TEXT PRIMARY KEY,
                conversation_id     TEXT,
                query               TEXT NOT NULL,
                answer              TEXT NOT NULL,
                sources             TEXT,       -- JSON: top retrieved chunks [{id, source, score}]
                collection          TEXT,       -- persistent collection name or NULL for workspace
                workspace_id        TEXT,       -- workspace id or NULL for collection
                username            TEXT NOT NULL,
                role                TEXT NOT NULL,
                allowed_collections TEXT,       -- JSON list or NULL (all access)
                rating              TEXT NOT NULL CHECK(rating IN ('up', 'down')),
                created_at          TEXT NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_user "
            "ON feedback(username, created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_collection "
            "ON feedback(collection, rating, created_at DESC)"
        )
        con.commit()
        con.close()
        logger.info("FeedbackStore initialized at %s", self.path)

    def add_feedback(
        self,
        query: str,
        answer: str,
        rating: str,                        # "up" or "down"
        username: str,
        role: str,
        sources: Optional[List[Dict]]   = None,
        collection: Optional[str]       = None,
        workspace_id: Optional[str]     = None,
        conversation_id: Optional[str]  = None,
        allowed_collections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        now      = datetime.utcnow().isoformat()
        fb_id    = uuid.uuid4().hex
        con      = self._conn()
        cur      = con.cursor()
        cur.execute(
            """
            INSERT INTO feedback
              (id, conversation_id, query, answer, sources, collection,
               workspace_id, username, role, allowed_collections, rating, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fb_id,
                conversation_id,
                query,
                answer,
                json.dumps(sources) if sources else None,
                collection,
                workspace_id,
                username,
                role,
                json.dumps(allowed_collections) if allowed_collections else None,
                rating,
                now,
            ),
        )
        con.commit()
        con.close()
        logger.info(
            "Feedback [%s] from %s on collection=%s", rating, username, collection
        )
        return {"id": fb_id, "rating": rating, "created_at": now}

    def get_feedback(
        self,
        collection: Optional[str] = None,
        username: Optional[str]   = None,
        rating: Optional[str]     = None,
        limit: int                = 100,
    ) -> List[Dict[str, Any]]:
        """Admin reporting — filter by collection, user, or rating."""
        con  = self._conn()
        cur  = con.cursor()
        where, params = [], []
        if collection:
            where.append("collection = ?"); params.append(collection)
        if username:
            where.append("username = ?");   params.append(username)
        if rating:
            where.append("rating = ?");     params.append(rating)
        sql = "SELECT * FROM feedback"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cur.execute(sql, params)
        rows = cur.fetchall()
        con.close()
        return [dict(r) for r in rows]
