from typing import Dict, Any, List

def fit_programs(local_priority: str, programs: list[dict]) -> list[dict]:
    # keep your existing logic
    # (not rewriting here since you already have it working)
    scored = []
    pr = (local_priority or "").lower()
    for p in programs:
        focus = [str(x).lower() for x in p.get("focus", [])]
        score = 1 if any(pr in f or f in pr for f in focus) else 0
        if score:
            scored.append(p)
    return scored

def generate_proposal_from_requirements(profile: Dict[str, Any], requirements: Dict[str, Any], requested_budget: int) -> Dict[str, Any]:
    """
    Generates a draft that follows the uploaded requirements section list.
    This is the key shift away from a generic template.
    """
    sections_out: List[Dict[str, str]] = []

    for sec in requirements.get("sections", []):
        key = sec.get("key", "section")
        title = sec.get("title", "Section")
        guidance = sec.get("guidance", "")

        body = _baseline_section_writer(
            title=title,
            guidance=guidance,
            profile=profile,
            requested_budget=requested_budget,
        )

        sections_out.append({
            "key": key,
            "title": title,
            "body": body,
            "guidance": guidance,
        })

    return {
        "meta": {
            "community_name": profile.get("community_name"),
            "local_priority": profile.get("local_priority"),
            "requested_budget": requested_budget,
            "grant_name": requirements.get("grant_name", ""),
        },
        "sections": sections_out
    }

def _baseline_section_writer(title: str, guidance: str, profile: Dict[str, Any], requested_budget: int) -> str:
    """
    Non-LLM baseline text. The LLM can polish later.
    """
    c = profile.get("community_name", "")
    region = profile.get("region", "")
    priority = profile.get("local_priority", "")
    challenges = profile.get("challenges", "")
    strengths = profile.get("strengths", "")
    partners = profile.get("partners", "")
    timeline = profile.get("timeline", "")

    base = []

    # Always anchor to community + priority
    base.append(f"{c} ({region}) is seeking ${requested_budget:,} to address {priority}.")

    # Add detail when available
    if challenges:
        base.append(f"Local context: {challenges}")
    if strengths:
        base.append(f"Community strengths/assets: {strengths}")
    if partners:
        base.append(f"Partners and roles: {partners}")
    if timeline:
        base.append(f"Timeline: {timeline}")

    # Use any extracted guidance as “what the funder is asking for”
    if guidance:
        base.append("")
        base.append("Application guidance (what this section should cover):")
        base.append(guidance)

    return "\n\n".join(base).strip()
