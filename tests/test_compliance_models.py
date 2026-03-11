from backend.app.compliance.evaluation import ComplianceGapEvaluator
from backend.app.compliance.llm_client import BaseLLMClient
from backend.app.compliance.models import SectionContext
from backend.app.compliance.registry import normalize_section_name, section_tags_for_name
from backend.app.compliance.retrieval import LocalHybridRetriever


class InvalidLLMClient(BaseLLMClient):
    def generate_json(self, system_prompt: str, user_prompt: str):
        return {"compliance_gaps": [{"message": "missing fields"}]}


class FailingLLMClient(BaseLLMClient):
    def generate_json(self, system_prompt: str, user_prompt: str):
        raise RuntimeError("network blocked")


def test_invalid_llm_payload_is_rejected() -> None:
    retriever = LocalHybridRetriever()
    context = SectionContext(
        section_name="staff_organization",
        section_text="A short but non-empty section.",
        normalized_section=normalize_section_name("staff_organization"),
        section_tags=section_tags_for_name("staff_organization"),
        community_scope=["First Nations", "Inuit", "Metis"],
        framework_tags=[],
        is_inuit_specific=False,
    )
    retrieved = retriever.retrieve(context)
    evaluator = ComplianceGapEvaluator(InvalidLLMClient())
    try:
        evaluator.evaluate(context, retrieved)
    except ValueError:
        return
    raise AssertionError("Expected ValueError for invalid LLM payload")


def test_fallback_evaluator_returns_confident_gap_when_llm_fails() -> None:
    retriever = LocalHybridRetriever()
    context = SectionContext(
        section_name="staff_organization",
        section_text=(
            "The consultant will manage the work, but the proposal does not name an internal lead, "
            "does not assign delivery responsibilities, and does not describe operational oversight."
        ),
        normalized_section=normalize_section_name("staff_organization"),
        section_tags=section_tags_for_name("staff_organization"),
        community_scope=["First Nations", "Inuit", "Metis"],
        framework_tags=[],
        is_inuit_specific=False,
    )
    retrieved = retriever.retrieve(context)
    evaluator = ComplianceGapEvaluator(FailingLLMClient())
    gaps = evaluator.evaluate(context, retrieved)
    assert any(gap.failed_check_id == "staff_capacity_001" for gap in gaps)
    assert all(0 <= gap.confidence_score <= 100 for gap in gaps)
