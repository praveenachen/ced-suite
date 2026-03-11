from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Set


@dataclass(frozen=True)
class SectionProfile:
    normalized_name: str
    retrieval_tags: List[str]
    aliases: List[str]


SECTION_PROFILES: List[SectionProfile] = [
    SectionProfile(
        normalized_name="staff_organization",
        retrieval_tags=["staff_capacity", "implementation_plan", "community_engagement"],
        aliases=["staff_organization", "staff organization", "team", "project_team"],
    ),
    SectionProfile(
        normalized_name="community_engagement",
        retrieval_tags=["community_engagement", "community_benefit", "ethical_research"],
        aliases=["community_engagement", "engagement", "consultation", "partnerships"],
    ),
    SectionProfile(
        normalized_name="implementation_plan",
        retrieval_tags=["implementation_plan", "evaluation_plan", "sustainability"],
        aliases=["implementation_plan", "workplan", "project_plan", "activities"],
    ),
    SectionProfile(
        normalized_name="budget_justification",
        retrieval_tags=["budget_alignment", "community_benefit", "land_environment"],
        aliases=["budget", "budget_justification", "financing", "costs"],
    ),
    SectionProfile(
        normalized_name="data_governance",
        retrieval_tags=["data_governance", "ethical_research", "regulatory_readiness"],
        aliases=["data_governance", "data_management", "privacy", "ethics"],
    ),
    SectionProfile(
        normalized_name="evaluation_plan",
        retrieval_tags=["evaluation_plan", "community_benefit", "skills_development"],
        aliases=["evaluation_plan", "outcomes", "measurement", "monitoring"],
    ),
]


SECTION_ALIASES: Dict[str, SectionProfile] = {
    alias: profile
    for profile in SECTION_PROFILES
    for alias in profile.aliases
}

INUIT_KEYWORDS = {
    "inuit",
    "nunavut",
    "nunavik",
    "nunatsiavut",
    "inuvialuit",
    "inuit nunangat",
    "iq",
    "inuit qaujimajatuqangit",
}

FRAMEWORK_KEYWORDS = {
    "TCPS2": {"tcps2", "ethics approval", "community welfare"},
    "OCAP": {"ocap", "ownership", "control", "access", "possession"},
    "NISR": {"inuit research", "inuit governance", "inuit-led"},
    "ISC_LEDSP_CORP": {"corp", "ledsp", "eligible costs", "eligible recipient"},
}


def normalize_section_name(section_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (section_name or "").strip().lower()).strip("_")
    if slug in SECTION_ALIASES:
        return SECTION_ALIASES[slug].normalized_name
    if "staff" in slug and any(term in slug for term in ["organization", "organisational", "organizational", "team"]):
        return "staff_organization"
    if "community" in slug and any(term in slug for term in ["engagement", "consult", "partnership", "relationship"]):
        return "community_engagement"
    if any(term in slug for term in ["implementation", "activities", "workplan", "project_plan", "project_description"]):
        return "implementation_plan"
    if any(term in slug for term in ["budget", "cost", "financial", "financing"]):
        return "budget_justification"
    if any(term in slug for term in ["evaluation", "outcome", "monitor", "measurement"]):
        return "evaluation_plan"
    if "data" in slug and any(term in slug for term in ["governance", "management", "privacy", "ownership"]):
        return "data_governance"
    return slug or "unknown_section"


def section_tags_for_name(section_name: str) -> List[str]:
    normalized = normalize_section_name(section_name)
    profile = SECTION_ALIASES.get(normalized)
    if profile:
        return profile.retrieval_tags
    return [normalized]


def detect_inuit_specific(text: str, section_name: str = "") -> bool:
    haystack = f"{section_name} {text}".lower()
    return any(keyword in haystack for keyword in INUIT_KEYWORDS)


def infer_framework_tags(text: str) -> List[str]:
    haystack = text.lower()
    tags: Set[str] = set()
    for tag, keywords in FRAMEWORK_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            tags.add(tag)
    return sorted(tags)
