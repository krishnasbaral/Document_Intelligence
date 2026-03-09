import os
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _split_csv(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    # --- Azure OpenAI ---
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    AZURE_DEPLOYMENT_NAME: str = os.getenv("AZURE_DEPLOYMENT_NAME", "")
    AZURE_EMBEDDING_DEPLOYMENT: str = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "")
    LLAMA_CLOUD_API_KEY: str = os.getenv("LLAMA_CLOUD_API_KEY", "")

    # --- Retrieval tuning ---
    HYBRID_ALPHA: float = float(os.getenv("HYBRID_ALPHA", "0.7"))
    BM25_TOP: int = int(os.getenv("BM25_TOP", "5"))
    VEC_TOP: int = int(os.getenv("VEC_TOP", "5"))

    # --- Chunking ---
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "512"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

    # --- Storage paths ---
    CHROMA_ROOT: str = os.getenv("CHROMA_ROOT", "./chroma_data")
    BM25_SQLITE_PATH: str = os.getenv("BM25_SQLITE_PATH", "./bm25.sqlite")
    CSV_FILE_PATH: str = os.getenv("CSV_FILE_PATH", "./record_results.csv")
    CONVERSATIONS_DB_PATH: str = os.getenv("CONVERSATIONS_DB_PATH", "./conversations.sqlite")
    FEEDBACK_DB_PATH: str = os.getenv("FEEDBACK_DB_PATH", "./feedback.sqlite")

    # --- Auth ---
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    USERS_FILE: str = os.getenv("USERS_FILE", "./users.json")

    # --- Collections ---
    COLLECTIONS: list[str] = field(
        default_factory=lambda: _split_csv(os.getenv("COLLECTIONS", ""))
    )

    # --- Prompts ---
    QA_PROMPT_STR: str = os.getenv(
        "QA_PROMPT_STR",
        "User Question: {query_str}\n\nDocument Content: {context_str}\n\nAI Response:",
    )
    LLM_INSTRUCTION: str = os.getenv(
        "LLM_INSTRUCTION", "Answer only from context."
    )

    # --- CORS (comma-separated origins, or * for dev) ---
    ALLOWED_ORIGINS: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
        )
    )

    def validate(self) -> None:
        """Run startup checks — call once in main.py lifespan."""
        errors: list[str] = []

        if self.JWT_SECRET in ("change_me", ""):
            errors.append(
                "JWT_SECRET is not set or still default. "
                "Set a strong random secret in .env before deploying."
            )

        if not self.AZURE_OPENAI_API_KEY:
            errors.append("AZURE_OPENAI_API_KEY is missing.")

        if not self.AZURE_OPENAI_ENDPOINT:
            errors.append("AZURE_OPENAI_ENDPOINT is missing.")

        if not self.AZURE_DEPLOYMENT_NAME:
            errors.append("AZURE_DEPLOYMENT_NAME is missing.")

        if not self.COLLECTIONS:
            logger.warning("COLLECTIONS is empty — no persistent collections configured.")

        for msg in errors:
            logger.error("CONFIG ERROR: %s", msg)

        if errors:
            raise SystemExit(
                f"Startup aborted — {len(errors)} config error(s). Check logs above."
            )


settings = Settings()
