from __future__ import annotations

import re

DEFAULT_USE_CASE = "default"
DEFAULT_COLLECTION = "grant_library"


def normalize_use_case(use_case: str | None) -> str:
    raw = (use_case or "").strip().lower()
    if not raw:
        return DEFAULT_USE_CASE
    cleaned = re.sub(r"[^a-z0-9_\-]+", "_", raw).strip("_")
    return cleaned or DEFAULT_USE_CASE


def collection_for_use_case(use_case: str | None, base_collection: str = DEFAULT_COLLECTION) -> str:
    uc = normalize_use_case(use_case)
    if uc == DEFAULT_USE_CASE:
        return base_collection
    return f"{base_collection}_{uc}"

