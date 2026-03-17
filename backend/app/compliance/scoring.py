from __future__ import annotations

from backend.app.compliance.models import ComplianceGap, ScoringResult, WarningEntry


def score_section(warnings: list[WarningEntry], gaps: list[ComplianceGap]) -> ScoringResult:
    structural = max(0, 100 - len(warnings) * 12)
    governance = max(0, 100 - sum(20 if gap.severity == "critical" else 12 if gap.severity == "major" else 6 for gap in gaps))
    funding_fit = max(0, 100 - len(gaps) * 10)
    community_quality = max(0, 100 - sum(15 if gap.category.startswith("iq_") else 8 for gap in gaps))
    overall = round((structural + governance + funding_fit + community_quality) / 4)
    return ScoringResult(
        overall_score=overall,
        dimensions={
            "structural_readiness": structural,
            "funding_fit": funding_fit,
            "indigenous_governance_ethics": governance,
            "community_centered_quality": community_quality,
        },
    )
