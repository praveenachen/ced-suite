from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Type, TypeVar

from pydantic import TypeAdapter

from backend.app.compliance.config import CHECKS_PATH, CHUNKS_PATH, MANIFEST_PATH
from backend.app.compliance.models import ComplianceCheck, SourceChunk, SourceManifestEntry

T = TypeVar("T")


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_typed_list(path: Path, model_type: Type[T]) -> List[T]:
    payload = _load_json(path)
    return TypeAdapter(List[model_type]).validate_python(payload)


@lru_cache(maxsize=1)
def load_manifest() -> List[SourceManifestEntry]:
    return _load_typed_list(MANIFEST_PATH, SourceManifestEntry)


@lru_cache(maxsize=1)
def load_chunks() -> List[SourceChunk]:
    return _load_typed_list(CHUNKS_PATH, SourceChunk)


@lru_cache(maxsize=1)
def load_checks() -> List[ComplianceCheck]:
    return _load_typed_list(CHECKS_PATH, ComplianceCheck)
