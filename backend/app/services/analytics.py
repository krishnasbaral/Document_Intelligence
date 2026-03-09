import os
import logging
import threading
from datetime import datetime

import pandas as pd

from app.settings import settings

logger = logging.getLogger(__name__)

_csv_lock = threading.Lock()

_CSV_COLUMNS = ["Timestamp", "Database", "Question", "Context", "Response", "Metadata"]


def append_to_csv(
    database: str,
    question: str,
    context_str: str,
    response: str,
    metadata: str,
) -> None:
    """Append a single analytics row. Thread-safe, append-mode (no full re-read)."""
    row = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Database": database,
        "Question": question,
        "Context": context_str,
        "Response": response,
        "Metadata": metadata,
    }
    path = settings.CSV_FILE_PATH

    with _csv_lock:
        try:
            write_header = not os.path.exists(path) or os.path.getsize(path) == 0
            df = pd.DataFrame([row], columns=_CSV_COLUMNS)
            df.to_csv(path, mode="a", header=write_header, index=False)
        except Exception:
            logger.exception("Failed to write analytics row")
