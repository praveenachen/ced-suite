from __future__ import annotations

import json
from typing import Any, Dict

from backend.app.compliance.models import RetrievedContext, SectionContext


def build_compliance_prompt(context: SectionContext, retrieved: RetrievedContext) -> Dict[str, str]:
    system_prompt = (
        "You evaluate one grant proposal section at a time for substantive compliance gaps only. "
        "Use only the retrieved checks and supporting excerpts. Do not invent requirements. "
        "Do not output warnings for incompleteness, missing sections, privacy, or placeholders. "
        "Support TCPS2, OCAP, Inuit governance, Inuit Qaujimajatuqangit checks when relevant, "
        "and funding/program requirements when relevant. Return valid JSON only."
    )

    payload: Dict[str, Any] = {
        "task": "Evaluate one proposal section for substantive compliance gaps.",
        "section_name": context.section_name,
        "normalized_section": context.normalized_section,
        "section_text": context.section_text,
        "is_inuit_specific": context.is_inuit_specific,
        "framework_tags": context.framework_tags,
        "retrieved_checks": [item.model_dump() for item in retrieved.checks],
        "supporting_excerpts": [item.model_dump() for item in retrieved.excerpts],
        "output_schema": {
            "compliance_gaps": [
                {
                    "failed_check_id": "string",
                    "category": "string",
                    "severity": "minor|major|critical",
                    "confidence_score": "0-100 integer",
                    "message": "string",
                    "recommendation": "string",
                    "source_excerpt": "string",
                    "source_document": "string",
                }
            ]
        },
        "instructions": [
            "Evaluate one proposal section only.",
            "Use only the retrieved checks and supporting excerpts.",
            "Do not invent requirements or policy expectations not present in the retrieved material.",
            "Only output substantive compliance gaps.",
            "Keep recommendations actionable and concise.",
            "If there are no substantive compliance gaps, return {\"compliance_gaps\": []}.",
        ],
    }
    return {"system": system_prompt, "user": json.dumps(payload, ensure_ascii=False)}
