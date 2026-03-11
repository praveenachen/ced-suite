from backend.app.compliance.config import WarningThresholds
from backend.app.compliance.warnings_engine import build_warnings


def test_warnings_engine_detects_empty_and_placeholder() -> None:
    warnings = build_warnings("TBD add later", WarningThresholds(min_words=60, max_words=500))
    warning_types = {item.type for item in warnings}
    assert "incomplete_section" in warning_types
    assert "placeholder_text" in warning_types


def test_warnings_engine_detects_over_limit() -> None:
    text = "word " * 520
    warnings = build_warnings(text, WarningThresholds(min_words=60, max_words=500))
    assert any(item.type == "over_word_limit" for item in warnings)
