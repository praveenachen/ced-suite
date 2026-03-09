from __future__ import annotations
from typing import Dict, Any, Tuple
from io import BytesIO
import json
import os
import re

CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

def _read_txt(file) -> str:
    return file.getvalue().decode("utf-8", errors="ignore")

def _read_pdf(file) -> str:
    """
    Best-effort PDF text extraction.
    Tries PyPDF2/pypdf first, then pdfplumber (if installed) as a fallback.
    """
    parts: list[str] = []
    stream = file
    if hasattr(file, "getvalue"):
        try:
            stream = BytesIO(file.getvalue())
        except Exception:
            stream = file

    reader_cls = None
    try:
        import PyPDF2
        reader_cls = PyPDF2.PdfReader
    except Exception:
        try:
            from pypdf import PdfReader as PypdfReader
            reader_cls = PypdfReader
        except Exception:
            reader_cls = None

    if reader_cls is not None:
        try:
            reader = reader_cls(stream)
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
        if hasattr(stream, "seek"):
            stream.seek(0)
        import pdfplumber

        parts = []
        with pdfplumber.open(stream) as pdf:
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
    low = ln.lower()

    # Exclude obvious body lines / bullets.
    if ln.startswith(("-", "*", "\u2022")):
        return False
    if len(ln.split()) > 18:
        return False
    if re.match(r"^page\s+\d+\s*(?:of|/)\s*\d+\b", low):
        return False
    if re.search(r"\b(?:https?://|www\.)\S+", ln):
        return False
    if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", ln, flags=re.I):
        return False
    if re.match(r"^[\(\[]?\s*[xX ]\s*[\)\]]\s+\S+", ln):
        return False

    # Strong heading patterns with explicit numbering systems.
    if re.match(r"^(?:[IVXLCDM]{1,8})[\)\.\-:]\s+\S+", ln, flags=re.I):
        return True
    if re.match(r"^\d+(\.\d+)*[\)\.\-:]?\s+\S+", ln):
        return True
    if re.match(r"^[A-Z][\)\.\-:]\s+\S+", ln):  # A) Scope
        return True
    if re.match(r"^(SECTION|PART|APPENDIX)\s+[A-Z0-9]+", ln, flags=re.I):
        return True
    if ln.endswith(":") and len(ln.split()) <= 12:
        return True

    # All-caps headings are common in grant docs.
    letters = [c for c in ln if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= 0.8 and len(ln.split()) <= 12:
            return True

    # Title Case-ish short lines, without sentence punctuation.
    # Keep this strict to avoid over-extracting body fragments as headings.
    words = re.findall(r"[A-Za-z][A-Za-z/&'-]*", ln)
    if 2 <= len(words) <= 6:
        title_like = sum(1 for w in words if w[0].isupper())
        if title_like / max(1, len(words)) >= 0.85 and not re.search(r"[.!?]$", ln):
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

def _normalize_section_key(title: str, index: int) -> str:
    key_base = re.sub(r"[^a-z0-9]+", "_", (title or "").lower()).strip("_")[:60]
    return key_base or f"section_{index + 1}"

def _normalize_sections(sections: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: dict[str, int] = {}

    for idx, sec in enumerate(sections):
        title = str(sec.get("title") or "").strip()
        guidance = str(sec.get("guidance") or "").strip()
        if not title:
            continue

        base_key = str(sec.get("key") or _normalize_section_key(title, idx)).strip()
        key = re.sub(r"[^a-z0-9_]+", "_", base_key.lower()).strip("_") or _normalize_section_key(title, idx)
        cnt = seen.get(key, 0) + 1
        seen[key] = cnt
        key = key if cnt == 1 else f"{key}_{cnt}"

        item: dict[str, Any] = {
            "key": key,
            "title": title[:140],
            "guidance": guidance[:3000],
        }

        word_limit = sec.get("word_limit")
        if isinstance(word_limit, int) and word_limit > 0:
            item["word_limit"] = word_limit
        else:
            inferred = _extract_word_limit(f"{title}\n{guidance}")
            if inferred:
                item["word_limit"] = inferred

        out.append(item)

    return out

def _should_use_llm_fallback(raw_text: str, heuristic_sections: list[dict]) -> bool:
    if len(raw_text.strip()) < 800:
        return False
    if len(heuristic_sections) <= 1:
        return True
    if len(heuristic_sections) > 12:
        return True

    titles = [str(s.get("title") or "").strip() for s in heuristic_sections]
    if titles:
        very_short = sum(1 for t in titles if len(t.split()) <= 2)
        if len(titles) >= 4 and (very_short / len(titles)) >= 0.5:
            return True

        normalized_titles = [
            re.sub(r"\d+", "", re.sub(r"[^a-z0-9]+", "", t.lower()))
            for t in titles
            if t
        ]
        if normalized_titles:
            unique_count = len(set(normalized_titles))
            if unique_count <= max(2, len(normalized_titles) // 3):
                return True

    keys = {str(s.get("key") or "") for s in heuristic_sections}
    return keys == {"application_requirements"}


def _extract_sections_with_llm(text: str) -> list[dict]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []

    snippet = text[:20000]
    if len(snippet.strip()) < 800:
        return []

    prompt = {
        "task": "Extract concrete grant application sections from the posting text.",
        "rules": [
            "Return JSON only.",
            "Prefer explicit required/expected sections in the application package.",
            "Prefer top-level numbered headings (Roman numerals, numeric levels, lettered lists) when present.",
            "Return sections the applicant must respond to; exclude context-only headings and administrative notes.",
            "Do not split a single required heading into multiple micro-sections unless the document clearly requires separate responses.",
            "Do not invent sections not implied by the text.",
            "Each section needs key, title, guidance, and optional word_limit.",
            "If limits are not explicit, omit word_limit.",
        ],
        "schema": {
            "sections": [
                {
                    "key": "snake_case_key",
                    "title": "Section Title",
                    "guidance": "What the applicant should cover in this section",
                    "word_limit": 500,
                }
            ]
        },
        "text": snippet,
    }

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract grant requirement sections from messy PDF text. "
                        "Output strict JSON with high recall and minimal hallucination."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        return _normalize_sections((data.get("sections") or []))
    except Exception:
        return []

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

    return _normalize_sections(sections)

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
    heuristic_sections = _extract_sections_from_text(raw)
    sections = heuristic_sections
    parser_mode = "heuristic"
    llm_used = False

    if _should_use_llm_fallback(raw, heuristic_sections):
        llm_sections = _extract_sections_with_llm(raw)
        llm_used = True
        if len(llm_sections) >= 2:
            sections = llm_sections
            parser_mode = "llm_fallback"
        else:
            parser_mode = "heuristic_fallback_single"

    confidence = "high" if len(sections) >= 4 else ("medium" if len(sections) >= 2 else "low")

    # Minimal requirements schema the rest of the app expects
    requirements = {
        "grant_name": uploaded_file.name,
        "sections": sections,
        "eligibility": [],            # optional / can be expanded later
        "word_limits": {},            # optional
        "must_include": [],           # optional
        "raw_text": raw,
        "required_sections": [s.get("title") for s in sections],
        "parser_meta": {
            "mode": parser_mode,
            "confidence": confidence,
            "raw_text_length": len(raw),
            "heuristic_section_count": len(heuristic_sections),
            "final_section_count": len(sections),
            "llm_fallback_used": llm_used,
        },
    }

    return requirements, raw

