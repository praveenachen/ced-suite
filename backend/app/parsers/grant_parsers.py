from __future__ import annotations
from typing import Dict, Any, Tuple
import re

def _read_txt(file) -> str:
    return file.getvalue().decode("utf-8", errors="ignore")

def _read_pdf(file) -> str:
    # best-effort PDF text extraction (no OCR)
    try:
        import PyPDF2
    except Exception:
        return ""
    try:
        reader = PyPDF2.PdfReader(file)
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        return ""

def _read_docx(file) -> str:
    try:
        import docx  # python-docx
    except Exception:
        return ""
    try:
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception:
        return ""

def _extract_sections_from_text(text: str) -> list[dict]:
    """
    Very simple heuristic section extraction. Works best if the PDF/DOCX has headings.
    If it can't find headings, returns a generic list.
    """
    cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not cleaned:
        return [
            {"key": "need_statement", "title": "Need Statement", "guidance": ""},
            {"key": "project_description", "title": "Project Description", "guidance": ""},
            {"key": "workplan", "title": "Workplan / Activities", "guidance": ""},
            {"key": "evaluation", "title": "Evaluation & Metrics", "guidance": ""},
            {"key": "budget_justification", "title": "Budget Justification", "guidance": ""},
        ]

    # Look for heading-like lines
    lines = [ln.strip() for ln in cleaned.splitlines()]
    heading_idxs = []
    for i, ln in enumerate(lines):
        if len(ln) >= 6 and len(ln) <= 90 and (ln.isupper() or ln.endswith(":")):
            heading_idxs.append(i)

    # If few headings, return default sections but keep raw text as guidance
    if len(heading_idxs) < 2:
        return [
            {"key": "need_statement", "title": "Need Statement", "guidance": "Use application text as guidance."},
            {"key": "project_description", "title": "Project Description", "guidance": "Use application text as guidance."},
            {"key": "workplan", "title": "Workplan / Activities", "guidance": "Use application text as guidance."},
            {"key": "evaluation", "title": "Evaluation & Metrics", "guidance": "Use application text as guidance."},
            {"key": "budget_justification", "title": "Budget Justification", "guidance": "Use application text as guidance."},
        ]

    # Build section objects from headings
    sections = []
    for idx, start in enumerate(heading_idxs):
        end = heading_idxs[idx + 1] if idx + 1 < len(heading_idxs) else len(lines)
        heading = lines[start].rstrip(":").strip()
        body = "\n".join(lines[start + 1:end]).strip()
        key = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")[:40] or f"section_{idx+1}"
        sections.append({"key": key, "title": heading, "guidance": body[:1200]})

    return sections

def parse_grant_upload_to_requirements(uploaded_file) -> Tuple[Dict[str, Any] | None, str]:
    """
    Returns:
      requirements: dict usable by the app
      raw_text: extracted text from the document (best-effort)
    """
    name = uploaded_file.name.lower()

    if name.endswith(".txt"):
        raw = _read_txt(uploaded_file)
    elif name.endswith(".pdf"):
        raw = _read_pdf(uploaded_file)
    elif name.endswith(".docx"):
        raw = _read_docx(uploaded_file)
    else:
        raw = ""

    raw = (raw or "").strip()

    # Minimal requirements schema the rest of the app expects
    requirements = {
        "grant_name": uploaded_file.name,
        "sections": _extract_sections_from_text(raw),
        "eligibility": [],            # optional / can be expanded later
        "word_limits": {},            # optional
        "must_include": [],           # optional
        "raw_text": raw,
        "required_sections": [s.get("title") for s in _extract_sections_from_text(raw)]
    }

    return requirements, raw
