from __future__ import annotations
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from backend.app.compliance.config import PROPOSAL_ANALYSIS_DIR
from backend.app.compliance.document_processing import (
    extract_pdf_text_with_diagnostics,
    extract_text_from_docx,
)
from backend.app.compliance.models import ComplianceEvaluationRequest, WarningEntry
from backend.app.compliance.proposal_models import (
    AnalysisHeader,
    MetricCategoryResult,
    MetricIssue,
    MetricResult,
    ProposalAnalysisResponse,
    ProposalChatResponse,
    ProposalExtractionDiagnostics,
    ProposalSection,
    ProposalSectionRewriteResponse,
)
from backend.app.compliance.registry import detect_inuit_specific, normalize_section_name
from backend.app.compliance.service import ComplianceEvaluationService


MAX_UPLOAD_BYTES = 15 * 1024 * 1024


CATEGORY_LABELS = {
    "content": "Content",
    "sections": "Sections",
    "funding_fit": "Funding Fit",
    "indigenous_governance_ethics": "Indigenous Governance & Ethics",
}


METRIC_SPECS = [
    ("community_need_problem_framing", "Community Need / Problem Framing", "content"),
    ("clarity_specificity", "Clarity & Specificity", "content"),
    ("quantifiable_impact", "Quantifiable Impact / Measurable Outcomes", "content"),
    ("repetition_redundancy", "Repetition / Redundancy", "content"),
    ("grammar_writing_quality", "Grammar / Writing Quality", "content"),
    ("section_completeness", "Section Completeness", "sections"),
    ("missing_required_components", "Missing Required Components", "sections"),
    ("structural_readiness", "Structural Readiness", "sections"),
    ("program_alignment", "Program Alignment", "funding_fit"),
    ("eligibility_requirements_fit", "Eligibility / Requirements Fit", "funding_fit"),
    ("budget_alignment", "Budget Alignment", "funding_fit"),
    ("deliverables_activities_fit", "Deliverables / Activities Fit", "funding_fit"),
    ("community_engagement", "Community Engagement", "indigenous_governance_ethics"),
    ("ocap_data_governance", "OCAP / Data Governance", "indigenous_governance_ethics"),
    ("tcps2_ethical_research", "TCPS2 / Ethical Research Alignment", "indigenous_governance_ethics"),
    ("inuit_specific_alignment", "Inuit-specific Alignment / IQ Principles", "indigenous_governance_ethics"),
]


def _proposal_analysis_path(proposal_id: str) -> Path:
    return PROPOSAL_ANALYSIS_DIR / f"{proposal_id}.json"


