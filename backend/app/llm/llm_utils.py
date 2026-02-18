# utils/llm_utils.py
from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional

_RAG_AVAILABLE: Optional[bool] = None


def _get_rag_context(
    query: str,
    top_k: int = 6,
    persist_dir: Optional[str] = None,
    collection_name: str = "grant_library",
) -> str:
    """Retrieve relevant grant-library excerpts for the query. Returns empty string if RAG unavailable."""
    global _RAG_AVAILABLE
    if _RAG_AVAILABLE is False:
        return ""
    try:
        from backend.app.rag.retrieve import retrieve
        _RAG_AVAILABLE = True
        out = retrieve(query=query, top_k=top_k, persist_dir=persist_dir, collection_name=collection_name)
        return (out or "").strip()
    except Exception:
        _RAG_AVAILABLE = False
        return ""


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


def enhance_sections(
    draft: Dict[str, Any],
    requirements: Dict[str, Any] | None = None,
    profile: Dict[str, Any] | None = None,
    *,
    use_rag: bool = True,
    rag_top_k: int = 6,
    rag_persist_dir: Optional[str] = None,
    rag_collection_name: str = "grant_library",
) -> Dict[str, str]:
    """
    Returns dict mapping section_key -> improved body text
    ex: {"need_statement": "...", "budget_justification": "..."}
    When use_rag is True, retrieves relevant grant-library excerpts and injects them into the prompt.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # fail gracefully (app still works)
        return {}

    requirements = requirements or {}
    profile = profile or {}

    sections = draft.get("sections", []) or []
    if not sections:
        return {}

    payload = _build_payload(draft=draft, requirements=requirements, profile=profile)

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
        rag_context = _get_rag_context(
            query=rag_query,
            top_k=rag_top_k,
            persist_dir=rag_persist_dir,
            collection_name=rag_collection_name,
        )
        if rag_context:
            payload["grant_library_excerpts"] = rag_context
            payload["instructions"].append(
                "Use the attached grant_library_excerpts when relevant to strengthen your writing with "
                "evidence, phrasing, or structure from successful grant materials. Do not copy verbatim; "
                "adapt to the current application. Cite or echo themes where they align with the requirements."
            )

    system_msg = (
        """You are a senior Canadian grant writer with 10+ years of experience writing successful federal, provincial, and Indigenous community infrastructure and CED grant applications.
        You write in clear, professional, funder-facing language. Your output should be ready for submission with minimal editing. Write with concrete implementation detail.
        Follow the grant posting requirements and do not invent facts.
        When the user payload includes grant_library_excerpts, use them as reference material to inform phrasing and structure where relevant; do not copy verbatim."""
    )
    user_msg = json.dumps(payload, ensure_ascii=False)

    # --- Prefer OpenAI Python SDK v1+ ---
    try:
        from openai import OpenAI  # v1+
        client = OpenAI(api_key=api_key)

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)

    except Exception as e_v1:
        # --- Fallback for legacy openai<1.0 ---
        try:
            import openai  # legacy
            openai.api_key = api_key

            r = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
            )
            content = r["choices"][0]["message"]["content"] or "{}"
            data = json.loads(content)

        except Exception as e_legacy:
            # IMPORTANT: don't silently swallow both failures
            raise RuntimeError(
                "LLM call failed in both OpenAI SDK v1+ and legacy modes."
                f"\n\nv1+ error: {repr(e_v1)}"
                f"\nlegacy error: {repr(e_legacy)}"
            )

    out: Dict[str, str] = {}
    for item in (data.get("sections", []) or []):
        k = item.get("key")
        t = item.get("text")
        if k and t:
            out[str(k)] = str(t)

    return out
