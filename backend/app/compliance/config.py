from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
SOURCE_DOCS_DIR = DATA_DIR / "source_docs"
PROCESSED_DIR = DATA_DIR / "processed"
MANIFEST_PATH = PROCESSED_DIR / "manifests" / "source_manifest.json"
CHUNKS_PATH = PROCESSED_DIR / "chunks" / "source_chunks.json"
CHECKS_PATH = PROCESSED_DIR / "compliance_checks" / "checks.json"
PROPOSAL_ANALYSIS_DIR = PROCESSED_DIR / "proposal_analyses"


class WarningThresholds(BaseModel):
    min_words: int = 60
    max_words: int = 500


class GuardrailConfig(BaseModel):
    redact_before_llm: bool = True
    block_external_llm_on_sensitive_content: bool = False


class RetrievalConfig(BaseModel):
    checks_top_k: int = Field(default=4, ge=1, le=6)
    excerpts_top_k: int = Field(default=2, ge=1, le=3)


class ComplianceConfig(BaseModel):
    warning_thresholds: WarningThresholds = WarningThresholds()
    guardrails: GuardrailConfig = GuardrailConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