class ProposalAnalysisService:
    def __init__(self, compliance_service: ComplianceEvaluationService) -> None:
        self.compliance_service = compliance_service

    def analyze_upload(self, file_name: str, file_bytes: bytes) -> ProposalAnalysisResponse:
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise ValueError("File exceeds the 15 MB upload limit.")

        suffix = Path(file_name).suffix.lower()
        temp_path = Path(_write_temp_file(file_name, file_bytes))
        try:
            if suffix == ".pdf":
                extraction_result = extract_pdf_text_with_diagnostics(temp_path)
                raw_text = str(extraction_result["text"])
                extractor_name = str(extraction_result["extractor"])
                candidate_extractors = list(extraction_result.get("candidates", []))
            elif suffix == ".docx":
                raw_text = extract_text_from_docx(temp_path)
                extractor_name = "python-docx"
                candidate_extractors = []
            else:
                raise ValueError("Only PDF and DOCX files are supported.")
        finally:
            temp_path.unlink(missing_ok=True)

        cleaned_text = _clean_proposal_text(raw_text)
        sections = _extract_proposal_sections(cleaned_text)
        extraction_diagnostics = _build_extraction_diagnostics(
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            sections=sections,
            extractor=extractor_name,
            candidate_extractors=candidate_extractors,
        )
        preview_sections = sections
        if extraction_diagnostics.preview_mode == "continuous":
            preview_sections = [
                ProposalSection(
                    key="continuous_preview",
                    title="Continuous Extracted Draft",
                    body=cleaned_text or raw_text,
                    order=0,
                )
            ]
        analysis = self._build_analysis(
            file_name=file_name,
            file_type=suffix[1:],
            sections=preview_sections,
            additional_submission_requirements=_extract_additional_submission_requirements(cleaned_text),
            extraction_diagnostics=extraction_diagnostics,
            raw_preview_text=cleaned_text or raw_text,
        )
        self.save_analysis(analysis)
        return analysis

    def save_analysis(self, analysis: ProposalAnalysisResponse) -> None:
        PROPOSAL_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        _proposal_analysis_path(analysis.analysis.proposal_id).write_text(
            analysis.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def load_analysis(self, proposal_id: str) -> ProposalAnalysisResponse:
        path = _proposal_analysis_path(proposal_id)
        if not path.exists():
            raise FileNotFoundError(proposal_id)
        return ProposalAnalysisResponse.model_validate_json(path.read_text(encoding="utf-8"))

    def reanalyze_sections(self, proposal_id: str, sections: List[ProposalSection]) -> ProposalAnalysisResponse:
        existing = self.load_analysis(proposal_id)
        ordered_sections = sorted(sections, key=lambda item: item.order)
        analysis = self._build_analysis(
            file_name=existing.analysis.file_name,
            file_type=existing.analysis.file_type,
            sections=ordered_sections,
            additional_submission_requirements=existing.additional_submission_requirements,
            extraction_diagnostics=existing.extraction,
            raw_preview_text=existing.raw_preview_text,
            proposal_id=proposal_id,
            uploaded_at=existing.analysis.uploaded_at,
        )
        self.save_analysis(analysis)
        return analysis

    def rewrite_section(
        self,
        proposal_id: str,
        section_key: str,
        instruction: str,
        metric_id: str | None = None,
        issue_id: str | None = None,
        issue_message: str | None = None,
        issue_recommendation: str | None = None,
    ) -> ProposalSectionRewriteResponse:
        analysis = self.load_analysis(proposal_id)
        section = next((item for item in analysis.sections if item.key == section_key), None)
        if not section:
            raise KeyError(section_key)

        rationale = f"Rewritten to address {metric_id.replace('_', ' ') if metric_id else 'the selected review issues'}."
        rewritten_text = _heuristic_rewrite(
            section.body,
            instruction,
            section.title,
            metric_id=metric_id,
            issue_id=issue_id,
            issue_message=issue_message,
            issue_recommendation=issue_recommendation,
        )
        return ProposalSectionRewriteResponse(
            proposal_id=proposal_id,
            section_key=section_key,
            rewritten_text=rewritten_text,
            rationale=rationale,
            references=[],
        )

    def chat(self, proposal_id: str, message: str, section_key: str | None = None, metric_id: str | None = None) -> ProposalChatResponse:
        analysis = self.load_analysis(proposal_id)
        suggested_actions: List[str] = []

        if section_key:
            section = next((item for item in analysis.sections if item.key == section_key), None)
            if section:
                suggested_actions.extend([gap.recommendation for gap in section.compliance_gaps[:2]])

        if metric_id:
            for category in analysis.categories:
                for metric in category.metrics:
                    if metric.id == metric_id:
                        suggested_actions.extend(metric.suggestions[:2])

        if not suggested_actions:
            suggested_actions = analysis.assistant_starters[:3]

        response = (
            f"For '{message}', start by tightening the most affected section, then address any linked compliance gaps. "
            f"I would focus on: {'; '.join(suggested_actions[:3])}."
        )
        return ProposalChatResponse(
            proposal_id=proposal_id,
            response=response,
            suggested_actions=suggested_actions[:4],
        )

    def _build_analysis(
        self,
        *,
        file_name: str,
        file_type: str,
        sections: List[ProposalSection],
        additional_submission_requirements: List[str] | None = None,
        extraction_diagnostics: ProposalExtractionDiagnostics | None = None,
        raw_preview_text: str = "",
        proposal_id: str | None = None,
        uploaded_at: datetime | None = None,
    ) -> ProposalAnalysisResponse:
        evaluated_sections: List[ProposalSection] = []
        for section in sections:
            evaluated = self.compliance_service.evaluate_section(
                ComplianceEvaluationRequest(section_name=section.title, section_text=section.body)
            )
            section_payload = section.model_dump(
                exclude={"warnings", "compliance_gaps", "issues_count", "section_score"}
            )
            warnings = _dedupe_warnings([*evaluated.warnings, *_word_limit_warnings(section.body, section.word_limit)])
            evaluated_sections.append(
                ProposalSection(
                    **section_payload,
                    warnings=warnings,
                    compliance_gaps=evaluated.compliance_gaps,
                    issues_count=len(warnings) + len(evaluated.compliance_gaps),
                    section_score=(evaluated.scoring_hooks or {}).get("overall_score", 0),
                )
            )

        categories = _build_metric_categories(evaluated_sections)
        overall_score = round(sum(category.score for category in categories) / max(1, len(categories)))
        issue_count = sum(category.issues for category in categories)
        now = datetime.now(timezone.utc)
        return ProposalAnalysisResponse(
            analysis=AnalysisHeader(
                proposal_id=proposal_id or uuid4().hex[:12],
                file_name=file_name,
                file_type=file_type,
                uploaded_at=uploaded_at or now,
                last_analyzed_at=now,
            ),
            extraction=extraction_diagnostics
            or ProposalExtractionDiagnostics(
                extractor="unknown",
                confidence="medium",
                preview_mode="sectioned",
                raw_text_length=len(raw_preview_text),
                cleaned_text_length=len(raw_preview_text),
                section_count=len(evaluated_sections),
            ),
            overall_score=overall_score,
            issue_count=issue_count,
            categories=categories,
            sections=evaluated_sections,
            additional_submission_requirements=additional_submission_requirements or [],
            assistant_starters=[
                "Strengthen the weakest section",
                "Add measurable outcomes",
                "Improve program alignment",
                "Rewrite for clearer community benefit",
            ],
            raw_preview_text=raw_preview_text,
            report_summary=_build_report_summary(evaluated_sections, categories),
        )


def _build_metric_categories(sections: List[ProposalSection]) -> List[MetricCategoryResult]:
    section_map = {section.key: section for section in sections}
    issue_buckets: Dict[str, List[MetricIssue]] = defaultdict(list)
    metric_scores: Dict[str, int] = {}

    for metric_id, label, category_id in METRIC_SPECS:
        metric_issues = _build_metric_issues(metric_id, label, sections, section_map)
        issue_buckets[metric_id] = metric_issues
        penalty = sum(18 if issue.severity == "critical" else 12 if issue.severity == "warning" else 8 for issue in metric_issues)
        metric_scores[metric_id] = max(28, 100 - penalty)

    categories: List[MetricCategoryResult] = []
    for category_id, label in CATEGORY_LABELS.items():
        metrics: List[MetricResult] = []
        for metric_id, metric_label, metric_category in METRIC_SPECS:
            if metric_category != category_id:
                continue
            metric_issues = issue_buckets[metric_id]
            metrics.append(
                MetricResult(
                    id=metric_id,
                    label=metric_label,
                    category_id=category_id,
                    description=_metric_description(metric_id, metric_label),
                    score=metric_scores[metric_id],
                    issues_count=len(metric_issues),
                    status="No issues" if not metric_issues else f"{len(metric_issues)} issues found",
                    summary=_metric_summary(metric_id, metric_issues),
                    issues=metric_issues,
                    suggestions=[issue.recommendation for issue in metric_issues[:3]] or [f"Maintain strong {metric_label.lower()}."],
                    linked_sections=sorted({section for issue in metric_issues for section in issue.affected_sections}),
                )
            )

        categories.append(
            MetricCategoryResult(
                id=category_id,
                label=label,
                score=round(sum(metric.score for metric in metrics) / max(1, len(metrics))),
                issues=sum(metric.issues_count for metric in metrics),
                metrics=metrics,
            )
        )
    return categories


def _build_metric_issues(metric_id: str, label: str, sections: List[ProposalSection], section_map: Dict[str, ProposalSection]) -> List[MetricIssue]:
    issues: List[MetricIssue] = []
    lower_metric = metric_id.lower()

    for section in sections:
        text = section.body
        normalized = normalize_section_name(section.title)

        if metric_id == "section_completeness" and any(w.type in {"empty_section", "whitespace_only_section", "incomplete_section"} for w in section.warnings):
            issues.append(_issue_from_warning(metric_id, label, section))
        elif metric_id == "structural_readiness" and section.section_score < 70:
            issues.append(_generic_issue(metric_id, label, section, "warning", 72, "Structural readiness is uneven in this section."))
        elif metric_id == "budget_alignment" and (normalized == "budget_justification" or "budget" in section.title.lower()):
            issues.extend(_issues_from_gaps(metric_id, label, section, category_filter={"budget_alignment"}))
        elif metric_id == "community_engagement":
            issues.extend(_issues_from_gaps(metric_id, label, section, category_filter={"community_engagement"}))
        elif metric_id == "ocap_data_governance":
            issues.extend(_issues_from_gaps(metric_id, label, section, category_filter={"data_governance"}))
        elif metric_id == "tcps2_ethical_research":
            issues.extend(_issues_from_gaps(metric_id, label, section, category_filter={"ethical_research"}))
        elif metric_id == "inuit_specific_alignment" and detect_inuit_specific(text, section.title):
            issues.extend(_issues_from_gaps(metric_id, label, section, category_filter={"iq_collaboration", "iq_service_to_community", "iq_skills_development", "community_benefit"}))
        elif metric_id == "quantifiable_impact" and not re.search(r"\b\d+[%+]?\b", text):
            issues.append(_generic_issue(metric_id, label, section, "warning", 76, "This section lacks concrete measures, targets, or numbers."))
        elif metric_id == "clarity_specificity" and _has_vague_language(text):
            issues.append(_generic_issue(metric_id, label, section, "info", 63, "The writing is directionally clear but still relies on broad or vague wording."))
        elif metric_id == "repetition_redundancy" and _has_repetition(text):
            issues.append(_generic_issue(metric_id, label, section, "info", 58, "This section repeats ideas or sentence stems more than necessary."))
        elif metric_id == "grammar_writing_quality" and _has_sentence_quality_risk(text):
            issues.append(_generic_issue(metric_id, label, section, "info", 55, "Sentence structure or punctuation could be tightened for a cleaner read."))
        elif metric_id == "program_alignment" and section.compliance_gaps:
            issues.append(_generic_issue(metric_id, label, section, "warning", 74, "The section would benefit from clearer program-fit language and stronger alignment framing."))
        elif metric_id == "deliverables_activities_fit" and normalized in {"implementation_plan", "evaluation_plan"} and "will" in text.lower() and not re.search(r"\bdeliverable|activity|milestone|timeline\b", text.lower()):
            issues.append(_generic_issue(metric_id, label, section, "warning", 77, "Activities are mentioned, but concrete deliverables or milestones are not obvious."))
        elif metric_id == "missing_required_components" and normalized in {"implementation_plan", "evaluation_plan"} and len(text.split()) < 120:
            issues.append(_generic_issue(metric_id, label, section, "warning", 68, "This section is present but likely missing expected detail."))
        elif metric_id == "community_need_problem_framing" and any(term in normalized for term in ["community_need", "problem", "need"]) and not re.search(r"\b(because|due to|evidence|data|increase|decline|shortage)\b", text.lower()):
            issues.append(_generic_issue(metric_id, label, section, "warning", 69, "The community need is stated, but the framing could use stronger evidence or causal detail."))
        elif metric_id == "eligibility_requirements_fit" and any(term in normalized for term in ["project_description", "implementation_plan"]) and not re.search(r"\beligible|objective|requirements|fit\b", text.lower()):
            issues.append(_generic_issue(metric_id, label, section, "info", 57, "Eligibility and requirements fit are not explicit in the current wording."))

    return issues[:4]


def _issues_from_gaps(metric_id: str, label: str, section: ProposalSection, category_filter: set[str]) -> List[MetricIssue]:
    issues: List[MetricIssue] = []
    for gap in section.compliance_gaps:
        if gap.category not in category_filter:
            continue
        anchor_text = _normalize_anchor_text(gap.source_excerpt) or _best_anchor_excerpt(section.body)
        issues.append(
            MetricIssue(
                issue_id=f"{metric_id}_{section.key}_{gap.failed_check_id}",
                title=label,
                message=gap.message,
                severity="critical" if gap.severity == "critical" else "warning",
                confidence_score=gap.confidence_score,
                section_key=section.key,
                anchor_type="text" if anchor_text else "section",
                anchor_text=anchor_text,
                anchor_hint=_first_paragraph(section.body),
                affected_sections=[section.key],
                excerpt=gap.source_excerpt,
                recommendation=gap.recommendation,
            )
        )
    return issues


def _issue_from_warning(metric_id: str, label: str, section: ProposalSection) -> MetricIssue:
    warning = section.warnings[0]
    anchor_text = _first_paragraph(section.body)
    anchor_type = "paragraph" if anchor_text else "section"
    return MetricIssue(
        issue_id=f"{metric_id}_{section.key}_{warning.type}",
        title=label,
        message=warning.message,
        severity="warning",
        confidence_score=96,
        section_key=section.key,
        anchor_type=anchor_type,
        anchor_text=anchor_text if anchor_type != "section" else None,
        anchor_hint=anchor_text,
        affected_sections=[section.key],
        excerpt=anchor_text,
        recommendation="Expand this section before relying on downstream scoring or rewrite suggestions.",
    )


def _generic_issue(
    metric_id: str,
    label: str,
    section: ProposalSection,
    severity: str,
    confidence: int,
    message: str,
) -> MetricIssue:
    paragraph_anchor = _first_paragraph(section.body)
    text_anchor = _best_anchor_excerpt(section.body)
    anchor_type = "text" if text_anchor else ("paragraph" if paragraph_anchor else "section")
    return MetricIssue(
        issue_id=f"{metric_id}_{section.key}",
        title=label,
        message=message,
        severity=severity,  # type: ignore[arg-type]
        confidence_score=confidence,
        section_key=section.key,
        anchor_type=anchor_type,
        anchor_text=text_anchor if anchor_type == "text" else paragraph_anchor if anchor_type == "paragraph" else None,
        anchor_hint=paragraph_anchor,
        affected_sections=[section.key],
        excerpt=text_anchor or paragraph_anchor or None,
        recommendation=f"Revise '{section.title}' to strengthen {label.lower()}.",
    )


def _metric_description(metric_id: str, label: str) -> str:
    descriptions = {
        "community_need_problem_framing": "Checks whether the proposal explains the problem, need, and local context persuasively.",
        "clarity_specificity": "Looks for specific, concrete wording instead of broad or generic statements.",
        "quantifiable_impact": "Assesses whether the draft includes measurable targets, outcomes, or quantified impact.",
        "repetition_redundancy": "Flags repeated ideas or overly recycled phrasing across sections.",
        "grammar_writing_quality": "Highlights sentence-level quality issues that affect readability and polish.",
        "section_completeness": "Evaluates whether sections are present and materially complete.",
        "missing_required_components": "Flags places where expected components appear to be missing or underdeveloped.",
        "structural_readiness": "Assesses whether the proposal feels submission-ready at a structural level.",
        "program_alignment": "Measures how clearly the draft connects the project to funder goals and expectations.",
        "eligibility_requirements_fit": "Looks for explicit evidence that the proposal fits the program rules and priorities.",
        "budget_alignment": "Checks whether costs are clearly tied to eligible project activities.",
        "deliverables_activities_fit": "Evaluates whether deliverables, activities, and implementation details are concrete.",
        "community_engagement": "Assesses whether community partners have meaningful roles in the work.",
        "ocap_data_governance": "Checks how the draft handles ownership, access, control, and data governance expectations.",
        "tcps2_ethical_research": "Assesses ethical research framing and respectful partnership language.",
        "inuit_specific_alignment": "Applies Inuit-specific governance and IQ expectations when the proposal is Inuit-focused.",
    }
    return descriptions.get(metric_id, f"Evaluates {label.lower()}.")


def _metric_summary(metric_id: str, issues: List[MetricIssue]) -> str:
    if not issues:
        return "Good overall alignment. No material issues found in this metric."
    if len(issues) == 1:
        return issues[0].message
    return f"{len(issues)} issues found. The most important theme is: {issues[0].message}"


def _build_report_summary(sections: List[ProposalSection], categories: List[MetricCategoryResult]) -> str:
    weakest = sorted(categories, key=lambda item: item.score)[:2]
    issue_count = sum(category.issues for category in categories)
    section_count = len(sections)
    weak_labels = ", ".join(category.label for category in weakest)
    return (
        f"Analyzed {section_count} proposal sections and found {issue_count} improvement opportunities. "
        f"The weakest areas are {weak_labels}, and those should be the first focus for revision."
    )


def _extract_proposal_sections(raw_text: str) -> List[ProposalSection]:
    cleaned_text = _clean_proposal_text(raw_text)
    try:
        from backend.app.parsers.grant_parsers import _extract_sections_from_text
    except Exception:
        _extract_sections_from_text = None

    sections: List[ProposalSection] = []
    if _extract_sections_from_text is not None:
        extracted = _extract_sections_from_text(cleaned_text)
        for index, section in enumerate(extracted):
            body = _clean_section_body(section.get("guidance") or "")
            title = _clean_section_title(section.get("title") or f"Section {index+1}")
            if not body:
                continue
            sections.append(
                ProposalSection(
                    key=section.get("key") or f"section_{index+1}",
                    title=title,
                    body=body,
                    order=len(sections),
                    word_limit=section.get("word_limit"),
                )
            )

    if sections:
        return _merge_fragmented_sections(sections)

    paragraphs = [
        _clean_section_body(part)
        for part in re.split(r"\n{2,}", cleaned_text)
        if _clean_section_body(part)
    ]
    chunk_size = 4
    for index in range(0, len(paragraphs), chunk_size):
        chunk = "\n\n".join(paragraphs[index : index + chunk_size])
        order = index // chunk_size
        sections.append(
            ProposalSection(
                key=f"section_{order+1}",
                title=f"Section {order+1}",
                body=chunk,
                order=order,
                word_limit=_extract_inline_word_limit(chunk),
            )
        )
    return _merge_fragmented_sections(sections)


def _write_temp_file(file_name: str, file_bytes: bytes) -> str:
    PROPOSAL_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = PROPOSAL_ANALYSIS_DIR / f"tmp_{uuid4().hex[:8]}_{Path(file_name).name}"
    temp_path.write_bytes(file_bytes)
    return str(temp_path)


def _heuristic_rewrite(
    text: str,
    instruction: str,
    title: str,
    *,
    metric_id: str | None = None,
    issue_id: str | None = None,
    issue_message: str | None = None,
    issue_recommendation: str | None = None,
) -> str:
    instruction_line = instruction.strip().rstrip(".")
    recommendation_line = (issue_recommendation or "").strip().rstrip(".")
    cleaned = _normalize_rewrite_text(text.strip())
    focus_line = recommendation_line or instruction_line or "Strengthen this section with clearer, more specific grant-ready language"

    if not cleaned:
        return _build_empty_section_rewrite(title, focus_line, metric_id)

    if metric_id == "budget_alignment":
        return _rewrite_budget_alignment(cleaned, title, focus_line)
    if metric_id == "quantifiable_impact":
        return _rewrite_quantifiable_impact(cleaned, title, focus_line)
    if metric_id == "clarity_specificity":
        return _rewrite_clarity(cleaned, title, focus_line)
    if metric_id == "repetition_redundancy":
        return _rewrite_repetition(cleaned, title, focus_line)
    if metric_id == "grammar_writing_quality":
        return _rewrite_grammar(cleaned, title, focus_line)
    if metric_id == "program_alignment":
        return _rewrite_program_alignment(cleaned, title, focus_line)
    if metric_id == "deliverables_activities_fit":
        return _rewrite_deliverables(cleaned, title, focus_line)

    return _rewrite_generic(cleaned, title, focus_line, issue_message=issue_message, issue_id=issue_id)


def _normalize_rewrite_text(text: str) -> str:
    paragraphs = [re.sub(r"\s+", " ", block).strip() for block in re.split(r"\n{2,}", text) if block.strip()]
    return "\n\n".join(paragraphs)


def _sentence_list(text: str) -> List[str]:
    return [re.sub(r"\s+", " ", sentence).strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _build_empty_section_rewrite(title: str, focus_line: str, metric_id: str | None) -> str:
    scaffolds = {
        "budget_alignment": (
            f"{title}: This section should explain each requested cost, the project activity it supports, and why the cost is eligible under the grant."
            "\n\nRequested costs will support defined implementation activities, partner coordination, reporting, and delivery milestones."
        ),
        "quantifiable_impact": (
            f"{title}: This section should state the measurable outcomes the project will achieve, including targets, timelines, and community benefits."
            "\n\nThe project will deliver clear outputs, track progress against defined indicators, and report quantified results during implementation."
        ),
    }
    return scaffolds.get(
        metric_id or "",
        f"{title}: {focus_line}. Add concrete activities, responsible roles, timelines, and measurable outcomes.",
    )


def _rewrite_budget_alignment(text: str, title: str, focus_line: str) -> str:
    sentences = _sentence_list(text)
    lead = sentences[0] if sentences else text
    amounts = re.findall(r"\$?\d[\d,]*(?:\.\d+)?", text)
    amount_phrase = ""
    if amounts:
        sampled = ", ".join(dict.fromkeys(amounts[:4]))
        amount_phrase = f" Requested amounts such as {sampled} should each be tied to a named project activity, partner role, or deliverable."
    return (
        f"{lead} Each budget item is tied to a specific eligible activity, implementation milestone, or partner responsibility under the project work plan."
        f"{amount_phrase}\n\n"
        f"Budget justification: explain what each cost covers, who is responsible, what output it supports, and why it is necessary for eligible project delivery. {focus_line}."
    )


def _rewrite_quantifiable_impact(text: str, title: str, focus_line: str) -> str:
    sentences = _sentence_list(text)
    base = " ".join(sentences[:2]) if sentences else text
    return (
        f"{base} The project will track measurable outputs, timelines, and outcomes across implementation."
        "\n\nMeasurable outcomes should include the number of communities supported, the number of plans or deliverables produced, the number of people trained, and the timeline for delivery."
        f" {focus_line}."
    )


def _rewrite_clarity(text: str, title: str, focus_line: str) -> str:
    sentences = _sentence_list(text)
    tightened = " ".join(sentences[:3]) if sentences else text
    tightened = re.sub(r"\b(?:various|several|many|support|help|improve|enhance)\b", "", tightened, flags=re.I)
    tightened = re.sub(r"\s{2,}", " ", tightened).strip()
    return (
        f"{tightened}\n\n"
        f"In concrete terms, this section should name the activity, the responsible party, the expected output, and the intended community benefit. {focus_line}."
    )


def _rewrite_repetition(text: str, title: str, focus_line: str) -> str:
    unique_sentences: List[str] = []
    seen: set[str] = set()
    for sentence in _sentence_list(text):
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_sentences.append(sentence)
    compact = " ".join(unique_sentences[:4]) if unique_sentences else text
    return (
        f"{compact}\n\n"
        f"This revision removes repeated ideas and keeps the section focused on the strongest distinct points. {focus_line}."
    )


def _rewrite_grammar(text: str, title: str, focus_line: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = _sentence_list(normalized)
    polished = " ".join(sentences[:4]) if sentences else normalized
    return (
        f"{polished}\n\n"
        f"This version uses shorter, clearer sentences and cleaner transitions to improve readability. {focus_line}."
    )


def _rewrite_program_alignment(text: str, title: str, focus_line: str) -> str:
    sentences = _sentence_list(text)
    base = " ".join(sentences[:3]) if sentences else text
    return (
        f"{base} This work directly advances the funding program by strengthening implementation readiness, community benefit, and long-term project feasibility."
        "\n\nThe section should explicitly connect the proposed activities to program objectives, eligible activities, and expected outcomes for participating communities."
        f" {focus_line}."
    )


def _rewrite_deliverables(text: str, title: str, focus_line: str) -> str:
    sentences = _sentence_list(text)
    base = " ".join(sentences[:2]) if sentences else text
    return (
        f"{base}\n\n"
        "Core deliverables should include named outputs, milestone dates, responsible partners, and completion indicators so progress can be tracked clearly."
        f" {focus_line}."
    )


def _rewrite_generic(text: str, title: str, focus_line: str, *, issue_message: str | None = None, issue_id: str | None = None) -> str:
    sentences = _sentence_list(text)
    base = " ".join(sentences[:3]) if sentences else text
    issue_context = f" This revision addresses: {issue_message}." if issue_message else ""
    return (
        f"{base}\n\n"
        f"Strengthened revision: clarify the main activity, name the responsible parties, describe the intended output, and state the expected community benefit.{issue_context} {focus_line}."
    )


def _has_vague_language(text: str) -> bool:
    return len(re.findall(r"\b(?:support|help|improve|enhance|various|several|many)\b", text.lower())) >= 3


def _has_repetition(text: str) -> bool:
    sentences = [sentence.strip().lower() for sentence in re.split(r"[.!?]", text) if sentence.strip()]
    return len(sentences) != len(set(sentences))


def _has_sentence_quality_risk(text: str) -> bool:
    if ".." in text or " ," in text:
        return True
    long_sentences = [sentence for sentence in re.split(r"[.!?]", text) if len(sentence.split()) > 35]
    return len(long_sentences) >= 2


def _clean_proposal_text(raw_text: str) -> str:
    text = (raw_text or "").replace("\r\n", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?im)^\s*page\s+\d+(?:\s+of\s+\d+)?\s*$", "", text)
    text = re.sub(r"(?im)^\s*\d+\s*$", "", text)
    text = re.sub(r"(?im)^\s*(figure|table)\s+\d+[:.\-].*$", "", text)
    text = re.sub(r"(?im)^\s*(doi:|https?://\S+)\s*$", "", text)

    tail_cut = re.search(
        r"(?im)^\s*(references|bibliography|works cited|literature cited|appendix(?:es)?|citations)\s*$",
        text,
    )
    if tail_cut:
        text = text[: tail_cut.start()]

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _is_noise_line(stripped):
            continue
        lines.append(stripped)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_section_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", (title or "").strip()).strip(":")
    return cleaned[:140] or "Untitled Section"


def _clean_section_body(body: str) -> str:
    cleaned = _clean_proposal_text(body)
    paragraphs: List[str] = []
    for paragraph in re.split(r"\n{2,}", cleaned):
        normalized = re.sub(r"\s+", " ", paragraph).strip()
        if not normalized:
            continue
        if _looks_like_reference_paragraph(normalized):
            continue
        paragraphs.append(normalized)
    return "\n\n".join(paragraphs).strip()


def _merge_fragmented_sections(sections: List[ProposalSection]) -> List[ProposalSection]:
    if not sections:
        return sections

    merged: List[ProposalSection] = []
    for section in sections:
        body_words = len(section.body.split())
        if merged and (body_words < 55 or _looks_like_subheading(section.title)):
            previous = merged[-1]
            merged[-1] = previous.model_copy(
                update={"body": f"{previous.body}\n\n{section.body}".strip()}
            )
            continue
        merged.append(section)

    return [
        section.model_copy(update={"order": index, "key": section.key or f"section_{index+1}"})
        for index, section in enumerate(merged)
    ]


def _is_noise_line(line: str) -> bool:
    if len(line) <= 2:
        return True
    if re.fullmatch(r"[\[\(]?\d{1,3}[\]\)]?", line):
        return True
    if re.fullmatch(r"(?:\[\d+\]\s*){2,}", line):
        return True
    if re.search(r"\b(?:journal|vol\.|issue|pp\.|doi)\b", line, flags=re.I) and len(line.split()) < 18:
        return True
    if re.fullmatch(r"(?:[A-Z][a-z]+,?\s+){1,6}\(\d{4}\).*", line):
        return True
    return False


def _looks_like_reference_paragraph(paragraph: str) -> bool:
    if re.match(r"^(?:\[\d+\]|\(\d{4}\))", paragraph):
        return True
    if re.search(r"\b(?:doi|retrieved from|available at)\b", paragraph, flags=re.I):
        return True
    if re.search(r"\b[A-Z][a-z]+,\s+[A-Z]\.", paragraph) and re.search(r"\(\d{4}\)", paragraph):
        return True
    return False


def _looks_like_subheading(title: str) -> bool:
    if re.match(r"^\d+[\).:-]\s+\S+", title):
        return False
    if re.match(r"^(SECTION|PART|APPENDIX)\s+[A-Z0-9]+", title, flags=re.I):
        return False
    words = title.split()
    if len(words) > 8:
        if re.match(r"^\d+[:.)-]", title):
            return True
        lowered = sum(1 for word in words if word[:1].islower())
        return lowered >= max(2, len(words) // 2)
    if re.match(r"^\d+(?:\.\d+)+", title):
        return True
    if re.match(r"^\d+[:.)-]", title) and any(word[:1].islower() for word in words[1:]):
        return True
    if len(words) <= 4 and title == title.title() and not re.match(r"^[A-Z]\.\s+\S+", title):
        return True
    return False


def _normalize_anchor_text(text: str | None, limit: int = 220) -> str | None:
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return None
    return normalized[:limit]


def _first_paragraph(text: str) -> str | None:
    for paragraph in re.split(r"\n{2,}", text or ""):
        normalized = _normalize_anchor_text(paragraph)
        if normalized:
            return normalized
    return None


def _best_anchor_excerpt(text: str) -> str | None:
    for paragraph in re.split(r"\n{2,}", text or ""):
        normalized_paragraph = re.sub(r"\s+", " ", paragraph).strip()
        if not normalized_paragraph:
            continue
        sentences = [re.sub(r"\s+", " ", sentence).strip() for sentence in re.split(r"(?<=[.!?])\s+", normalized_paragraph)]
        for sentence in sentences:
            if 10 <= len(sentence.split()) <= 32:
                return _normalize_anchor_text(sentence)
        fallback = _normalize_anchor_text(normalized_paragraph)
        if fallback:
            return fallback
    return None


def _word_limit_warnings(section_text: str, word_limit: int | None) -> List[WarningEntry]:
    if not word_limit or word_limit <= 0:
        return []
    word_count = len(re.findall(r"\b\w+\b", section_text or ""))
    warnings: List[WarningEntry] = []
    if word_count > word_limit:
        warnings.append(
            WarningEntry(
                type="word_limit_exceeded",
                message=f"This section is over the stated word limit ({word_count}/{word_limit} words).",
                details={"word_count": word_count, "word_limit": word_limit},
            )
        )
    elif word_limit >= 100 and word_count < max(40, int(word_limit * 0.4)):
        warnings.append(
            WarningEntry(
                type="below_expected_word_limit",
                message=f"This section appears short relative to the stated word limit ({word_count}/{word_limit} words).",
                details={"word_count": word_count, "word_limit": word_limit},
            )
        )
    return warnings


def _dedupe_warnings(warnings: List[WarningEntry]) -> List[WarningEntry]:
    seen: set[str] = set()
    deduped: List[WarningEntry] = []
    for warning in warnings:
        key = f"{warning.type}:{warning.message}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(warning)
    return deduped


def _extract_inline_word_limit(text: str) -> int | None:
    match = re.search(r"(?i)\b(?:word\s*limit|max(?:imum)?\s*words?|up to)\s*[:\-]?\s*(\d{2,5})\b", text or "")
    if not match:
        return None
    return int(match.group(1))


def _extract_additional_submission_requirements(text: str) -> List[str]:
    patterns = [
        ("Letters of support", r"(?i)\bletter(?:s)? of support\b"),
        ("Budget form", r"(?i)\bbudget (?:form|worksheet|template)\b"),
        ("Resumes or CVs", r"(?i)\b(?:resume|cv|curriculum vitae)s?\b"),
        ("Signed authorization or approval", r"(?i)\b(?:signed|signature|approval|authorization) form\b"),
        ("Appendices or supporting attachments", r"(?i)\bappendi(?:x|ces)\b|\bsupporting attachments?\b"),
        ("Financial statements or supporting financial documents", r"(?i)\bfinancial statements?\b|\baudited statements?\b"),
        ("Work plan or timeline attachment", r"(?i)\bwork plan\b|\btimeline attachment\b"),
    ]
    found: List[str] = []
    for label, pattern in patterns:
        if re.search(pattern, text or ""):
            found.append(label)
    return found


def _build_extraction_diagnostics(
    *,
    raw_text: str,
    cleaned_text: str,
    sections: List[ProposalSection],
    extractor: str,
    candidate_extractors: List[dict],
) -> ProposalExtractionDiagnostics:
    warnings: List[str] = []
    numbering_gaps_detected = _has_numbering_gaps([section.title for section in sections])

    if len(raw_text.strip()) < 1500:
        warnings.append("Very little text was extracted from this file.")
    if len(sections) <= 2:
        warnings.append("Only a small number of sections were detected from the uploaded document.")
    if numbering_gaps_detected:
        warnings.append("Section numbering appears incomplete or discontinuous in the extracted draft.")
    if len(cleaned_text) < max(400, int(len(raw_text) * 0.55)):
        warnings.append("A large amount of text was removed during cleanup, which may indicate formatting-related loss.")

    if len(sections) >= 4 and not numbering_gaps_detected and len(cleaned_text) >= 2500:
        confidence = "high"
    elif len(sections) >= 2 and len(cleaned_text) >= 1500:
        confidence = "medium"
    else:
        confidence = "low"

    preview_mode = "continuous" if confidence == "low" or numbering_gaps_detected else "sectioned"
    return ProposalExtractionDiagnostics(
        extractor=extractor,
        confidence=confidence,
        preview_mode=preview_mode,
        raw_text_length=len(raw_text),
        cleaned_text_length=len(cleaned_text),
        section_count=len(sections),
        numbering_gaps_detected=numbering_gaps_detected,
        warnings=warnings,
        candidate_extractors=[
            {
                "extractor": str(item.get("extractor", "")),
                "score": float(item.get("score", 0)),
                "chars": int(item.get("chars", 0)),
            }
            for item in candidate_extractors
        ],
    )


def _has_numbering_gaps(titles: List[str]) -> bool:
    numbers: List[int] = []
    for title in titles:
        match = re.match(r"^\s*(\d+)", title or "")
        if match:
            numbers.append(int(match.group(1)))
    if len(numbers) < 2:
        return False
    numbers = sorted(set(numbers))
    return any((current - previous) > 1 for previous, current in zip(numbers, numbers[1:]))
