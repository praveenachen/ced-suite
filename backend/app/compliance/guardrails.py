from __future__ import annotations

import re
from typing import List

from backend.app.compliance.config import GuardrailConfig
from backend.app.compliance.models import GuardrailMatch, GuardrailResult, WarningEntry


PERSONAL_PATTERNS = [
    ("personal_identifier", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[REDACTED_EMAIL]"),
    ("personal_identifier", re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b"), "[REDACTED_PHONE]"),
    ("personal_identifier", re.compile(r"\b\d{3}-\d{3}-\d{3}\b"), "[REDACTED_BAND_NUMBER]"),
]

SENSITIVE_CONTEXT_PATTERNS = [
    ("named_individual_sensitive_context", re.compile(r"\b(?:Elder|youth|participant|patient|student|resident)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"), "[REDACTED_PERSON]"),
    ("restricted_knowledge", re.compile(r"\b(?:sacred|ceremonial|restricted knowledge|confidential traditional knowledge|elders only)\b", re.IGNORECASE), "[REDACTED_RESTRICTED_KNOWLEDGE]"),
    ("community_data_governance", re.compile(r"\b(?:raw interview transcripts?|household-?level data|participant-?level data|confidential community data|unpublished survey data)\b", re.IGNORECASE), "[REDACTED_SENSITIVE_DATA]"),
    ("consent_risk", re.compile(r"\b(?:without consent|no consent|pending consent|consent not yet obtained)\b", re.IGNORECASE), "[REDACTED_CONSENT_RISK]"),
]


def run_guardrails(text: str, config: GuardrailConfig) -> GuardrailResult:
    original_text = text or ""
    redaction_log: List[GuardrailMatch] = []
    warnings: List[WarningEntry] = []
    sanitized = original_text

    def add_warning(category: str, message: str) -> None:
        warnings.append(WarningEntry(type=category, message=message))

    for category, pattern, replacement in PERSONAL_PATTERNS + SENSITIVE_CONTEXT_PATTERNS:
        for match in pattern.finditer(original_text):
            redaction_log.append(
                GuardrailMatch(
                    category=category,
                    match_text=match.group(0),
                    replacement=replacement,
                    start=match.start(),
                    end=match.end(),
                )
            )

    if redaction_log:
        add_warning("sensitive_content", "Sensitive or governed content was detected before external analysis.")

    if any(item.category == "community_data_governance" for item in redaction_log):
        add_warning("possible_restricted_data_governance_issue", "This section may include governed community data that requires additional review.")

    if config.redact_before_llm:
        for match in sorted(redaction_log, key=lambda item: item.start, reverse=True):
            sanitized = sanitized[: match.start] + match.replacement + sanitized[match.end :]

    blocked = config.block_external_llm_on_sensitive_content and bool(redaction_log)
    if blocked:
        add_warning("external_llm_blocked", "External LLM analysis was blocked because sensitive content was detected.")

    return GuardrailResult(
        sanitized_text=sanitized,
        warnings=warnings,
        redaction_log=redaction_log,
        blocked=blocked,
    )
