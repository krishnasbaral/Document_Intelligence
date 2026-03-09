import logging
from typing import List, Dict, Any

from app.settings import settings
from app.services.chroma_store import (
    get_persistent_collection,
    get_workspace_collection,
    _sanitize_collection_name,
)
from app.services.bm25_sqlite import BM25SQLite

logger = logging.getLogger(__name__)


def _vector_query(col, query: str, top_k: int):
    """Return (ids, id→score dict) from Chroma vector search."""
    vec = col.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    ids = vec.get("ids", [[]])[0]
    dists = vec.get("distances", [[]])[0]
    scores = {_id: 1.0 / (1.0 + float(dist)) for _id, dist in zip(ids, dists)}
    return ids, scores


def hybrid_retrieve_persistent(
    collection_name: str,
    query: str,
    bm25: BM25SQLite,
) -> List[Dict[str, Any]]:
    """Hybrid BM25 + vector retrieval for persistent collections."""
    col = get_persistent_collection(collection_name)
    # Sanitize so BM25 and Chroma always use the same key (e.g. "HR_Team" not "HR Team")
    safe_name = _sanitize_collection_name(collection_name)

    # --- Vector leg ---
    _, vec_scores = _vector_query(col, query, settings.VEC_TOP)

    # --- BM25 leg ---
    bm = bm25.search(safe_name, query, top_k=settings.BM25_TOP)
    bm_scores = {doc_id: score for doc_id, score in bm}
    max_bm = max(bm_scores.values(), default=1.0) or 1.0
    bm_scores = {k: v / max_bm for k, v in bm_scores.items()}

    # --- Combine ---
    alpha = settings.HYBRID_ALPHA
    combined: Dict[str, float] = {}
    for k, v in bm_scores.items():
        combined[k] = combined.get(k, 0.0) + (1 - alpha) * v
    for k, v in vec_scores.items():
        combined[k] = combined.get(k, 0.0) + alpha * v

    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    top_n = max(settings.BM25_TOP, settings.VEC_TOP)
    top_ids = [doc_id for doc_id, _ in ranked[:top_n]]

    # --- Hydrate texts + metadata ---
    texts = bm25.get_texts(safe_name, top_ids)
    got = col.get(ids=top_ids, include=["metadatas"])
    id_to_meta = dict(zip(got.get("ids", []), got.get("metadatas", [])))

    return [
        {
            "id": doc_id,
            "score": score,
            "text": texts.get(doc_id, ""),
            "metadata": id_to_meta.get(doc_id, {}),
        }
        for doc_id, score in ranked[:top_n]
    ]


def retrieve_workspace(workspace_id: str, query: str) -> List[Dict[str, Any]]:
    """Vector-only retrieval for temporary workspaces."""
    col = get_workspace_collection(workspace_id)
    vec = col.query(
        query_texts=[query],
        n_results=6,
        include=["documents", "metadatas", "distances"],
    )
    ids = vec.get("ids", [[]])[0]
    docs = vec.get("documents", [[]])[0]
    metas = vec.get("metadatas", [[]])[0]
    dists = vec.get("distances", [[]])[0]

    return [
        {
            "id": _id,
            "score": 1.0 / (1.0 + float(dist)),
            "text": text,
            "metadata": meta or {},
        }
        for _id, text, meta, dist in zip(ids, docs, metas, dists)
    ]