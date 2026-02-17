# backend/app/rag/retrieve.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from backend.app.rag.store import get_collection

from openai import OpenAI

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")


def embed_query(query: str) -> List[float]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.embeddings.create(model=EMBED_MODEL, input=[query])
    return resp.data[0].embedding


def retrieve(
    query: str,
    top_k: int = 6,
    persist_dir: Optional[str] = None,
    collection_name: str = "grant_library",
) -> str:
    """
    Returns a single string of top_k snippets + citations.
    Reads from the persisted vector store on disk.
    """
    query = (query or "").strip()
    if not query:
        return ""

    col = get_collection(persist_dir=persist_dir, collection_name=collection_name)

    q_emb = embed_query(query)
    res = col.query(
        query_embeddings=[q_emb],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    parts: List[str] = []
    for i, (d, m) in enumerate(zip(docs, metas), start=1):
        source = (m or {}).get("source", "unknown")
        chunk_index = (m or {}).get("chunk_index", "—")
        parts.append(
            f"[{i}] Source: {source} (chunk {chunk_index})\n{(d or '').strip()}"
        )

    return "\n\n---\n\n".join(parts)
