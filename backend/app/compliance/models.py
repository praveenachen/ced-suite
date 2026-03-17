from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["minor", "major", "critical"]
PriorityLevel = Literal["core", "secondary", "low_priority"]


class SourceManifestEntry(BaseModel):
    filename: str
    canonical_title: str
    short_description: str
    priority_level: PriorityLevel
    document_type: str
    community_scope: List[str]
    framework_tags: List[str]
    section_tags: List[str]
    include_in_primary_retrieval: bool


class SourceChunk(BaseModel):
    chunk_id: str
    title: str
    brief_description: str
    source_document: str
    document_type: str
    priority_level: PriorityLevel
    chunk_text: str
    section_tags: List[str]
    community_scope: List[str]
    framework_tags: List[str]
    year_if_known: Optional[int] = None
    page_number_if_known: Optional[int] = None


class ComplianceCheck(BaseModel):
    check_id: str
    title: str
    section: str
    category: str
    check_text: str
    explanation: str
    failure_signals: List[str]
    evidence_examples: List[str]
    severity_if_failed: Severity
    framework_tags: List[str]
    community_scope: List[str]
    source_document: str
    source_section: str
    source_excerpt: str
    priority_weight: float = Field(default=1.0, ge=0)


class WarningEntry(BaseModel):
    type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ComplianceGap(BaseModel):
    failed_check_id: str
    category: str
    severity: Severity
    confidence_score: int = Field(ge=0, le=100)
    message: str
    recommendation: str
    source_excerpt: str
    source_document: str


class ComplianceEvaluationRequest(BaseModel):
    section_name: str
    section_text: Optional[str] = ""


class ComplianceEvaluationResponse(BaseModel):
    section: str
    warnings: List[WarningEntry]
    compliance_gaps: List[ComplianceGap]
    scoring_hooks: Optional[Dict[str, Any]] = None


class ProposalSectionInput(BaseModel):
    section_name: str
    section_text: str


class ProposalEvaluationRequest(BaseModel):
    sections: List[ProposalSectionInput] = Field(default_factory=list)
    source_file_name: Optional[str] = None
    source_file_type: Optional[Literal["pdf", "docx"]] = None


class ProposalEvaluationResponse(BaseModel):
    status: Literal["scaffolded"] = "scaffolded"
    message: str
    todo: List[str]


class GuardrailMatch(BaseModel):
    category: str
    match_text: str
    replacement: str
    start: int
    end: int


class GuardrailResult(BaseModel):
    sanitized_text: str
    warnings: List[WarningEntry] = Field(default_factory=list)
    redaction_log: List[GuardrailMatch] = Field(default_factory=list)
    blocked: bool = False


class RetrievedContext(BaseModel):
    checks: List[ComplianceCheck]
    excerpts: List[SourceChunk]


class SectionContext(BaseModel):
    section_name: str
    section_text: str
    normalized_section: str
    section_tags: List[str]
    community_scope: List[str]
    framework_tags: List[str]
    is_inuit_specific: bool = False


class ScoringResult(BaseModel):
    overall_score: int
    dimensions: Dict[str, int]
