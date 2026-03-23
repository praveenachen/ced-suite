"""
FastAPI backend for the Grant Proposal Builder frontend.
Run from repo root: uvicorn api.main:app --reload --port 8000
Set PYTHONPATH to include repo root so backend.app imports resolve.
"""
from __future__ import annotations

import sys
import re
from io import BytesIO
from pathlib import Path
from datetime import date

# Ensure repo root is on path (ced-suite)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

app = FastAPI(title="Grant Proposal API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic models for request/response ----------
class CommunityProfile(BaseModel):
    community_name: str = ""
    region: str = ""
    local_priority: str = ""
    timeline: str = ""
    challenges: str = ""
    strengths: str = ""
    partners: str = ""
    evidence_note: str = ""
    requested_budget: Optional[int] = None
    indicators_before: Optional[Dict[str, Any]] = None
    indicators_after: Optional[Dict[str, Any]] = None
    scenario: Optional[Dict[str, Any]] = None


class SectionSpec(BaseModel):
    key: str
    title: str
    guidance: str = ""
    word_limit: Optional[int] = None


class RequirementsBody(BaseModel):
    grant_name: str = ""
    program_name: Optional[str] = None
    name: Optional[str] = None
    sections: List[SectionSpec] = []
    eligibility: List[str] = []
    word_limits: Dict[str, int] = {}
    must_include: List[str] = []
    raw_text: str = ""
    required_sections: List[str] = []


class GenerateDraftRequest(BaseModel):
    profile: CommunityProfile
    requirements: Dict[str, Any]  # full requirements as returned by parse
    requested_budget: int = Field(..., ge=0)


class EnhanceRequest(BaseModel):
    draft: Dict[str, Any]
    requirements: Dict[str, Any]
    profile: Dict[str, Any]
    use_case: Optional[str] = None


class ValidateRequest(BaseModel):
    draft: Dict[str, Any]
    requirements: Dict[str, Any]


class RewriteSectionRequest(BaseModel):
    section_key: str
    section_title: str = ""
    current_text: str = ""
    instruction: str = Field(..., min_length=1)
    requirements: Dict[str, Any]
    profile: Dict[str, Any]
    use_case: Optional[str] = None


class ExportSection(BaseModel):
    key: str = ""
    title: str
    body: str


class ExportDraftPdfRequest(BaseModel):
    grant_name: str = ""
    community_name: str = ""
    region: str = ""
    local_priority: str = ""
    requested_budget: Optional[int] = None
    sections: List[ExportSection] = []


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\- ]+", "", (value or "").strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:60] or "grant_proposal"


def _render_pdf(body: ExportDraftPdfRequest) -> bytes:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF export dependency missing: {e}. Install reportlab.",
        )

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER
    left = 72
    right = width - 72
    top = height - 72
    bottom = 72
    line_h = 14
    y = top

    def new_page() -> None:
        nonlocal y
        c.showPage()
        y = top

    def ensure_room(lines: int = 1) -> None:
        nonlocal y
        if y - (lines * line_h) < bottom:
            new_page()

    def draw_line(text: str, *, font: str = "Helvetica", size: int = 11, extra_gap: float = 0.0) -> None:
        nonlocal y
        ensure_room(1)
        c.setFont(font, size)
        c.drawString(left, y, text)
        y -= line_h + extra_gap

    def wrap_text(text: str, size: int = 11) -> List[str]:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        max_w = right - left
        words = (text or "").split()
        if not words:
            return [""]

        lines: List[str] = []
        cur = words[0]
        for w in words[1:]:
            candidate = f"{cur} {w}"
            if stringWidth(candidate, "Helvetica", size) <= max_w:
                cur = candidate
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    def draw_paragraph(text: str, *, size: int = 11, gap: float = 4.0) -> None:
        nonlocal y
        chunks = [p.strip() for p in (text or "").replace("\r\n", "\n").split("\n")]
        for chunk in chunks:
            lines = wrap_text(chunk, size=size)
            for ln in lines:
                ensure_room(1)
                c.setFont("Helvetica", size)
                c.drawString(left, y, ln)
                y -= line_h
            y -= gap

    # Cover header
    draw_line("Grant Proposal", font="Helvetica-Bold", size=22, extra_gap=8)
    if body.grant_name:
        draw_line(body.grant_name, font="Helvetica-Bold", size=14, extra_gap=6)
    draw_line(f"Community: {body.community_name or 'N/A'}", font="Helvetica", size=11)
    draw_line(f"Region: {body.region or 'N/A'}", font="Helvetica", size=11)
    draw_line(f"Local Priority: {body.local_priority or 'N/A'}", font="Helvetica", size=11)
    if body.requested_budget is not None:
        draw_line(
            f"Requested Funding: ${body.requested_budget:,.0f}",
            font="Helvetica",
            size=11,
        )
    draw_line(f"Generated: {date.today().isoformat()}", font="Helvetica", size=10, extra_gap=14)

    # Body sections
    for i, sec in enumerate(body.sections, start=1):
        if y < bottom + 120:
            new_page()
        title = (sec.title or f"Section {i}").strip()
        draw_line(f"{i}. {title}", font="Helvetica-Bold", size=13, extra_gap=3)
        draw_paragraph((sec.body or "").strip() or "No content provided.", size=11, gap=6.0)

    c.save()
    buf.seek(0)
    return buf.read()


