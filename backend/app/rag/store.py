# backend/app/rag/store.py
from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings


DEFAULT_COLLECTION = "grant_library"


@dataclass
class VectorStoreConfig:
    persist_dir: str
    collection_name: str = DEFAULT_COLLECTION


def get_default_persist_dir() -> str:
    # .../backend/app/data/app_library/vector_store
    here = os.path.dirname(os.path.abspath(__file__))
    backend_app_dir = os.path.abspath(os.path.join(here, ".."))  # backend/app
    return os.path.join(backend_app_dir, "data", "app_library", "vector_store")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_client(persist_dir: Optional[str] = None) -> chromadb.ClientAPI:
    persist_dir = persist_dir or get_default_persist_dir()
    _ensure_dir(persist_dir)
    return chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection(
    persist_dir: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION,
) -> chromadb.Collection:
    client = get_client(persist_dir=persist_dir)
    # Create if missing, otherwise load
    return client.get_or_create_collection(name=collection_name)


def stable_id(text: str, source: str = "") -> str:
    # deterministic id so re-ingesting the same chunk will overwrite instead of duplicating
    h = hashlib.sha256()
    h.update(source.encode("utf-8"))
    h.update(b"||")
    h.update(text.encode("utf-8"))
    return h.hexdigest()
