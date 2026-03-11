from backend.app.compliance.config import GuardrailConfig
from backend.app.compliance.guardrails import run_guardrails


def test_guardrails_redact_and_warn() -> None:
    result = run_guardrails(
        "Contact Elder Mary Smith at mary@example.com and share raw interview transcripts without consent.",
        GuardrailConfig(redact_before_llm=True, block_external_llm_on_sensitive_content=False),
    )
    assert "[REDACTED_EMAIL]" in result.sanitized_text
    assert "[REDACTED_PERSON]" in result.sanitized_text
    assert any(item.type == "sensitive_content" for item in result.warnings)
    assert any(item.type == "possible_restricted_data_governance_issue" for item in result.warnings)


def test_guardrails_can_block_external_llm() -> None:
    result = run_guardrails(
        "Please publish participant-level data with names attached.",
        GuardrailConfig(redact_before_llm=True, block_external_llm_on_sensitive_content=True),
    )
    assert result.blocked is True
    assert any(item.type == "external_llm_blocked" for item in result.warnings)
