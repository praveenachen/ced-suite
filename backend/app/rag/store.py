# backend/app/rag/store.py

# this is database creation 
from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings


# Collection names for dual knowledge bases
DEFAULT_COLLECTION = "grant_library"
QUANT_COLLECTION = "quant_data"

# Source types
SOURCE_APP_LIBRARY = "app_library"
SOURCE_QUANT_DATA = "quant_data"


@dataclass
class VectorStoreConfig:
    persist_dir: str
    collection_name: str = DEFAULT_COLLECTION


def get_default_persist_dir() -> str:
    # .../backend/app/data/app_library/vector_store
    here = os.path.dirname(os.path.abspath(__file__))
    backend_app_dir = os.path.abspath(os.path.join(here, ".."))  # backend/app
    return os.path.join(backend_app_dir, "data", "app_library", "vector_store")


def get_app_library_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    backend_app_dir = os.path.abspath(os.path.join(here, ".."))
    return os.path.join(backend_app_dir, "data", "app_library")


def get_quant_data_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    backend_app_dir = os.path.abspath(os.path.join(here, ".."))
    return os.path.join(backend_app_dir, "data", "quant_data")


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


def get_quant_collection(persist_dir: Optional[str] = None) -> chromadb.Collection:
    return get_collection(persist_dir=persist_dir, collection_name=QUANT_COLLECTION)


def stable_id(text: str, source: str = "") -> str:
    # deterministic id so re-ingesting the same chunk will overwrite instead of duplicating
    h = hashlib.sha256()
    h.update(source.encode("utf-8"))
    h.update(b"||")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def list_collections(persist_dir: Optional[str] = None) -> List[str]:
    client = get_client(persist_dir=persist_dir)
    collections = client.list_collections()
    return [c.name for c in collections]


def delete_collection(collection_name: str, persist_dir: Optional[str] = None) -> bool:
    try:
        client = get_client(persist_dir=persist_dir)
        client.delete_collection(name=collection_name)
        return True
    except Exception:
        return False


def get_collection_stats(
    collection_name: str = DEFAULT_COLLECTION,
    persist_dir: Optional[str] = None
) -> Dict[str, Any]:
    try:
        col = get_collection(persist_dir=persist_dir, collection_name=collection_name)
        count = col.count()
        return {
            "name": collection_name,
            "count": count,
            "exists": True
        }
    except Exception as e:
        return {
            "name": collection_name,
            "count": 0,
            "exists": False,
            "error": str(e)
        }
