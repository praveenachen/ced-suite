from __future__ import annotations

import re
from typing import List

from backend.app.compliance.config import WarningThresholds
from backend.app.compliance.models import WarningEntry


PLACEHOLDER_PATTERN = re.compile(r"\b(?:tbd|lorem ipsum|coming soon|add later|to be added|insert here)\b", re.IGNORECASE)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def build_warnings(section_text: str | None, thresholds: WarningThresholds) -> List[WarningEntry]:
    text = section_text if section_text is not None else None
    warnings: List[WarningEntry] = []

    if text is None:
        return [WarningEntry(type="missing_section", message="This section is missing.")]

    if text == "":
        warnings.append(WarningEntry(type="empty_section", message="This section is empty."))
        return warnings

    if text.strip() == "":
        warnings.append(WarningEntry(type="whitespace_only_section", message="This section contains only whitespace."))
        return warnings

    word_count = _word_count(text)
    if word_count < thresholds.min_words:
        warnings.append(
            WarningEntry(
                type="incomplete_section",
                message="This section appears incomplete.",
                details={"word_count": word_count, "minimum_words": thresholds.min_words},
            )
        )

    if word_count > thresholds.max_words:
        warnings.append(
            WarningEntry(
                type="over_word_limit",
                message="This section exceeds the recommended word limit.",
                details={"word_count": word_count, "maximum_words": thresholds.max_words},
            )
        )

    if PLACEHOLDER_PATTERN.search(text):
        warnings.append(
            WarningEntry(
                type="placeholder_text",
                message="This section contains placeholder text that should be replaced before submission.",
            )
        )

    return warnings


def is_evaluable(section_text: str | None) -> bool:
    return bool(section_text is not None and section_text.strip())
