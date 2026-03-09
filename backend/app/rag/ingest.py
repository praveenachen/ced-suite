# backend/app/rag/ingest.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from backend.app.rag.store import get_collection, stable_id

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    """
    Simple char-based chunker. Good enough for demo; can swap later for token chunking.
    """
    text = (text or "").strip()
    if not text:
        return []

    chunks: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + chunk_size)
        chunk = text[i:j].strip()
        if chunk:
            chunks.append(chunk)
        i = max(j - overlap, j)  # overlap
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [r.embedding for r in resp.data]


def ingest_folder(
    library_dir: str,
    persist_dir: Optional[str] = None,
    collection_name: str = "grant_library",
    reset: bool = False,
    source_tag: Optional[str] = None,
    use_case: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Ingests ALL .txt files in library_dir into a persisted Chroma collection.
    - Persists on disk (persist_dir or default from store.py).
    - Uses stable_id(text, source) so re-ingesting doesn't duplicate.
    - If reset=True, clears collection first.
    """
    lib = Path(library_dir)
    lib.mkdir(parents=True, exist_ok=True)

    col = get_collection(persist_dir=persist_dir, collection_name=collection_name)

    if reset:
        # wipe collection for a clean rebuild
        try:
            col.delete(where={})
        except Exception:
            # older chroma versions sometimes require explicit ids; fallback: recreate collection
            pass

    files = sorted([p for p in lib.rglob("*") if p.is_file() and p.suffix.lower() == ".txt"])

    total_chunks = 0
    added = 0

    for fp in files:
        raw = _read_text_file(fp)
        chunks = chunk_text(raw)

        if not chunks:
            continue

        embeddings = embed_texts(chunks)

        ids: List[str] = []
        metas: List[Dict] = []
        for idx, chunk in enumerate(chunks):
            source = str(fp.relative_to(lib)).replace("\\", "/")
            ids.append(stable_id(chunk, source=source))
            meta: Dict[str, Any] = {"source": source, "chunk_index": idx}
            if source_tag:
                meta["source_tag"] = source_tag
            if use_case:
                meta["use_case"] = use_case
            if extra_metadata:
                meta.update(extra_metadata)
            metas.append(meta)

        # Upsert-like behavior via deterministic IDs:
        # If IDs already exist, Chroma will overwrite or ignore depending on version;
        # deterministic IDs prevents duplicates in either case.
        col.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metas,
        )

        total_chunks += len(chunks)
        added += len(chunks)

    return {"files": len(files), "chunks": total_chunks, "added": added}
