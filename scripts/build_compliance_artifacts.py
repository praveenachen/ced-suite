from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from backend.app.compliance.config import CHECKS_PATH, CHUNKS_PATH, MANIFEST_PATH, SOURCE_DOCS_DIR
from backend.app.compliance.document_processing import extract_pdf_pages, normalize_whitespace, smart_chunk_paragraphs, stable_chunk_id


@dataclass(frozen=True)
class DocumentSpec:
    filename: str
    canonical_title: str
    short_description: str
    priority_level: str
    document_type: str
    community_scope: List[str]
    framework_tags: List[str]
    section_tags: List[str]
    include_in_primary_retrieval: bool
    brief_description: str


DOCUMENT_SPECS: List[DocumentSpec] = [
    DocumentSpec(
        filename="TCPS2 Chapter 9.pdf",
        canonical_title="TCPS 2 Chapter 9",
        short_description="Canadian research ethics guidance for research involving First Nations, Inuit, and Metis peoples.",
        priority_level="core",
        document_type="ethics_guidance",
        community_scope=["First Nations", "Inuit", "Metis"],
        framework_tags=["TCPS2", "ethics"],
        section_tags=["community_engagement", "ethical_research", "data_governance"],
        include_in_primary_retrieval=True,
        brief_description="Explains ethical obligations for Indigenous research, including community engagement and collective welfare.",
    ),
    DocumentSpec(
        filename="OCAP Principles.pdf",
        canonical_title="OCAP Principles",
        short_description="First Nations data governance principles focused on ownership, control, access, and possession.",
        priority_level="core",
        document_type="data_governance_guidance",
        community_scope=["First Nations"],
        framework_tags=["OCAP", "data_governance"],
        section_tags=["data_governance", "ethical_research", "community_engagement"],
        include_in_primary_retrieval=True,
        brief_description="Defines expectations for First Nations data ownership and governance.",
    ),
    DocumentSpec(
        filename="National Inuit Strategy on Research (Full).pdf",
        canonical_title="National Inuit Strategy on Research",
        short_description="Inuit-led strategy for research governance, partnerships, data, and capacity development.",
        priority_level="core",
        document_type="research_strategy",
        community_scope=["Inuit"],
        framework_tags=["NISR", "Inuit_governance", "IQ"],
        section_tags=["community_engagement", "data_governance", "community_benefit", "iq_collaboration", "iq_skills_development"],
        include_in_primary_retrieval=True,
        brief_description="Sets Inuit research expectations around governance, benefit, partnership, and data sovereignty.",
    ),
    DocumentSpec(
        filename="Negotiating Research Relationships with Inuit Communities.pdf",
        canonical_title="Negotiating Research Relationships with Inuit Communities",
        short_description="Practical guide for initiating, negotiating, and maintaining respectful Inuit research relationships.",
        priority_level="core",
        document_type="community_relationship_guidance",
        community_scope=["Inuit"],
        framework_tags=["Inuit_governance", "community_engagement"],
        section_tags=["community_engagement", "ethical_research", "implementation_plan", "iq_collaboration"],
        include_in_primary_retrieval=True,
        brief_description="Provides practical expectations for communication, negotiated roles, and respectful Inuit community engagement.",
    ),
    DocumentSpec(
        filename="paw_2026-2027_6161886_inst_1768505132675_eng.pdf",
        canonical_title="ISC LEDSP/CORP Application Instructions 2026-2027",
        short_description="Indigenous Services Canada application instructions for LEDSP/CORP eligibility, project framing, and cost readiness.",
        priority_level="core",
        document_type="program_instructions",
        community_scope=["First Nations", "Inuit", "Metis"],
        framework_tags=["ISC_LEDSP_CORP", "funding_requirements"],
        section_tags=["implementation_plan", "budget_alignment", "community_benefit", "land_environment", "regulatory_readiness", "staff_capacity"],
        include_in_primary_retrieval=True,
        brief_description="Defines LEDSP/CORP eligibility, project requirements, and application field expectations.",
    ),
    DocumentSpec(
        filename="Indigenous Peoples Funding & Resource Guide.pdf",
        canonical_title="Indigenous Peoples Funding and Resource Guide",
        short_description="Reference guide to Indigenous funding and capacity-building support resources.",
        priority_level="secondary",
        document_type="funding_reference",
        community_scope=["First Nations", "Inuit", "Metis"],
        framework_tags=["funding_reference"],
        section_tags=["staff_capacity", "sustainability", "community_benefit"],
        include_in_primary_retrieval=True,
        brief_description="Supports funding readiness and ecosystem awareness but is not a primary compliance authority.",
    ),
    DocumentSpec(
        filename="Indigenous Population Profile, 2021 Census.pdf",
        canonical_title="Indigenous Population Profile, 2021 Census",
        short_description="Statistics Canada release summarizing Indigenous population demographics and growth.",
        priority_level="secondary",
        document_type="statistical_reference",
        community_scope=["First Nations", "Inuit", "Metis"],
        framework_tags=["evidence_context"],
        section_tags=["community_benefit", "evaluation_plan"],
        include_in_primary_retrieval=False,
        brief_description="Useful for contextual evidence but not a direct compliance source.",
    ),
    DocumentSpec(
        filename="Inuit-Nunangat-Policy-EN.pdf",
        canonical_title="Inuit Nunangat Policy",
        short_description="Federal policy guidance for designing and delivering policies and programs in Inuit Nunangat.",
        priority_level="secondary",
        document_type="policy_guidance",
        community_scope=["Inuit"],
        framework_tags=["Inuit_policy", "Inuit_governance"],
        section_tags=["community_benefit", "implementation_plan", "iq_service_to_community", "iq_environmental_stewardship"],
        include_in_primary_retrieval=True,
        brief_description="Supports Inuit-specific program design with self-determination and Inuit Nunangat relevance.",
    ),
    DocumentSpec(
        filename="IDS 1.pdf",
        canonical_title="Indigenous Data Sovereignty in Open Data",
        short_description="Background discussion of Indigenous data sovereignty and open data risks.",
        priority_level="secondary",
        document_type="governance_support",
        community_scope=["First Nations", "Inuit", "Metis"],
        framework_tags=["IDS", "data_governance"],
        section_tags=["data_governance", "ethical_research"],
        include_in_primary_retrieval=False,
        brief_description="Supports governance interpretation but is not a primary compliance authority.",
    ),
]


