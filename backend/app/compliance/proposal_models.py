from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.app.compliance.models import ComplianceGap, WarningEntry


MetricSeverity = Literal["success", "info", "warning", "critical"]
MetricAnchorType = Literal["text", "paragraph", "section"]


class ProposalSection(BaseModel):
    key: str
    title: str
    body: str
    order: int
    word_limit: Optional[int] = None
    issues_count: int = 0
    warnings: List[WarningEntry] = Field(default_factory=list)
    compliance_gaps: List[ComplianceGap] = Field(default_factory=list)
    section_score: int = 0


class MetricIssue(BaseModel):
    issue_id: str
    title: str
    message: str
    severity: MetricSeverity
    confidence_score: int = Field(ge=0, le=100)
    section_key: str
    anchor_type: MetricAnchorType = "section"
    anchor_text: Optional[str] = None
    anchor_hint: Optional[str] = None
    affected_sections: List[str] = Field(default_factory=list)
    excerpt: Optional[str] = None
    recommendation: str


class MetricResult(BaseModel):
    id: str
    label: str
    category_id: str
    description: str
    score: int = Field(ge=0, le=100)
    issues_count: int = 0
    status: str
    summary: str
    issues: List[MetricIssue] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    linked_sections: List[str] = Field(default_factory=list)


class MetricCategoryResult(BaseModel):
    id: str
    label: str
    score: int = Field(ge=0, le=100)
    issues: int = 0
    metrics: List[MetricResult] = Field(default_factory=list)


class AnalysisHeader(BaseModel):
    proposal_id: str
    file_name: str
    file_type: Literal["pdf", "docx"]
    uploaded_at: datetime
    last_analyzed_at: datetime


class ProposalExtractionDiagnostics(BaseModel):
    extractor: str
    confidence: Literal["high", "medium", "low"]
    preview_mode: Literal["sectioned", "continuous"]
    raw_text_length: int = 0
    cleaned_text_length: int = 0
    section_count: int = 0
    numbering_gaps_detected: bool = False
    warnings: List[str] = Field(default_factory=list)
    candidate_extractors: List[Dict[str, str | int | float]] = Field(default_factory=list)


class ProposalAnalysisResponse(BaseModel):
    analysis: AnalysisHeader
    extraction: ProposalExtractionDiagnostics
    overall_score: int = Field(ge=0, le=100)
    issue_count: int = 0
    categories: List[MetricCategoryResult] = Field(default_factory=list)
    sections: List[ProposalSection] = Field(default_factory=list)
    additional_submission_requirements: List[str] = Field(default_factory=list)
    assistant_starters: List[str] = Field(default_factory=list)
    raw_preview_text: str = ""
    report_summary: str


class ProposalSectionRewriteRequest(BaseModel):
    proposal_id: str
    section_key: str
    instruction: str
    metric_id: Optional[str] = None
    issue_id: Optional[str] = None
    issue_message: Optional[str] = None
    issue_recommendation: Optional[str] = None


class ProposalReanalyzeRequest(BaseModel):
    proposal_id: str
    sections: List[ProposalSection]


class ProposalSectionRewriteResponse(BaseModel):
    proposal_id: str
    section_key: str
    rewritten_text: str
    rationale: str
    references: List[Dict[str, str | int | float | None]] = Field(default_factory=list)


class ProposalChatRequest(BaseModel):
    proposal_id: str
    message: str
    section_key: Optional[str] = None
    metric_id: Optional[str] = None


class ProposalChatResponse(BaseModel):
    proposal_id: str
    response: str
    suggested_actions: List[str] = Field(default_factory=list)
