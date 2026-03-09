import os
import tempfile
from typing import List

from llama_parse import LlamaParse
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter

from app.settings import settings


async def parse_with_llamaparse(file_bytes: bytes, filename: str) -> str:
    suffix = os.path.splitext(filename)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        parser = LlamaParse(
            api_key=settings.LLAMA_CLOUD_API_KEY,
            result_type="text",
            verbose=False,
            language="en",
            num_workers=2,
        )
        docs = await parser.aload_data([tmp_path])
        text = " ".join(d.text for d in docs if d.text and d.text.strip())
        if not text.strip():
            raise ValueError(f"LlamaParse returned no text for file: {filename}")
        return text
    finally:
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass


def chunk_text(text: str) -> List[str]:
    splitter = SentenceSplitter(
        chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP,
    )
    nodes = splitter.get_nodes_from_documents([Document(text=text)])
    return [n.text for n in nodes if n.text and n.text.strip()]


def build_chunk_ids(file_name: str, n: int) -> List[str]:
    base = os.path.basename(file_name)
    return [f"{base}__{i + 1}" for i in range(n)]