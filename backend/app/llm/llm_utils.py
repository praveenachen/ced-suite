# utils/llm_utils.py
from __future__ import annotations

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

from backend.app.rag.use_cases import collection_for_use_case, normalize_use_case
from backend.app.llm.client import gemini_sdk_available, generate_json
from backend.app.rag.store import QUANT_COLLECTION

_RAG_AVAILABLE: Optional[bool] = None
logger = logging.getLogger(__name__)
CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "models/gemini-2.5-flash")


def _get_rag_context(
    query: str,
    top_k: int = 6,
    persist_dir: Optional[str] = None,
    collection_name: str = "grant_library",
    where: Optional[Dict[str, Any]] = None,
) -> str:
    """Retrieve relevant grant-library excerpts for the query. Returns empty string if RAG unavailable."""
    global _RAG_AVAILABLE
    if _RAG_AVAILABLE is False:
        return ""
    try:
        from backend.app.rag.retrieve import retrieve
        _RAG_AVAILABLE = True
        out = retrieve(
            query=query,
            top_k=top_k,
            persist_dir=persist_dir,
            collection_name=collection_name,
            where=where,
        )
        return (out or "").strip()
    except Exception:
        _RAG_AVAILABLE = False
        return ""


def _format_references_for_prompt(refs: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    for ref in refs:
        source = ref.get("source", "unknown")
        chunk_index = ref.get("chunk_index", "-")
        source_type = ref.get("source_type", "unknown")
        snippet = ref.get("snippet", "")
        blocks.append(
            f"Source: {source} (chunk {chunk_index}, type: {source_type})\n{snippet}"
        )
    return "\n\n---\n\n".join(blocks)


def _get_rag_context_from_both_sources(
    query: str,
    top_k: int = 6,
    persist_dir: Optional[str] = None,
    app_collection_name: str = "grant_library",
    quant_collection_name: str = QUANT_COLLECTION,
    where: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return combined, app-library, and quant-data references."""
    global _RAG_AVAILABLE
    if _RAG_AVAILABLE is False:
        return [], [], []

    try:
        from backend.app.rag.retrieve import retrieve_from_both_sources

        _RAG_AVAILABLE = True
        out = retrieve_from_both_sources(
            query=query,
            top_k=top_k,
            persist_dir=persist_dir,
            where=where,
            use_hybrid=True,
            rerank_provider=None,
            app_collection_name=app_collection_name,
            quant_collection_name=quant_collection_name,
        )
    except Exception:
        _RAG_AVAILABLE = False
        return [], [], []

    combined_refs: List[Dict[str, Any]] = []
    app_refs: List[Dict[str, Any]] = []
    quant_refs: List[Dict[str, Any]] = []

    for idx, (_, doc, meta, score, source_type) in enumerate(out.get("combined", []), start=1):
        m = meta or {}
        combined_refs.append(
            {
                "rank": idx,
                "source": m.get("source", "unknown"),
                "chunk_index": m.get("chunk_index"),
                "score": score,
                "source_type": source_type or m.get("source_type", "unknown"),
                "snippet": (doc or "").strip()[:500],
            }
        )

    for idx, (_, doc, meta, score) in enumerate(out.get("app_library", []), start=1):
        m = meta or {}
        app_refs.append(
            {
                "rank": idx,
                "source": m.get("source", "unknown"),
                "chunk_index": m.get("chunk_index"),
                "score": score,
                "source_type": m.get("source_type", "app_library"),
                "snippet": (doc or "").strip()[:500],
            }
        )

    for idx, (_, doc, meta, score) in enumerate(out.get("quant_data", []), start=1):
        m = meta or {}
        quant_refs.append(
            {
                "rank": idx,
                "source": m.get("source", "unknown"),
                "chunk_index": m.get("chunk_index"),
                "score": score,
                "source_type": m.get("source_type", "quant_data"),
                "snippet": (doc or "").strip()[:500],
            }
        )

    return combined_refs, app_refs, quant_refs


def _build_payload(
    draft: Dict[str, Any],
    requirements: Dict[str, Any],
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    sections = draft.get("sections", []) or []

    grant_name = (
        requirements.get("grant_name")
        or requirements.get("program_name")
        or requirements.get("name")
        or ""
    )
    raw_req_text = (requirements.get("raw_text") or "")[:6000]

    payload = {
        "grant_name": grant_name,
        "community_profile": {
            "community_name": profile.get("community_name", ""),
            "region": profile.get("region", ""),
            "local_priority": profile.get("local_priority", ""),
            "timeline": profile.get("timeline", ""),
            "challenges": profile.get("challenges", ""),
            "strengths": profile.get("strengths", ""),
            "partners": profile.get("partners", ""),
            "evidence_note": (profile.get("evidence_note") or "").strip(),
            "indicators_before": profile.get("indicators_before", {}) or {},
            "indicators_after": profile.get("indicators_after", {}) or {},
            "scenario": profile.get("scenario", {}) or {},
            "requested_budget": profile.get("requested_budget", None),
        },
        "requirements_text_snippet": raw_req_text,
        "sections_to_improve": [
            {
                "key": s.get("key"),
                "title": s.get("title"),
                "current_body": s.get("body", ""),
                "guidance_from_application": s.get("guidance", ""),
                "word_limit": s.get("word_limit", None),
            }
            for s in sections
        ],
        "instructions": [
            """Rewrite EACH section into a grant-ready, detailed version aligned to the uploaded grant posting.
            You are a senior Canadian grant writer with experience supporting Indigenous,
            rural, and community-led economic development initiatives.
            Write content that is submission-ready with minimal editing.

            Write in long-form paragraphs only (no bullet points, no numbered lists).
            Each section should be 2–5 well-developed paragraphs with clear transitions so
            the proposal reads as a cohesive narrative rather than isolated sections.

            Use respectful, strengths-based, plain-language writing.
            Avoid academic jargon, corporate buzzwords, or generic claims.

            Ground all writing strictly in the provided information.
            Do NOT invent facts, partners, legal status, timelines, funding amounts,
            or commitments that were not explicitly provided.

            If an evidence note, indicators, or before/after metrics are provided,
            use them to:
            - justify the need,
            - explain expected change,
            - and support outcomes in a realistic, defensible way.

            Add practical implementation detail where appropriate, including:
            - phased activities (e.g., planning → implementation → evaluation),
            - who is responsible for what,
            - how community engagement will occur,
            - and key risks with reasonable mitigation approaches.

            Follow standard Canadian grant application norms:
            - clearly distinguish needs, activities, outputs, and outcomes,
            - describe feasibility and readiness,
            - and ensure alignment with funder priorities stated in the application.

            Respect any provided word_limit for each section where possible.
            Prioritize clarity and completeness over verbosity.

            Return JSON ONLY in this exact format:
            {"sections":[{"key":"<section_key>","text":"<rewritten section text>"}]}
            """
        ],
    }
    return payload


def _retrieve_rag_references(
    query: str,
    top_k: int = 5,
    persist_dir: Optional[str] = None,
    collection_name: str = "grant_library",
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return structured RAG references for UI side panels."""
    try:
        from backend.app.rag.retrieve import embed_query
        from backend.app.rag.store import get_collection
    except Exception:
        return []

    q = (query or "").strip()
    if not q:
        return []

    try:
        col = get_collection(persist_dir=persist_dir, collection_name=collection_name)
        q_emb = embed_query(q)
        res = col.query(
            query_embeddings=[q_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
            where=where,
        )
    except Exception:
        return []

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    refs: List[Dict[str, Any]] = []
    for idx, (doc, meta, dist) in enumerate(zip(docs, metas, dists), start=1):
        m = meta or {}
        refs.append(
            {
                "rank": idx,
                "source": m.get("source", "unknown"),
                "chunk_index": m.get("chunk_index"),
                "distance": dist,
                "snippet": (doc or "").strip()[:500],
            }
        )
    return refs


def enhance_sections(
    draft: Dict[str, Any],
    requirements: Dict[str, Any] | None = None,
    profile: Dict[str, Any] | None = None,
    *,
    use_rag: bool = True,
    rag_top_k: int = 6,
    rag_persist_dir: Optional[str] = None,
    rag_collection_name: str = "grant_library",
    use_case: Optional[str] = None,
) -> Dict[str, str]:
    """
    Returns dict mapping section_key -> improved body text
    ex: {"need_statement": "...", "budget_justification": "..."}
    When use_rag is True, retrieves relevant grant-library excerpts and injects them into the prompt.
    """
    if not gemini_sdk_available():
        logger.warning("Gemini SDK not installed; skipping section enhancement")
        return {}

    requirements = requirements or {}
    profile = profile or {}

    sections = draft.get("sections", []) or []
    if not sections:
        return {}

    payload = _build_payload(draft=draft, requirements=requirements, profile=profile)
    use_case_norm = normalize_use_case(use_case)
    rag_collection = collection_for_use_case(use_case_norm, base_collection=rag_collection_name)
    quant_collection = collection_for_use_case(use_case_norm, base_collection=QUANT_COLLECTION)
    payload["rag_use_case"] = use_case_norm

    # RAG: retrieve relevant grant-library context and add to payload when available
    if use_rag:
        grant_name = (
            requirements.get("grant_name")
            or requirements.get("program_name")
            or requirements.get("name")
            or ""
        )
        raw_req = (requirements.get("raw_text") or "")[:2000]
        rag_query = f"{grant_name}\n\n{raw_req}".strip() or "grant application community economic development"
        combined_refs, app_refs, quant_refs = _get_rag_context_from_both_sources(
            query=rag_query,
            top_k=rag_top_k,
            persist_dir=rag_persist_dir,
            app_collection_name=rag_collection,
            quant_collection_name=quant_collection,
        )

        if combined_refs:
            payload["supporting_excerpts"] = _format_references_for_prompt(combined_refs)
        if app_refs:
            payload["grant_library_excerpts"] = _format_references_for_prompt(app_refs)
        if quant_refs:
            payload["quant_data_excerpts"] = _format_references_for_prompt(quant_refs)

        if combined_refs or app_refs or quant_refs:
            payload["instructions"].append(
                "Ground your writing in both narrative evidence and quantitative context from the provided "
                "supporting_excerpts, grant_library_excerpts, and quant_data_excerpts where relevant. "
                "Do not copy verbatim; adapt to the current application."
            )

    system_msg = (
        """You are a senior Canadian grant writer with 10+ years of experience writing successful federal, provincial, and Indigenous community infrastructure and CED grant applications.
        You write in clear, professional, funder-facing language. Your output should be ready for submission with minimal editing. Write with concrete implementation detail.
        Follow the grant posting requirements and do not invent facts.
        When the user payload includes supporting_excerpts, grant_library_excerpts, or quant_data_excerpts,
        use them as reference material to inform phrasing, evidence, and quantitative grounding where relevant;
        do not copy verbatim."""
    )
    user_msg = json.dumps(payload, ensure_ascii=False)

    try:
        data = generate_json(
            model=CHAT_MODEL,
            system_msg=system_msg,
            user_msg=user_msg,
            temperature=0.1,
        )
    except Exception as e:
        raise RuntimeError(f"LLM call failed in Gemini mode: {repr(e)}")

    out: Dict[str, str] = {}
    for item in (data.get("sections", []) or []):
        k = item.get("key")
        t = item.get("text")
        if k and t:
            out[str(k)] = str(t)

    return out


def rewrite_section_with_instruction(
    *,
    section_key: str,
    section_title: str,
    current_text: str,
    instruction: str,
    requirements: Optional[Dict[str, Any]] = None,
    profile: Optional[Dict[str, Any]] = None,
    use_rag: bool = True,
    rag_top_k: int = 5,
    rag_persist_dir: Optional[str] = None,
    rag_collection_name: str = "grant_library",
    use_case: Optional[str] = None,
) -> Dict[str, Any]:
    """Rewrite a single section using user instruction; returns text + structured references."""
    if not gemini_sdk_available():
        logger.warning("Gemini SDK not installed; skipping section rewrite")
        return {"text": (current_text or "").strip(), "references": []}

    requirements = requirements or {}
    profile = profile or {}

    use_case_norm = normalize_use_case(use_case)
    rag_collection = collection_for_use_case(use_case_norm, base_collection=rag_collection_name)
    quant_collection = collection_for_use_case(use_case_norm, base_collection=QUANT_COLLECTION)

    grant_name = (
        requirements.get("grant_name")
        or requirements.get("program_name")
        or requirements.get("name")
        or ""
    )
    rag_query = "\n\n".join(
        [
            grant_name,
            section_title or section_key,
            instruction or "",
            (current_text or "")[:1200],
            (requirements.get("raw_text") or "")[:1200],
        ]
    ).strip()

    references: List[Dict[str, Any]] = []
    excerpts = ""
    if use_rag:
        combined_refs, app_refs, quant_refs = _get_rag_context_from_both_sources(
            query=rag_query,
            top_k=rag_top_k,
            persist_dir=rag_persist_dir,
            app_collection_name=rag_collection,
            quant_collection_name=quant_collection,
        )
        references = combined_refs
        excerpts = _format_references_for_prompt(combined_refs)

    payload = {
        "grant_name": grant_name,
        "section": {
            "key": section_key,
            "title": section_title,
            "current_text": current_text or "",
        },
        "instruction": (instruction or "").strip(),
        "community_profile": profile,
        "requirements_text_snippet": (requirements.get("raw_text") or "")[:3000],
        "rag_use_case": use_case_norm,
        "supporting_excerpts": excerpts,
    }

    system_msg = (
        "You are a senior Canadian grant writer. Rewrite one section only. "
        "Follow user instruction exactly, keep factual integrity, and do not invent facts. "
        "If source excerpts are provided, use them only as reference guidance and do not copy verbatim. "
        "Return JSON only: {\"text\":\"<rewritten section>\"}."
    )
    user_msg = json.dumps(payload, ensure_ascii=False)

    try:
        data = generate_json(
            model=CHAT_MODEL,
            system_msg=system_msg,
            user_msg=user_msg,
            temperature=0.2,
        )
    except Exception as e:
        raise RuntimeError(f"Section rewrite failed in Gemini mode: {repr(e)}")

    text = str(data.get("text") or "").strip() or (current_text or "").strip()
    return {"text": text, "references": references}
