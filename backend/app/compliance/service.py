from __future__ import annotations

from backend.app.compliance.config import ComplianceConfig
from backend.app.compliance.evaluation import ComplianceGapEvaluator
from backend.app.compliance.fallback import build_minimum_review_gap
from backend.app.compliance.guardrails import run_guardrails
from backend.app.compliance.llm_client import BaseLLMClient, NullLLMClient, OpenAICompatibleLLMClient
from backend.app.compliance.models import (
    ComplianceEvaluationRequest,
    ComplianceEvaluationResponse,
    ProposalEvaluationResponse,
    SectionContext,
)
from backend.app.compliance.registry import detect_inuit_specific, infer_framework_tags, normalize_section_name, section_tags_for_name
from backend.app.compliance.retrieval import LocalHybridRetriever
from backend.app.compliance.scoring import score_section
from backend.app.compliance.warnings_engine import build_warnings, is_evaluable


class ComplianceEvaluationService:
    def __init__(
        self,
        *,
        config: ComplianceConfig | None = None,
        retriever: LocalHybridRetriever | None = None,
        llm_client: BaseLLMClient | None = None,
    ) -> None:
        self.config = config or ComplianceConfig()
        self.retriever = retriever or LocalHybridRetriever()
        self.evaluator = ComplianceGapEvaluator(llm_client or NullLLMClient())

    def evaluate_section(self, request: ComplianceEvaluationRequest) -> ComplianceEvaluationResponse:
        guardrail_result = run_guardrails(request.section_text or "", self.config.guardrails)
        warnings = list(guardrail_result.warnings)
        warnings.extend(build_warnings(request.section_text, self.config.warning_thresholds))
        warning_types = {item.type for item in warnings}

        if (
            not is_evaluable(request.section_text)
            or guardrail_result.blocked
            or bool(
                warning_types
                & {
                    "missing_section",
                    "empty_section",
                    "whitespace_only_section",
                    "incomplete_section",
                }
            )
        ):
            return ComplianceEvaluationResponse(
                section=request.section_name,
                warnings=warnings,
                compliance_gaps=[],
                scoring_hooks=score_section(warnings, []).model_dump(),
            )

        normalized_section = normalize_section_name(request.section_name)
        inuit_specific = detect_inuit_specific(guardrail_result.sanitized_text, request.section_name)
        section_context = SectionContext(
            section_name=request.section_name,
            section_text=guardrail_result.sanitized_text,
            normalized_section=normalized_section,
            section_tags=section_tags_for_name(request.section_name),
            community_scope=["Inuit"] if inuit_specific else ["First Nations", "Inuit", "Metis"],
            framework_tags=infer_framework_tags(guardrail_result.sanitized_text),
            is_inuit_specific=inuit_specific,
        )
        retrieved = self.retriever.retrieve(
            section_context,
            checks_top_k=self.config.retrieval.checks_top_k,
            excerpts_top_k=self.config.retrieval.excerpts_top_k,
        )
        gaps = self.evaluator.evaluate(section_context, retrieved)
        if not gaps and retrieved.checks:
            gaps = [build_minimum_review_gap(retrieved.checks[0])]
        return ComplianceEvaluationResponse(
            section=request.section_name,
            warnings=warnings,
            compliance_gaps=gaps,
            scoring_hooks=score_section(warnings, gaps).model_dump(),
        )

    @staticmethod
    def scaffold_proposal_evaluation() -> ProposalEvaluationResponse:
        return ProposalEvaluationResponse(
            message="Proposal-wide evaluation is scaffolded but not fully implemented yet.",
            todo=[
                "Parse uploaded PDF/DOCX into proposal sections.",
                "Run each extracted section through the compliance pipeline.",
                "Aggregate section-level scoring, warnings, and compliance gaps into proposal-wide feedback.",
            ],
        )


def build_default_service() -> ComplianceEvaluationService:
    llm_client: BaseLLMClient
    if OpenAICompatibleLLMClient().api_key:
        llm_client = OpenAICompatibleLLMClient()
    else:
        llm_client = NullLLMClient()
    return ComplianceEvaluationService(llm_client=llm_client)
