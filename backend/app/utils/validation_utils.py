from typing import Dict, Any, List

def validate_proposal_against_requirements(draft: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, List[str]]:
    gaps: List[str] = []
    warnings: List[str] = []

    req_sections = requirements.get("sections", [])
    draft_sections = draft.get("sections", [])

    req_keys = {s.get("key") for s in req_sections}
    draft_keys = {s.get("key") for s in draft_sections}

    missing = [s.get("title", s.get("key", "section")) for s in req_sections if s.get("key") not in draft_keys]
    if missing:
        gaps.append("Missing required sections: " + ", ".join(missing))

    # crude “too short” checks
    for s in draft_sections:
        body = (s.get("body") or "").strip()
        title = s.get("title", "Section")
        if len(body) < 200:
            warnings.append(f"Section '{title}' looks short—may need more detail.")

    # must-include phrases (if present in requirements)
    must_include = requirements.get("must_include", []) or []
    full_text = "\n\n".join([(s.get("body") or "") for s in draft_sections]).lower()

    for phrase in must_include:
        if str(phrase).lower() not in full_text:
            gaps.append(f"Required item not found: '{phrase}'")

    return {"gaps": gaps, "warnings": warnings}
