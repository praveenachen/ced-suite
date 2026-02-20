"""
FastAPI backend for the Grant Proposal Builder frontend.
Run from repo root: uvicorn api.main:app --reload --port 8000
Set PYTHONPATH to include repo root so backend.app imports resolve.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

# Ensure repo root is on path (ced-suite)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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


class ValidateRequest(BaseModel):
    draft: Dict[str, Any]
    requirements: Dict[str, Any]


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
    enhanced = enhance_sections(
        draft=body.draft,
        requirements=body.requirements,
        profile=body.profile,
    )
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
