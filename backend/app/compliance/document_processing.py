from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, Iterable, List

from docx import Document
from pypdf import PdfReader


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {path.suffix}")


def extract_text_from_pdf(path: Path) -> str:
    return extract_pdf_text_with_diagnostics(path)["text"]


def extract_text_from_docx(path: Path) -> str:
    document = Document(str(path))
    return "\n\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())


def extract_pdf_pages(path: Path) -> List[str]:
    reader = PdfReader(str(path))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def extract_pdf_text_with_diagnostics(path: Path) -> Dict[str, object]:
    candidates: List[Dict[str, object]] = []

    try:
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        candidates.append(
            {
                "name": "pypdf",
                "text": "\n\n".join(page for page in pages if page),
                "page_count": len(pages),
            }
        )
    except Exception:
        pass

    try:
        import pdfplumber

        pages = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                pages.append((page.extract_text() or "").strip())
        candidates.append(
            {
                "name": "pdfplumber",
                "text": "\n\n".join(page for page in pages if page),
                "page_count": len(pages),
            }
        )
    except Exception:
        pass

    try:
        import fitz

        pages = []
        with fitz.open(str(path)) as pdf:
            for page in pdf:
                pages.append((page.get_text("text") or "").strip())
        candidates.append(
            {
                "name": "pymupdf",
                "text": "\n\n".join(page for page in pages if page),
                "page_count": len(pages),
            }
        )
    except Exception:
        pass

    if not candidates:
        return {"extractor": "none", "text": "", "page_count": 0}

    scored = []
    for candidate in candidates:
        text = normalize_whitespace(str(candidate["text"]))
        page_count = int(candidate["page_count"])
        score = _score_pdf_extraction_candidate(text, page_count)
        scored.append({**candidate, "text": text, "score": score})

    best = max(scored, key=lambda item: item["score"])
    return {
        "extractor": best["name"],
        "text": best["text"],
        "page_count": best["page_count"],
        "candidates": [
            {"extractor": item["name"], "score": item["score"], "chars": len(str(item["text"]))}
            for item in scored
        ],
    }


def normalize_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text or "")).strip()


def smart_chunk_paragraphs(
    paragraphs: Iterable[str],
    *,
    min_words: int = 180,
    max_words: int = 380,
    overlap_paragraphs: int = 1,
) -> List[str]:
    cleaned = [normalize_whitespace(paragraph) for paragraph in paragraphs if normalize_whitespace(paragraph)]
    chunks: List[str] = []
    current: List[str] = []
    current_words = 0

    for paragraph in cleaned:
        paragraph_words = len(paragraph.split())
        is_heading = paragraph_words < 14 and paragraph == paragraph.title()
        if current and (current_words + paragraph_words > max_words) and current_words >= min_words:
            chunks.append("\n\n".join(current))
            current = current[-overlap_paragraphs:] if overlap_paragraphs else []
            current_words = sum(len(item.split()) for item in current)

        if is_heading and current:
            current.append(paragraph)
            continue

        current.append(paragraph)
        current_words += paragraph_words

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def stable_chunk_id(source_document: str, page_number: int | None, text: str) -> str:
    h = hashlib.sha256()
    h.update(source_document.encode("utf-8"))
    h.update(b"||")
    h.update(str(page_number).encode("utf-8"))
    h.update(b"||")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:16]


def _score_pdf_extraction_candidate(text: str, page_count: int) -> float:
    if not text:
        return 0.0
    words = re.findall(r"\b\w+\b", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    avg_words_per_line = len(words) / max(1, len(lines))
    long_lines = sum(1 for line in lines if len(line.split()) >= 6)
    punctuation_hits = len(re.findall(r"[.!?;:]", text))
    return (
        len(text) * 0.01
        + len(words) * 0.02
        + long_lines * 0.8
        + avg_words_per_line * 2.5
        + punctuation_hits * 0.05
        + page_count * 1.0
    )
