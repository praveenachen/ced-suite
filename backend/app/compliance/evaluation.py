from __future__ import annotations

from pydantic import ValidationError, TypeAdapter

from backend.app.compliance.fallback import build_fallback_gaps
from backend.app.compliance.llm_client import BaseLLMClient
from backend.app.compliance.models import ComplianceGap, RetrievedContext, SectionContext
from backend.app.compliance.prompting import build_compliance_prompt


class ComplianceGapEvaluator:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm_client = llm_client

    def evaluate(self, context: SectionContext, retrieved: RetrievedContext) -> list[ComplianceGap]:
        if not retrieved.checks:
            return []

        prompt = build_compliance_prompt(context, retrieved)
        try:
            payload = self.llm_client.generate_json(prompt["system"], prompt["user"])
            return TypeAdapter(list[ComplianceGap]).validate_python(payload.get("compliance_gaps", []))
        except ValidationError as exc:
            raise ValueError(f"Invalid compliance gap payload returned by LLM client: {exc}") from exc
        except Exception:
            return build_fallback_gaps(context, retrieved)
