import sqlite3
import math
import re
import logging
from typing import List, Tuple, Dict

_WORD = re.compile(r"[A-Za-z0-9]+")

logger = logging.getLogger(__name__)


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _WORD.findall(text)]


class BM25SQLite:
    """Lightweight BM25 index backed by a single SQLite file."""

    def __init__(self, path: str):
        self.path = path
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _conn(self):
        return sqlite3.connect(self.path)

    def _init_db(self):
        con = self._conn()
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                collection TEXT NOT NULL,
                doc_id     TEXT NOT NULL,
                source     TEXT,
                length     INTEGER NOT NULL,
                text       TEXT NOT NULL,
                PRIMARY KEY (collection, doc_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS terms (
                collection TEXT NOT NULL,
                term       TEXT NOT NULL,
                df         INTEGER NOT NULL,
                PRIMARY KEY (collection, term)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS postings (
                collection TEXT NOT NULL,
                term       TEXT NOT NULL,
                doc_id     TEXT NOT NULL,
                tf         INTEGER NOT NULL,
                PRIMARY KEY (collection, term, doc_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                collection TEXT PRIMARY KEY,
                doc_count  INTEGER NOT NULL,
                avgdl      REAL NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_postings_lookup "
            "ON postings(collection, term)"
        )
        con.commit()
        con.close()

    def _recompute_stats(self, collection: str):
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            "SELECT COUNT(*), COALESCE(AVG(length), 0) FROM docs WHERE collection=?",
            (collection,),
        )
        n, avgdl = cur.fetchone()
        cur.execute(
            """
            INSERT INTO stats(collection, doc_count, avgdl)
            VALUES(?,?,?)
            ON CONFLICT(collection)
            DO UPDATE SET doc_count=excluded.doc_count, avgdl=excluded.avgdl
            """,
            (collection, int(n), float(avgdl)),
        )
        con.commit()
        con.close()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def upsert_document(
        self,
        collection: str,
        doc_id: str,
        text: str,
        source: str | None = None,
    ):
        tokens = tokenize(text)
        length = len(tokens)
        tf: Dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        con = self._conn()
        cur = con.cursor()

        # Remove old version first
        self.delete_document(collection, doc_id, _existing_conn=con, _skip_commit=True)

        cur.execute(
            "INSERT INTO docs(collection, doc_id, source, length, text) VALUES(?,?,?,?,?)",
            (collection, doc_id, source, length, text),
        )

        for term, freq in tf.items():
            cur.execute(
                "INSERT INTO postings(collection, term, doc_id, tf) VALUES(?,?,?,?)",
                (collection, term, doc_id, freq),
            )
            cur.execute(
                "SELECT df FROM terms WHERE collection=? AND term=?",
                (collection, term),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE terms SET df=df+1 WHERE collection=? AND term=?",
                    (collection, term),
                )
            else:
                cur.execute(
                    "INSERT INTO terms(collection, term, df) VALUES(?,?,1)",
                    (collection, term),
                )

        con.commit()
        con.close()
        self._recompute_stats(collection)

    def delete_document(
        self,
        collection: str,
        doc_id: str,
        _existing_conn=None,
        _skip_commit=False,
    ):
        con = _existing_conn or self._conn()
        cur = con.cursor()

        cur.execute(
            "SELECT term FROM postings WHERE collection=? AND doc_id=?",
            (collection, doc_id),
        )
        terms = [r[0] for r in cur.fetchall()]

        cur.execute(
            "DELETE FROM postings WHERE collection=? AND doc_id=?",
            (collection, doc_id),
        )
        cur.execute(
            "DELETE FROM docs WHERE collection=? AND doc_id=?",
            (collection, doc_id),
        )

        for term in set(terms):
            cur.execute(
                "UPDATE terms SET df=df-1 WHERE collection=? AND term=?",
                (collection, term),
            )
            cur.execute(
                "DELETE FROM terms WHERE collection=? AND term=? AND df<=0",
                (collection, term),
            )

        if not _skip_commit:
            con.commit()
        if _existing_conn is None:
            con.close()
            self._recompute_stats(collection)

    def delete_by_source(self, collection: str, source: str):
        con = self._conn()
        cur = con.cursor()
        cur.execute(
            "SELECT doc_id FROM docs WHERE collection=? AND source=?",
            (collection, source),
        )
        ids = [r[0] for r in cur.fetchall()]
        con.close()
        for doc_id in ids:
            self.delete_document(collection, doc_id)
        self._recompute_stats(collection)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, collection: str, query: str, top_k: int) -> List[Tuple[str, float]]:
        k1 = 1.5
        b = 0.75

        q_terms = tokenize(query)
        if not q_terms:
            return []

        con = self._conn()
        cur = con.cursor()

        cur.execute(
            "SELECT doc_count, avgdl FROM stats WHERE collection=?",
            (collection,),
        )
        row = cur.fetchone()
        if not row or row[0] == 0:
            con.close()
            return []
        N, avgdl = int(row[0]), float(row[1])

        scores: Dict[str, float] = {}
        for term in set(q_terms):
            cur.execute(
                "SELECT df FROM terms WHERE collection=? AND term=?",
                (collection, term),
            )
            r = cur.fetchone()
            if not r:
                continue
            df = int(r[0])
            idf = math.log(1 + (N - df + 0.5) / (df + 0.5))

            cur.execute(
                """
                SELECT p.doc_id, p.tf, d.length
                FROM postings p
                JOIN docs d ON d.collection = p.collection AND d.doc_id = p.doc_id
                WHERE p.collection = ? AND p.term = ?
                """,
                (collection, term),
            )
            for doc_id, tf_val, dl in cur.fetchall():
                tf_val = int(tf_val)
                dl = int(dl)
                denom = tf_val + k1 * (1 - b + b * (dl / (avgdl or 1.0)))
                score = idf * (tf_val * (k1 + 1) / (denom or 1.0))
                scores[doc_id] = scores.get(doc_id, 0.0) + score

        con.close()
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    def get_texts(self, collection: str, doc_ids: List[str]) -> Dict[str, str]:
        if not doc_ids:
            return {}
        con = self._conn()
        cur = con.cursor()
        qmarks = ",".join(["?"] * len(doc_ids))
        cur.execute(
            f"SELECT doc_id, text FROM docs "
            f"WHERE collection=? AND doc_id IN ({qmarks})",
            [collection, *doc_ids],
        )
        out = {doc_id: text for doc_id, text in cur.fetchall()}
        con.close()
        return out
