from backend.app.compliance.models import SectionContext
from backend.app.compliance.registry import normalize_section_name, section_tags_for_name
from backend.app.compliance.retrieval import LocalHybridRetriever


def build_context(section_name: str, section_text: str, is_inuit_specific: bool = False) -> SectionContext:
    return SectionContext(
        section_name=section_name,
        section_text=section_text,
        normalized_section=normalize_section_name(section_name),
        section_tags=section_tags_for_name(section_name),
        community_scope=["Inuit"] if is_inuit_specific else ["First Nations", "Inuit", "Metis"],
        framework_tags=[],
        is_inuit_specific=is_inuit_specific,
    )


def test_section_aware_retrieval_prefers_staff_capacity_checks() -> None:
    retriever = LocalHybridRetriever()
    context = build_context(
        "staff_organization",
        "The project will be led by the executive director and a project coordinator with clear implementation roles.",
    )
    result = retriever.retrieve(context)
    assert result.checks
    assert result.checks[0].check_id == "staff_capacity_001"


def test_inuit_specific_retrieval_returns_inuit_checks() -> None:
    retriever = LocalHybridRetriever()
    context = build_context(
        "community_engagement",
        "This Inuit Nunangat project will be planned with Inuit partners in Nunavut through a shared steering group.",
        is_inuit_specific=True,
    )
    result = retriever.retrieve(context)
    retrieved_ids = {item.check_id for item in result.checks}
    assert "inuit_governance_001" in retrieved_ids
    assert any(
        chunk.source_document in {
            "National Inuit Strategy on Research",
            "Negotiating Research Relationships with Inuit Communities",
        }
        for chunk in result.excerpts
    )