CHECK_SPECS: List[Dict[str, object]] = [
    {
        "check_id": "community_engagement_001",
        "title": "Community engagement is clearly described",
        "section": "community_engagement",
        "category": "community_engagement",
        "check_text": "The proposal should explain how the affected Indigenous community will be engaged in project planning, implementation, or oversight.",
        "explanation": "TCPS2 Chapter 9 emphasizes engagement when research may affect the welfare of Indigenous communities.",
        "failure_signals": ["No named community partners", "No engagement process", "Engagement appears one-way or post hoc"],
        "evidence_examples": ["Named Inuit or Indigenous partner bodies", "Decision-making role for community", "Clear engagement timeline"],
        "severity_if_failed": "major",
        "framework_tags": ["TCPS2", "ethics"],
        "community_scope": ["First Nations", "Inuit", "Metis"],
        "source_document": "TCPS 2 Chapter 9",
        "source_section": "Introduction",
        "search_terms": ["engaged in a manner appropriate to the nature and context of the research"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "ethical_research_001",
        "title": "Proposal addresses collective welfare and respectful conduct",
        "section": "community_engagement",
        "category": "ethical_research",
        "check_text": "Research-oriented sections should show respect for collective welfare, reciprocity, and appropriate community protocols.",
        "explanation": "TCPS2 Chapter 9 frames Indigenous research ethics around collective welfare and respectful relationships.",
        "failure_signals": ["Only individual benefits described", "No reciprocity", "No protocol or ethics references"],
        "evidence_examples": ["Reciprocal benefits", "Respectful governance process", "Ethics or protocol awareness"],
        "severity_if_failed": "major",
        "framework_tags": ["TCPS2", "ethics"],
        "community_scope": ["First Nations", "Inuit", "Metis"],
        "source_document": "TCPS 2 Chapter 9",
        "source_section": "Introduction",
        "search_terms": ["collective welfare", "reciprocity"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "data_governance_001",
        "title": "Data ownership and control are addressed",
        "section": "data_governance",
        "category": "data_governance",
        "check_text": "If community data will be collected or used, the proposal should explain community ownership, control, access, or possession expectations.",
        "explanation": "OCAP requires clear treatment of First Nations control over community data and information management.",
        "failure_signals": ["Data collection mentioned without governance", "Open sharing promised without controls", "No access or storage plan"],
        "evidence_examples": ["Data stewardship commitments", "Community approval for access", "Storage and possession terms"],
        "severity_if_failed": "critical",
        "framework_tags": ["OCAP", "data_governance"],
        "community_scope": ["First Nations"],
        "source_document": "OCAP Principles",
        "source_section": "Ownership, Control, Access and Possession",
        "search_terms": ["Ownership, Control, Access and Possession"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "data_governance_002",
        "title": "Indigenous data sovereignty risks are managed",
        "section": "data_governance",
        "category": "data_governance",
        "check_text": "Sections involving data should avoid implying unrestricted open use of Indigenous community data.",
        "explanation": "Indigenous data sovereignty guidance warns that open data approaches can conflict with Indigenous rights and privacy expectations.",
        "failure_signals": ["Commitment to public release of raw data", "No privacy boundary", "No consent or governance condition"],
        "evidence_examples": ["Restricted release conditions", "Community review prior to sharing", "Controlled access"],
        "severity_if_failed": "major",
        "framework_tags": ["IDS", "data_governance"],
        "community_scope": ["First Nations", "Inuit", "Metis"],
        "source_document": "Indigenous Data Sovereignty in Open Data",
        "source_section": "Key points",
        "search_terms": ["Indigenous peoples to control data from and about their communities and lands"],
        "priority_weight": 0.7,
    },
    {
        "check_id": "inuit_governance_001",
        "title": "Inuit-specific work is aligned with Inuit-led governance",
        "section": "community_engagement",
        "category": "community_engagement",
        "check_text": "Inuit-specific proposals should show Inuit involvement in setting priorities, governance, or oversight.",
        "explanation": "The National Inuit Strategy on Research centers Inuit governance over research agendas, partnerships, and decisions.",
        "failure_signals": ["Inuit are only beneficiaries", "No Inuit partner named", "No governance role for Inuit organization"],
        "evidence_examples": ["Inuit-led steering committee", "Partnership with regional Inuit organization", "Shared decision-making"],
        "severity_if_failed": "critical",
        "framework_tags": ["NISR", "Inuit_governance"],
        "community_scope": ["Inuit"],
        "source_document": "National Inuit Strategy on Research",
        "source_section": "Strategy overview",
        "search_terms": ["Inuit governance in research"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "community_benefit_001",
        "title": "Inuit-specific work identifies tangible community benefit",
        "section": "implementation_plan",
        "category": "community_benefit",
        "check_text": "Inuit-specific sections should explain how the work benefits Inuit communities and not only institutional goals.",
        "explanation": "The National Inuit Strategy on Research and Inuit Nunangat Policy both emphasize Inuit self-determination and benefit.",
        "failure_signals": ["Benefits only described for researchers", "No local outcomes", "No community-facing deliverables"],
        "evidence_examples": ["Community-facing outputs", "Service improvements", "Local benefits or employment"],
        "severity_if_failed": "major",
        "framework_tags": ["NISR", "Inuit_policy"],
        "community_scope": ["Inuit"],
        "source_document": "National Inuit Strategy on Research",
        "source_section": "Strategy overview",
        "search_terms": ["Inuit self-determination"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "iq_collaboration_001",
        "title": "Proposal reflects collaborative Inuit decision-making",
        "section": "community_engagement",
        "category": "iq_collaboration",
        "check_text": "Where an Inuit-specific context is clear, the proposal should show collaborative and consensus-oriented planning.",
        "explanation": "Aajiiqatigiinniq and Piliriqatigiinniq support consensus building and collaborative work in Inuit contexts.",
        "failure_signals": ["Top-down plan", "No collaborative mechanism", "No consensus or shared planning process"],
        "evidence_examples": ["Shared planning tables", "Consensus-oriented decision process", "Collaborative implementation"],
        "severity_if_failed": "major",
        "framework_tags": ["IQ", "Inuit_governance"],
        "community_scope": ["Inuit"],
        "source_document": "National Inuit Strategy on Research",
        "source_section": "Strategy overview",
        "search_terms": ["partnership", "capacity"],
        "priority_weight": 0.95,
    },
    {
        "check_id": "iq_skills_development_001",
        "title": "Proposal supports Inuit skills development",
        "section": "staff_organization",
        "category": "iq_skills_development",
        "check_text": "Inuit-specific proposals should consider local skills development, mentorship, or capacity strengthening where relevant.",
        "explanation": "Pilimmaksarniq and related Inuit principles support skills development and capacity building.",
        "failure_signals": ["External experts only", "No local training or roles", "No community capacity outcome"],
        "evidence_examples": ["Training plan", "Mentorship roles", "Community employment or skills transfer"],
        "severity_if_failed": "minor",
        "framework_tags": ["IQ", "NISR"],
        "community_scope": ["Inuit"],
        "source_document": "National Inuit Strategy on Research",
        "source_section": "Strategy overview",
        "search_terms": ["capacity", "skills"],
        "priority_weight": 0.9,
    },
    {
        "check_id": "staff_capacity_001",
        "title": "Responsible delivery team is identified",
        "section": "staff_organization",
        "category": "staff_capacity",
        "check_text": "The proposal should identify who will lead the project and how responsibilities are divided.",
        "explanation": "LEDSP/CORP reviewers need enough detail to judge readiness and whether the project can be delivered.",
        "failure_signals": ["No responsible team members", "No roles or departments", "No delivery ownership"],
        "evidence_examples": ["Named lead", "Implementation responsibilities", "Operational staffing plan"],
        "severity_if_failed": "major",
        "framework_tags": ["ISC_LEDSP_CORP"],
        "community_scope": ["First Nations", "Inuit", "Metis"],
        "source_document": "ISC LEDSP/CORP Application Instructions 2026-2027",
        "source_section": "Applicant information",
        "search_terms": ["Contact person", "Applicant name"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "implementation_plan_001",
        "title": "Project description is eligible and concrete",
        "section": "implementation_plan",
        "category": "implementation_plan",
        "check_text": "The proposal should clearly describe the project, the activities to be delivered, and how they meet program objectives.",
        "explanation": "ISC instructions ask reviewers to assess whether the project is eligible and aligned to LEDSP or CORP objectives.",
        "failure_signals": ["Activities are vague", "No link to objectives", "No deliverables or outputs"],
        "evidence_examples": ["Concrete activities", "Program objective alignment", "Defined outputs"],
        "severity_if_failed": "major",
        "framework_tags": ["ISC_LEDSP_CORP"],
        "community_scope": ["First Nations", "Inuit", "Metis"],
        "source_document": "ISC LEDSP/CORP Application Instructions 2026-2027",
        "source_section": "Purpose",
        "search_terms": ["The proposed project meets at least one of the LEDSP or CORP objectives"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "budget_alignment_001",
        "title": "Requested costs are tied to eligible project work",
        "section": "budget_justification",
        "category": "budget_alignment",
        "check_text": "Budget sections should explain why the requested funds are needed for eligible project costs.",
        "explanation": "ISC instructions explicitly assess whether requested funds are eligible project costs.",
        "failure_signals": ["No link between costs and activities", "No justification", "Administrative costs not explained"],
        "evidence_examples": ["Line-item rationale", "Cost tied to activity", "Eligibility framing"],
        "severity_if_failed": "major",
        "framework_tags": ["ISC_LEDSP_CORP"],
        "community_scope": ["First Nations", "Inuit", "Metis"],
        "source_document": "ISC LEDSP/CORP Application Instructions 2026-2027",
        "source_section": "Purpose",
        "search_terms": ["requested funds are eligible project costs"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "regulatory_readiness_001",
        "title": "Land and environmental implications are acknowledged when relevant",
        "section": "implementation_plan",
        "category": "land_environment",
        "check_text": "If the project affects land, infrastructure, or site use, the proposal should show awareness of land or environmental considerations.",
        "explanation": "LEDSP/CORP review includes project readiness and practical feasibility, including site-related considerations when applicable.",
        "failure_signals": ["Site work described with no land context", "No permissions or location details", "No environmental considerations"],
        "evidence_examples": ["Site readiness", "Permissions or approvals", "Environmental stewardship measures"],
        "severity_if_failed": "minor",
        "framework_tags": ["ISC_LEDSP_CORP"],
        "community_scope": ["First Nations", "Inuit", "Metis"],
        "source_document": "ISC LEDSP/CORP Application Instructions 2026-2027",
        "source_section": "Project fields",
        "search_terms": ["The proposed project is an eligible project"],
        "priority_weight": 0.9,
    },
    {
        "check_id": "implementation_plan_002",
        "title": "Research relationship is negotiated early",
        "section": "community_engagement",
        "category": "community_engagement",
        "check_text": "Inuit research proposals should show early contact and negotiated expectations with the community.",
        "explanation": "The Inuit community relationship guide recommends early contact, negotiated roles, and clear communication strategies.",
        "failure_signals": ["Community contact deferred until after funding", "No communication plan", "No negotiated expectations"],
        "evidence_examples": ["Early community contact", "Negotiated relationship", "Communication strategy"],
        "severity_if_failed": "major",
        "framework_tags": ["Inuit_governance"],
        "community_scope": ["Inuit"],
        "source_document": "Negotiating Research Relationships with Inuit Communities",
        "source_section": "Elements of a negotiated research relationship",
        "search_terms": ["Elements of a negotiated research relationship", "Initiating community contact", "Communication strategy"],
        "priority_weight": 1.0,
    },
    {
        "check_id": "iq_service_to_community_001",
        "title": "Inuit-specific work is framed as service to community",
        "section": "implementation_plan",
        "category": "iq_service_to_community",
        "check_text": "Inuit-specific sections should describe how the project serves community priorities and public value in Inuit Nunangat.",
        "explanation": "Pijitsirniq and the Inuit Nunangat Policy support service to community and Inuit self-determination.",
        "failure_signals": ["Institution-first framing", "No community priority stated", "Benefits detached from local needs"],
        "evidence_examples": ["Community-defined priority", "Public value", "Inuit Nunangat relevance"],
        "severity_if_failed": "major",
        "framework_tags": ["IQ", "Inuit_policy"],
        "community_scope": ["Inuit"],
        "source_document": "Inuit Nunangat Policy",
        "source_section": "Policy overview",
        "search_terms": ["support Inuit self-determination"],
        "priority_weight": 0.85,
    },
]


def repo_doc_path(filename: str) -> Path:
    for subdir in ("core", "secondary", "low_priority"):
        candidate = SOURCE_DOCS_DIR / subdir / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(filename)


def page_paragraphs(page_text: str) -> List[str]:
    normalized = normalize_whitespace(page_text)
    return [part.strip() for part in re.split(r"\n{2,}|(?<=[.!?])\s{2,}", normalized) if part.strip()]


def build_manifest() -> List[Dict[str, object]]:
    return [
        {
            "filename": spec.filename,
            "canonical_title": spec.canonical_title,
            "short_description": spec.short_description,
            "priority_level": spec.priority_level,
            "document_type": spec.document_type,
            "community_scope": spec.community_scope,
            "framework_tags": spec.framework_tags,
            "section_tags": spec.section_tags,
            "include_in_primary_retrieval": spec.include_in_primary_retrieval,
        }
        for spec in DOCUMENT_SPECS
    ]


def build_chunks() -> List[Dict[str, object]]:
    chunks: List[Dict[str, object]] = []
    for spec in DOCUMENT_SPECS:
        pages = extract_pdf_pages(repo_doc_path(spec.filename))
        for page_index, page_text in enumerate(pages, start=1):
            paragraphs = page_paragraphs(page_text)
            for chunk_text in smart_chunk_paragraphs(paragraphs):
                chunks.append(
                    {
                        "chunk_id": stable_chunk_id(spec.canonical_title, page_index, chunk_text),
                        "title": f"{spec.canonical_title} - Page {page_index}",
                        "brief_description": spec.brief_description,
                        "source_document": spec.canonical_title,
                        "document_type": spec.document_type,
                        "priority_level": spec.priority_level,
                        "chunk_text": chunk_text,
                        "section_tags": spec.section_tags,
                        "community_scope": spec.community_scope,
                        "framework_tags": spec.framework_tags,
                        "year_if_known": infer_year(page_text),
                        "page_number_if_known": page_index,
                    }
                )
    return chunks


def infer_year(text: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", text or "")
    return int(match.group(0)) if match else None


def find_excerpt(pages: Iterable[str], search_terms: Iterable[str]) -> tuple[str, int | None]:
    normalized_pages = [normalize_whitespace(page) for page in pages]
    for term in search_terms:
        term_lower = term.lower()
        for page_number, page_text in enumerate(normalized_pages, start=1):
            idx = page_text.lower().find(term_lower)
            if idx >= 0:
                start = max(0, idx - 140)
                end = min(len(page_text), idx + len(term) + 240)
                return page_text[start:end].strip(), page_number
    for page_number, page_text in enumerate(normalized_pages, start=1):
        if page_text:
            return page_text[:380], page_number
    return "", None


def build_checks() -> List[Dict[str, object]]:
    document_pages = {spec.canonical_title: extract_pdf_pages(repo_doc_path(spec.filename)) for spec in DOCUMENT_SPECS}
    checks: List[Dict[str, object]] = []
    for spec in CHECK_SPECS:
        excerpt, page_number = find_excerpt(document_pages[spec["source_document"]], spec["search_terms"])
        check = {key: value for key, value in spec.items() if key != "search_terms"}
        check["source_excerpt"] = excerpt
        if page_number is not None:
            check["source_section"] = f'{check["source_section"]} (page {page_number})'
        checks.append(check)
    return checks


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    write_json(MANIFEST_PATH, build_manifest())
    write_json(CHUNKS_PATH, build_chunks())
    write_json(CHECKS_PATH, build_checks())


if __name__ == "__main__":
    main()