# ---------- Endpoints ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/parse-grant")
async def parse_grant(file: UploadFile = File(...)):
    """Parse uploaded grant document (PDF/DOCX/TXT) into structured requirements."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    name = file.filename.lower()
    if not (name.endswith(".txt") or name.endswith(".pdf") or name.endswith(".docx")):
        raise HTTPException(status_code=400, detail="Only .txt, .pdf, .docx supported")
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    # Parser expects a file-like with .name and .read() / .getvalue()
    class FileLike:
        def __init__(self, data: bytes, filename: str):
            self._io = BytesIO(data)
            self.name = filename
        def read(self, n=-1):
            return self._io.read(n)
        def getvalue(self):
            return self._io.getvalue()
    file_like = FileLike(content, file.filename)
    try:
        from backend.app.parsers.grant_parsers import parse_grant_upload_to_requirements
        requirements, raw_text = parse_grant_upload_to_requirements(file_like)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if requirements is None:
        raise HTTPException(status_code=422, detail="Could not parse document")
    # Convert sections to serializable dicts
    req_dict = {
        "grant_name": requirements.get("grant_name"),
        "sections": [
            {"key": s.get("key"), "title": s.get("title"), "guidance": s.get("guidance", ""), "word_limit": s.get("word_limit")}
            for s in requirements.get("sections", [])
        ],
        "eligibility": requirements.get("eligibility", []),
        "word_limits": requirements.get("word_limits", {}),
        "must_include": requirements.get("must_include", []),
        "raw_text": requirements.get("raw_text", raw_text),
        "required_sections": requirements.get("required_sections", []),
        "parser_meta": requirements.get("parser_meta", {}),
    }
    return {"requirements": req_dict, "raw_text": raw_text}


@app.post("/api/generate-draft")
def generate_draft(body: GenerateDraftRequest):
    """Generate a baseline draft from community profile and requirements."""
    try:
        from backend.app.utils.grant_utils import generate_proposal_from_requirements
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Backend import error: {e}")
    profile = body.profile.model_dump()
    requirements = body.requirements
    budget = body.requested_budget
    draft = generate_proposal_from_requirements(profile=profile, requirements=requirements, requested_budget=budget)
    return draft


@app.post("/api/enhance")
def enhance(body: EnhanceRequest):
    """Enhance draft sections using RAG + LLM."""
    try:
        from backend.app.llm.llm_utils import enhance_sections
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Backend import error: {e}")
    try:
        enhanced = enhance_sections(
            draft=body.draft,
            requirements=body.requirements,
            profile=body.profile,
            use_case=body.use_case,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"enhanced": enhanced}


@app.post("/api/validate")
def validate(body: ValidateRequest):
    """Validate draft against requirements."""
    try:
        from backend.app.utils.validation_utils import validate_proposal_against_requirements
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Backend import error: {e}")
    result = validate_proposal_against_requirements(draft=body.draft, requirements=body.requirements)
    return result


@app.post("/api/rewrite-section")
def rewrite_section(body: RewriteSectionRequest):
    """Rewrite one draft section with user instruction and return source references."""
    try:
        from backend.app.llm.llm_utils import rewrite_section_with_instruction
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Backend import error: {e}")

    try:
        out = rewrite_section_with_instruction(
            section_key=body.section_key,
            section_title=body.section_title,
            current_text=body.current_text,
            instruction=body.instruction,
            requirements=body.requirements,
            profile=body.profile,
            use_case=body.use_case,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return out


@app.post("/api/export-draft-pdf")
def export_draft_pdf(body: ExportDraftPdfRequest):
    """Export the final draft as a professionally formatted PDF."""
    if not body.sections:
        raise HTTPException(status_code=400, detail="At least one section is required for export.")

    pdf_bytes = _render_pdf(body)
    base = _safe_filename(body.community_name or body.grant_name or "grant_proposal")
    filename = f"{base}_proposal.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
