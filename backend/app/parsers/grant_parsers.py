from __future__ import annotations
from typing import Dict, Any, Tuple
import re

def _read_txt(file) -> str:
    return file.getvalue().decode("utf-8", errors="ignore")

def _read_pdf(file) -> str:
    """
    Best-effort PDF text extraction.
    Tries PyPDF2 first, then pdfplumber (if installed) as a fallback.
    """
    parts: list[str] = []

    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            parts.append(page.extract_text() or "")
    except Exception:
        parts = []

    text = "\n".join(parts).strip()
    if len(text) > 200:
        return text

    # Fallback parser for PDFs where PyPDF2 misses ordering/blocks
    try:
        # rewind underlying buffer if available
        if hasattr(file, "_io") and hasattr(file._io, "seek"):
            file._io.seek(0)
        import pdfplumber

        parts = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except Exception:
        return text

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

def _is_probable_heading(line: str) -> bool:
    ln = line.strip()
    if not ln:
        return False
    if len(ln) < 3 or len(ln) > 140:
        return False

    # Exclude obvious body lines / bullets.
    if ln.startswith(("-", "*", "•")):
        return False
    if len(ln.split()) > 18:
        return False

    # Common heading patterns.
    if ln.endswith(":"):
        return True
    if re.match(r"^\d+(\.\d+)*[\)\.\-:]?\s+\S+", ln):
        return True
    if re.match(r"^[A-Z][\)\.\-:]\s+\S+", ln):  # A) Scope
        return True
    if re.match(r"^(SECTION|PART|APPENDIX)\s+[A-Z0-9]+", ln, flags=re.I):
        return True

    # All-caps headings are common in grant docs.
    letters = [c for c in ln if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= 0.8 and len(ln.split()) <= 12:
            return True

    # Title Case-ish short lines, without sentence punctuation.
    words = re.findall(r"[A-Za-z][A-Za-z/&'-]*", ln)
    if 1 <= len(words) <= 12:
        title_like = sum(1 for w in words if w[0].isupper())
        if title_like / max(1, len(words)) >= 0.7 and not re.search(r"[.!?]$", ln):
            return True

    return False

def _extract_word_limit(text: str) -> int | None:
    m = re.search(
        r"(?i)\b(?:word\s*limit|max(?:imum)?\s*words?|up to)\s*[:\-]?\s*(\d{2,5})\b",
        text,
    )
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None

    m = re.search(r"(?i)\b(\d{2,5})\s*words?\b", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None

def _extract_sections_from_text(text: str) -> list[dict]:
    """
    Heuristic section extraction for grant packages.
    Finds heading-like lines and assigns following content as guidance.
    If no clear headings are found, returns a single catch-all section.
    """
    cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not cleaned:
        return [{"key": "application_requirements", "title": "Application Requirements", "guidance": ""}]

    lines = [ln.strip() for ln in cleaned.splitlines()]
    heading_idxs = []
    for i, ln in enumerate(lines):
        if _is_probable_heading(ln):
            # Avoid duplicate heading candidates on adjacent lines.
            if heading_idxs and i - heading_idxs[-1] <= 1 and lines[heading_idxs[-1]].lower() == ln.lower():
                continue
            heading_idxs.append(i)

    # If we cannot confidently segment headings, keep all guidance in one section
    # instead of forcing a fixed template.
    if len(heading_idxs) < 2:
        return [
            {
                "key": "application_requirements",
                "title": "Application Requirements",
                "guidance": cleaned[:6000],
                "word_limit": _extract_word_limit(cleaned),
            }
        ]

    sections = []
    seen_keys: dict[str, int] = {}
    for idx, start in enumerate(heading_idxs):
        end = heading_idxs[idx + 1] if idx + 1 < len(heading_idxs) else len(lines)
        heading = lines[start].rstrip(":").strip()
        body = "\n".join(lines[start + 1:end]).strip()
        key_base = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")[:60] or f"section_{idx+1}"
        count = seen_keys.get(key_base, 0) + 1
        seen_keys[key_base] = count
        key = key_base if count == 1 else f"{key_base}_{count}"

        # Keep enough context to guide generation, but cap to avoid runaway payloads.
        guidance = body[:3000]
        sec = {"key": key, "title": heading, "guidance": guidance}
        wl = _extract_word_limit(f"{heading}\n{body}")
        if wl:
            sec["word_limit"] = wl
        sections.append(sec)

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
    sections = _extract_sections_from_text(raw)

    # Minimal requirements schema the rest of the app expects
    requirements = {
        "grant_name": uploaded_file.name,
        "sections": sections,
        "eligibility": [],            # optional / can be expanded later
        "word_limits": {},            # optional
        "must_include": [],           # optional
        "raw_text": raw,
        "required_sections": [s.get("title") for s in sections]
    }

    return requirements, raw
