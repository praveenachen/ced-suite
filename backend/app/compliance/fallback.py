from __future__ import annotations

import re
from typing import List

from backend.app.compliance.models import ComplianceCheck, ComplianceGap, RetrievedContext, SectionContext


NEGATION_PATTERNS = [
    "no",
    "not",
    "does not",
    "do not",
    "without",
    "missing",
    "lack",
    "lacks",
    "lacking",
    "fails to",
]

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "will",
    "have",
    "who",
    "how",
    "what",
    "when",
    "your",
    "their",
    "about",
    "should",
    "project",
    "proposal",
    "section",
    "clear",
    "clearly",
}


def build_fallback_gaps(context: SectionContext, retrieved: RetrievedContext) -> List[ComplianceGap]:
    text = (context.section_text or "").lower()
    gaps: List[ComplianceGap] = []

    for index, check in enumerate(retrieved.checks):
        negation_hits = _count_negation_hits(text, check)
        evidence_hits = _count_evidence_hits(text, check)

        if negation_hits <= 0 and evidence_hits > 0:
            continue

        if negation_hits <= 0 and evidence_hits == 0 and index > 0:
            continue

        confidence = min(88, 58 + negation_hits * 12 + (6 if evidence_hits == 0 else 0) + max(0, 8 - index * 2))
        recommendation = _recommendation_from_check(check)
        message = _message_from_check(check)
        gaps.append(
            ComplianceGap(
                failed_check_id=check.check_id,
                category=check.category,
                severity=check.severity_if_failed,
                confidence_score=confidence,
                message=message,
                recommendation=recommendation,
                source_excerpt=check.source_excerpt,
                source_document=check.source_document,
            )
        )

    unique: List[ComplianceGap] = []
    seen = set()
    for gap in gaps:
        if gap.failed_check_id in seen:
            continue
        seen.add(gap.failed_check_id)
        unique.append(gap)
    return unique


def build_minimum_review_gap(check: ComplianceCheck) -> ComplianceGap:
    return ComplianceGap(
        failed_check_id=check.check_id,
        category=check.category,
        severity="minor",
        confidence_score=36,
        message=f"This section may still need stronger evidence for {check.title.lower()}.",
        recommendation=_recommendation_from_check(check),
        source_excerpt=check.source_excerpt,
        source_document=check.source_document,
    )


def _count_negation_hits(text: str, check: ComplianceCheck) -> int:
    keywords = _keywords_for_check(check)
    total = 0
    for keyword in keywords:
        escaped = re.escape(keyword)
        for neg in NEGATION_PATTERNS:
            pattern = rf"\b{re.escape(neg)}\b(?:\W+\w+){{0,5}}\W+{escaped}\b"
            if re.search(pattern, text):
                total += 1
                break
    return total


def _count_evidence_hits(text: str, check: ComplianceCheck) -> int:
    hits = 0
    for example in check.evidence_examples:
        keywords = _keywords_from_text(example)
        if keywords and any(keyword in text for keyword in keywords):
            hits += 1
    return hits


def _keywords_for_check(check: ComplianceCheck) -> List[str]:
    phrases = list(check.failure_signals) + [check.check_text, check.title]
    keywords = []
    for phrase in phrases:
        keywords.extend(_keywords_from_text(phrase))
    return list(dict.fromkeys(keywords))


def _keywords_from_text(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z]{4,}", (text or "").lower())
        if token not in STOPWORDS
    ]


def _message_from_check(check: ComplianceCheck) -> str:
    if check.category == "staff_capacity":
        return "The proposal does not clearly identify who will lead and deliver the project."
    return check.explanation.rstrip(".") + "."


def _recommendation_from_check(check: ComplianceCheck) -> str:
    if check.evidence_examples:
        return "; ".join(check.evidence_examples[:2]) + "."
    return check.check_text
