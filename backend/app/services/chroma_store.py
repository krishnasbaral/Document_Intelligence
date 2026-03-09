import logging
from functools import lru_cache

import chromadb
import re
from app.settings import settings
from app.llm_client import get_azure_client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def chroma_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=settings.CHROMA_ROOT)


# ---------------------------------------------------------------------------
# Azure embedding function (Chroma-compatible callable)
# ---------------------------------------------------------------------------

class AzureEmbeddingFunction:
    def __init__(self):
        self.client, _ = get_azure_client()

    def __call__(self, input):  # noqa: A002 — Chroma expects `input`
        response = self.client.embeddings.create(
            model=settings.AZURE_EMBEDDING_DEPLOYMENT,
            input=input,
        )
        return [d.embedding for d in response.data]


# ---------------------------------------------------------------------------
# Collection accessors
# ---------------------------------------------------------------------------

# Use a plain dict so we can invalidate if needed (lru_cache can't be
# selectively cleared per key).
_persistent_cache: dict[str, chromadb.Collection] = {}




def invalidate_persistent_collection(name: str) -> None:
    """Call after any destructive operation on a persistent collection."""
    _persistent_cache.pop(name, None)


def get_persistent_collection(name: str) -> chromadb.Collection:
    safe_name = _sanitize_collection_name(name)
    if safe_name not in _persistent_cache:
        _persistent_cache[safe_name] = chroma_client().get_or_create_collection(
            safe_name,
            embedding_function=AzureEmbeddingFunction(),
        )
    return _persistent_cache[safe_name]


def get_workspace_collection(workspace_id: str) -> chromadb.Collection:
    name = f"temp__{workspace_id}"
    return chroma_client().get_or_create_collection(
        name,
        embedding_function=AzureEmbeddingFunction(),
    )
def _sanitize_collection_name(name: str) -> str:
    """Replace spaces and invalid chars with underscores for Chroma compatibility."""
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    # Collapse consecutive underscores and strip leading/trailing
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized or "default"