import streamlit as st
import json
from typing import Dict, Any, List

from utils.grant_parsers import parse_grant_upload_to_requirements
from utils.grant_utils import generate_proposal_from_requirements, fit_programs
from utils.validation_utils import validate_proposal_against_requirements
from utils.llm_utils import enhance_sections

st.markdown(
    """
<style>
/* =========================
   GLOBAL DARK THEME
========================= */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
main,
.block-container,
[data-testid="stHeader"],
[data-testid="stSidebar"]{
  background:#000 !important;
  color:#fff !important;
}

/* Default text white (but DO NOT blanket-target everything) */
.stApp p, .stApp span, .stApp li, .stApp label,
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
  color:#fff !important;
}

/* =========================
   INPUTS (white + black text + yellow border)
========================= */
input, textarea, select,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
  background:#fff !important;
  color:#111 !important;
  border:2px solid #f5c400 !important;
}

::placeholder { color:#6b7280 !important; }

/* =========================
   DIVIDERS (yellow)
========================= */
hr{
  border:none !important;
  height:2px !important;
  background:#f5c400 !important;
  margin:2rem 0 !important;
}

/* =========================
   ALL BUTTONS (yellow + black text) + stable hover
========================= */
.stButton > button,
button,
[data-testid="stDownloadButton"] button{
  background:#f5c400 !important;
  color:#111 !important;
  border:2px solid #f5c400 !important;
  font-weight:700 !important;
  border-radius:10px !important;
  box-shadow:none !important;
  filter:none !important;
}

.stButton > button * ,
button * ,
[data-testid="stDownloadButton"] button *{
  color:#111 !important;
}

.stButton > button:hover,
button:hover,
[data-testid="stDownloadButton"] button:hover,
.stButton > button:active,
button:active,
.stButton > button:focus,
button:focus{
  background:#f5c400 !important;
  color:#111 !important;
  border-color:#f5c400 !important;
  box-shadow:none !important;
  outline:none !important;
}

/* Download icon black */
[data-testid="stDownloadButton"] svg{ fill:#111 !important; }

/* =========================
   FILE UPLOADER — grey dropzone, black text, no inner white pill
========================= */

/* IMPORTANT: do NOT set uploader background to white globally */
[data-testid="stFileUploader"]{ background:transparent !important; }

/* Dropzone card */
[data-testid="stFileUploader"] section{
  background:#e5e7eb !important;
  border:2px dashed #9ca3af !important;
  border-radius:16px !important;
  padding:18px !important;
  box-shadow:none !important;
}

/* Kill inner wrappers that render the white instruction pill */
[data-testid="stFileUploader"] section > div,
[data-testid="stFileUploader"] section > div > div,
[data-testid="stFileUploader"] section > div > div > div{
  background:transparent !important;
  border:none !important;
  box-shadow:none !important;
}

/* Force ALL uploader text to black */
[data-testid="stFileUploader"] section *{
  color:#111 !important;
  opacity:1 !important;
}

/* Uploader icon black */
[data-testid="stFileUploader"] section svg{
  fill:#111 !important;
}

/* Browse files button inside uploader = light grey (not yellow) */
[data-testid="stFileUploader"] button{
  background:#f9fafb !important;
  color:#111 !important;
  border:2px solid #d1d5db !important;
  border-radius:12px !important;
  font-weight:700 !important;
  box-shadow:none !important;
}

[data-testid="stFileUploader"] button:hover,
[data-testid="stFileUploader"] button:active,
[data-testid="stFileUploader"] button:focus{
  background:#f3f4f6 !important;
  color:#111 !important;
  border:2px solid #d1d5db !important;
  box-shadow:none !important;
  outline:none !important;
}s

/* Alerts keep their own colors */
[data-testid="stAlert"] *{ color:inherit !important; }
</style>


""",
    unsafe_allow_html=True,
)


st.header("📝 Grant & Proposal Writer")
st.caption("Upload a grant posting → generate a comprehensive, requirements-aligned proposal draft → download.")

# #Gemini API key check
# import os

# with st.sidebar:
#     st.markdown("### 🔎 LLM Debug Status")

#     st.write("GEMINI_API_KEY present:", "✅" if os.getenv("GEMINI_API_KEY") else "❌")

#     try:
#         import google.generativeai as genai
#         st.write("google-generativeai package installed: ✅")
#     except Exception as e:
#         st.write("google-generativeai package installed: ❌")
#         st.write(str(e))

# ------------------------------
# Demo Data (internal/testing)
# ------------------------------
if st.button("🧪 Load Demo Data", use_container_width=True):
    st.session_state["community_context"] = {
        "community_name": "Kinngait",
        "region": "Nunavut",
        "local_priority": "Water infrastructure",
        "challenges": "Frequent boil-water advisories; aging distribution pipes; high operating costs for repairs.",
        "timeline": "Apr–Dec 2026",
        "requested_budget": 250_000,
        "need_index_before": 0.51,
        "need_index_after": 0.449,
        "evidence_note": "Kinngait is proposing targeted investments to address water infrastructure needs. Based on baseline indicators and scenario improvements, the Need Index decreases from 0.51 to 0.449, demonstrating measurable expected impact aligned with funder priorities.",
        "indicators_before": {"water_reliability": 55.0, "unemployment_rate": 13.2, "internet_access": 62.0},
        "indicators_after": {"water_reliability": 60.5, "unemployment_rate": 11.9, "internet_access": 68.2},
        "scenario": {"improve_water_pct": 10, "reduce_unemp_pct": 10, "improve_internet_pct": 10},
    }

    st.session_state["gw_requirements"] = {
        "grant_name": "Northern Infrastructure Improvement Fund",
        "eligibility": [
            "Municipality or Hamlet government",
            "Project located in Nunavut"
        ],
        "must_include": [
            "community engagement",
            "outcomes",
            "budget",
        ],
        "sections": [
            {
                "key": "need_statement",
                "title": "Need Statement",
                "guidance": "Describe the current problem, who is impacted, and why this is urgent now.",
                "word_limit": 750,
            },
            {
                "key": "project_plan",
                "title": "Project Plan",
                "guidance": "Describe activities, phases, partners, roles, and timeline.",
                "word_limit": 1000,
            },
            {
                "key": "outcomes_metrics",
                "title": "Outcomes & Metrics",
                "guidance": "Define measurable outputs/outcomes and how you will track them.",
                "word_limit": 500,
            },
            {
                "key": "budget_justification",
                "title": "Budget Justification",
                "guidance": "Explain what the funding will pay for and why each cost is needed.",
                "word_limit": 500,
            },
        ],
        "raw_text": "",
    }

    st.success("Demo community + demo requirements loaded.")

st.divider()

# ------------------------------
# STEP 1 — Community profile (auto-filled from Impact Planner if available)
# ------------------------------
st.subheader("1) Community profile")

ctx = st.session_state.get("community_context")
has_ctx = isinstance(ctx, dict) and bool(ctx.get("community_name")) and bool(ctx.get("local_priority"))

if has_ctx:
    st.success(
        f"Imported from Impact Planner: **{ctx.get('community_name','')}** "
        f"(Need Index {ctx.get('need_index_before')} → {ctx.get('need_index_after')})"
    )

    st.write(f"**Region:** {ctx.get('region','—')}")
    st.write(f"**Local priority:** {ctx.get('local_priority','—')}")
    if ctx.get("requested_budget"):
        st.write(f"**Target funding request:** ${int(ctx.get('requested_budget')):,}")
    if ctx.get("timeline"):
        st.write(f"**Timeline:** {ctx.get('timeline')}")
    if ctx.get("challenges"):
        st.markdown("**Key challenges + evidence note:**")
        st.write(ctx.get("challenges"))
        st.write(ctx.get("evidence_note", ""))

    with st.expander("Edit community info (optional)"):
        ctx["community_name"] = st.text_input("Community name", value=ctx.get("community_name", ""))
        ctx["region"] = st.text_input("Region / Province", value=ctx.get("region", ""))
        ctx["local_priority"] = st.text_input("Local priority", value=ctx.get("local_priority", ""))
        ctx["timeline"] = st.text_input("Timeline", value=ctx.get("timeline", ""))
        ctx["challenges"] = st.text_area("Key challenges", value=ctx.get("challenges", ""))
        ctx["requested_budget"] = st.number_input(
            "Requested funding ($)",
            min_value=10_000,
            max_value=5_000_000,
            value=int(ctx.get("requested_budget", 250_000)),
            step=5_000
        )
        st.session_state["community_context"] = ctx

    profile: Dict[str, Any] = {
        "community_name": ctx.get("community_name", "").strip(),
        "region": ctx.get("region", "").strip(),
        "local_priority": ctx.get("local_priority", "").strip(),
        "timeline": ctx.get("timeline", "").strip(),
        "challenges": ctx.get("challenges", "").strip(),
        "evidence_note": (ctx.get("evidence_note", "") or "").strip(),
        "need_index_before": ctx.get("need_index_before"),
        "need_index_after": ctx.get("need_index_after"),
        "indicators_before": ctx.get("indicators_before", {}),
        "indicators_after": ctx.get("indicators_after", {}),
        "scenario": ctx.get("scenario", {}),
    }
    budget = int(ctx.get("requested_budget", 250_000))

else:
    st.info("No Impact Planner data found. Fill this in, or go to the Impact Planner page to auto-fill.")

    community_name = st.text_input("Community name")
    region = st.text_input("Region / Province")
    local_priority = st.text_input("Local priority")
    timeline = st.text_input("Timeline (optional)")
    challenges = st.text_area("Key challenges (optional)")
    budget = st.number_input("Requested funding ($)", min_value=10_000, max_value=5_000_000, value=250_000, step=5_000)

    profile = {
        "community_name": community_name.strip(),
        "region": region.strip(),
        "local_priority": local_priority.strip(),
        "timeline": timeline.strip(),
        "challenges": challenges.strip(),
        "evidence_note": "",
    }

if not profile["community_name"] or not profile["local_priority"]:
    st.caption("Enter at least **Community name** and **Local priority** to continue.")
    st.stop()

st.divider()

# ------------------------------
# STEP 2 — Upload grant requirements (JSON OR PDF/DOCX/TXT)
# ------------------------------
st.subheader("2) Grant requirements (recommended: upload the grant posting)")

c_req1, c_req2 = st.columns(2, gap="large")

with c_req1:
    st.markdown("**Upload grant posting / application guide**")
    requirements_doc = st.file_uploader(
        "PDF / DOCX / TXT",
        type=["pdf", "docx", "txt"],
        key="req_doc"
    )

with c_req2:
    st.markdown("**Advanced: upload structured requirements**")
    requirements_json = st.file_uploader(
        "Requirements JSON",
        type=["json"],
        key="req_json"
    )

requirements: Dict[str, Any] | None = None
requirements_raw_text: str = ""

if requirements_json is not None:
    try:
        requirements = json.load(requirements_json)
        requirements_raw_text = requirements.get("raw_text", "")
        st.success("Loaded requirements JSON.")
    except Exception as e:
        st.error(f"Could not read JSON: {e}")

elif requirements_doc is not None:
    requirements, requirements_raw_text = parse_grant_upload_to_requirements(requirements_doc)
    if requirements:
        st.success("Parsed grant posting into structured requirements (best-effort).")
    else:
        st.error("Could not parse the uploaded document. Try a TXT export or upload JSON.")

if requirements:
    st.session_state["gw_requirements"] = requirements
    st.session_state["gw_requirements_raw_text"] = requirements_raw_text
    st.session_state["gw_step"] = max(st.session_state["gw_step"], 2)

req = st.session_state.get("gw_requirements")
req_text = st.session_state.get("gw_requirements_raw_text", "")

if not req:
    st.caption("Upload requirements to continue.")
    st.stop()

with st.expander("View parsed requirements (what the tool is using)"):
    st.json(req)
    if req_text:
        st.markdown("**Extracted application text (snippet):**")
        st.write(req_text[:2000] + ("..." if len(req_text) > 2000 else ""))

st.divider()

# ------------------------------
# STEP 3 — Optional: program suggestions
# ------------------------------
st.subheader("3) (Optional) Program suggestions from a program list")
st.caption("Upload a programs list (JSON) to suggest likely matches. Otherwise, skip this step.")

programs_file = st.file_uploader(
    "Optional: Funding programs list (JSON)",
    type=["json"],
    key="programs_json"
)

programs = None
if programs_file is not None:
    try:
        programs = json.load(programs_file)
    except Exception as e:
        st.warning(f"Could not read programs JSON: {e}")

st.divider()

# ------------------------------
# STEP 4 — Generate draft (requirement-aligned)
# ------------------------------
st.subheader("4) Generate proposal draft (aligned to requirements)")

if st.button("Generate Draft", type="primary", key="btn_generate_draft"):
    draft = generate_proposal_from_requirements(
        profile=profile,
        requirements=req,
        requested_budget=budget,
    )

    enhanced = {}
    try:
        enhanced = enhance_sections(draft, requirements=req, profile=profile)
        if not enhanced:
            st.warning("LLM enhancement returned empty output (check API key / Gemini install / errors).")
    except Exception as e:
        st.error("LLM enhancement failed. See details below.")
        with st.expander("Show error details"):
            st.exception(e)


    validation = validate_proposal_against_requirements(draft, req)

    st.session_state["gw_draft"] = draft
    st.session_state["gw_enhanced"] = enhanced
    st.session_state["gw_validation"] = validation
    st.session_state["gw_step"] = 5

draft = st.session_state.get("gw_draft")
enhanced = st.session_state.get("gw_enhanced") or {}
validation = st.session_state.get("gw_validation") or {}

if not draft:
    st.caption("Click **Generate Draft** to create a proposal aligned to the uploaded requirements.")
    st.stop()

st.divider()

# ------------------------------
# Draft preview
# ------------------------------
st.markdown("### Draft preview")

sections = draft.get("sections", [])
for sec in sections:
    title = sec.get("title", "Section")
    key = sec.get("key")
    body = enhanced.get(key) or sec.get("body", "")
    st.markdown(f"#### {title}")
    st.write(body)

st.divider()
# ------------------------------
# Compliance summary
# ------------------------------
st.markdown("### Compliance check")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Missing / gaps**")
    gaps = validation.get("gaps", [])
    if gaps:
        st.write("\n".join([f"• {g}" for g in gaps]))
    else:
        st.success("No major gaps detected.")
with c2:
    st.markdown("**Warnings**")
    warns = validation.get("warnings", [])
    if warns:
        st.write("\n".join([f"• {w}" for w in warns]))
    else:
        st.success("No warnings detected.")

st.divider()

# ------------------------------
# STEP 5 — Download (Grant Application Package PDF)
# ------------------------------
st.subheader("5) Download")

from io import BytesIO
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors

def as_text(x):
    if isinstance(x, list):
        return "\n".join(str(i) for i in x)
    return "" if x is None else str(x)

def make_grant_package_pdf_bytes(
    *,
    suite_title: str,
    subtitle: str,
    prepared_for: str,
    prepared_by: str,
    community_name: str,
    region: str,
    program_name: str,
    requested_budget: int,
    proposal_text_by_section: list[dict],  # [{"title": str, "body": str}]
    evidence_note: str | None = None,
    indicators_before: dict | None = None,
    indicators_after: dict | None = None,
    scenario: dict | None = None,
    requirements: dict | None = None,
    compliance_gaps: list[str] | None = None,
    compliance_warnings: list[str] | None = None,
    logo_path: str | None = None,
    contact_name: str | None = None,
    contact_email: str | None = None,
    contact_phone: str | None = None,
    project_title: str | None = None,
    project_duration: str | None = None,
) -> bytes:
    """
    Outputs a more complete "grant application package" PDF:
      - Cover page (FCI branding)
      - Package overview (key info + included sections)
      - Application checklist / compliance map (simple heuristic mapping)
      - Budget table page (heuristic extraction)
      - Proposal body (long-form sections)
      - Appendices (Evidence note + indicators before/after + scenario)
    """

    requirements = requirements or {}
    indicators_before = indicators_before or {}
    indicators_after = indicators_after or {}
    scenario = scenario or {}
    gaps = compliance_gaps or []
    warns = compliance_warnings or []

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    # Layout
    left = 0.85 * inch
    right = 0.85 * inch
    top = 0.8 * inch
    bottom = 0.75 * inch
    usable_w = W - left - right

    # Typography
    FONT = "Times-Roman"
    FONT_B = "Times-Bold"


    page_num = 0

    # ---------- helpers ----------
    def wrap_lines(text: str, font_name: str, font_size: int, max_width: float):
        words = (text or "").split()
        if not words:
            return [""]
        lines, cur = [], words[0]
        for w in words[1:]:
            test = cur + " " + w
            if c.stringWidth(test, font_name, font_size) <= max_width:
                cur = test
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    def draw_footer():
        # footer line
        c.setStrokeColor(colors.HexColor("#cce7f2"))
        c.setLineWidth(1)
        c.line(left, bottom - 10, W - right, bottom - 10)

        # footer text
        c.setFillColor(colors.grey)
        c.setFont(FONT, 9)
        c.drawString(left, bottom - 24, prepared_by)
        c.drawRightString(W - right, bottom - 24, f"{page_num}")
        c.setFillColor(colors.black)

    def draw_header():
        # header line + running header text (skip on cover)
        c.setStrokeColor(colors.HexColor("#e5e7eb"))
        c.setLineWidth(1)
        c.line(left, H - top + 6, W - right, H - top + 6)

        c.setFillColor(colors.grey)
        c.setFont(FONT, 9)
        c.drawString(left, H - top + 14, "Grant Application Package — Draft")
        c.drawRightString(W - right, H - top + 14, f"{community_name} | {program_name}")
        c.setFillColor(colors.black)

    def new_page(with_header=True):
        nonlocal page_num
        c.showPage()
        page_num += 1
        if with_header:
            draw_header()
        draw_footer()

    def draw_logo_on_cover():
        if not logo_path:
            return
        try:
            # smaller and higher to avoid overlap
            c.drawImage(
                logo_path,
                left - 0.35 * inch,
                H - top - 0.45 * inch,
                width=0.95 * inch,
                height=0.95 * inch,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    def draw_paragraph(text: str, x: float, y: float, font_name: str, font_size: int, line_h: float):
        c.setFont(font_name, font_size)
        for line in wrap_lines(text, font_name, font_size, usable_w):
            if y <= bottom + 30:
                new_page(with_header=True)
                y = H - top - 18  # leave room for header
                c.setFont(font_name, font_size)
            c.drawString(x, y, line)
            y -= line_h
        return y

    def draw_section_title(title: str, y: float):
        bar_h = 18
        if y <= bottom + 90:
            new_page(with_header=True)
            y = H - top - 18
        c.setFillColor(colors.HexColor("#E8F4FA"))
        c.rect(left, y - bar_h + 4, usable_w, bar_h, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#0B3D59"))
        c.setFont(FONT_B, 12)
        c.drawString(left + 10, y - bar_h + 8, title)
        c.setFillColor(colors.black)
        return y - bar_h - 8

    def draw_kv_block(items: list[tuple[str, str]], y: float):
        c.setFont(FONT_B, 11)
        for k, v in items:
            if y <= bottom + 40:
                new_page(with_header=True)
                y = H - top - 18
                c.setFont(FONT_B, 11)
            c.drawString(left, y, f"{k}:")
            c.setFont(FONT, 11)
            c.drawString(left + 120, y, v)
            c.setFont(FONT_B, 11)
            y -= 14
        return y

    def get_required_items(req: dict) -> list[str]:
        # best-effort: accept multiple schema styles
        items = req.get("required_items")
        if isinstance(items, list):
            return [str(x).strip() for x in items if str(x).strip()]
        # sometimes parsers store as "sections" or "requirements"
        for key in ["requirements", "sections", "must_include"]:
            maybe = req.get(key)
            if isinstance(maybe, list):
                out = []
                for x in maybe:
                    if isinstance(x, dict) and x.get("name"):
                        out.append(str(x["name"]).strip())
                    else:
                        out.append(str(x).strip())
                return [x for x in out if x]
        return []

    def find_best_section_for_item(item: str, sections: list[dict]) -> str:
        # heuristic: keyword match in title/body
        needle = (item or "").lower()
        best = ""
        best_score = 0
        for s in sections:
            title = (s.get("title") or "").lower()
            body = (s.get("body") or "").lower()
            score = 0
            if needle and needle in title:
                score += 3
            if needle and needle in body:
                score += 1
            # extra: split words
            for w in needle.split():
                if len(w) >= 5 and w in title:
                    score += 1
            if score > best_score:
                best_score = score
                best = s.get("title") or ""
        return best if best_score > 0 else "Not clearly addressed"

    def extract_budget_items(sections: list[dict]) -> list[tuple[str, str, str]]:
        """
        Try to build rows: (Category, Amount, Justification)
        We’ll look for a section whose title contains 'budget' OR body lines with $.
        """
        budget_rows: list[tuple[str, str, str]] = []
        budget_text = ""

        for s in sections:
            t = (s.get("title") or "").lower()
            if "budget" in t:
                budget_text = s.get("body") or ""
                break

        # simple parse: lines like "Category: $X — justification"
        if budget_text:
            for line in budget_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # crude dollar detection
                if "$" in line:
                    # split into parts
                    cat = line
                    amt = ""
                    just = ""
                    # try common patterns
                    if ":" in line:
                        cat, rest = line.split(":", 1)
                        rest = rest.strip()
                        amt = rest
                    if "—" in line:
                        left_part, right_part = line.split("—", 1)
                        just = right_part.strip()
                        if ":" in left_part:
                            cat, rest = left_part.split(":", 1)
                            amt = rest.strip()
                        else:
                            amt = left_part.strip()
                    budget_rows.append((cat.strip()[:45], amt.strip()[:18], just.strip()[:70]))

        # fallback: single total only
        if not budget_rows:
            budget_rows.append(("Total Requested", f"${requested_budget:,}", "Aligned to scope and requirements"))

        return budget_rows

    def draw_table(
        *,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        col_widths: list[float],
        y: float,
    ) -> float:
        y = draw_section_title(title, y)

        # header row
        c.setFillColor(colors.HexColor("#f3f4f6"))
        row_h = 18
        x = left
        for i, htxt in enumerate(headers):
            c.rect(x, y - row_h + 4, col_widths[i], row_h, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#111827"))
            c.setFont(FONT_B, 10)
            c.drawString(x + 6, y - 10, htxt)
            c.setFillColor(colors.HexColor("#f3f4f6"))
            x += col_widths[i]
        c.setFillColor(colors.black)
        y -= row_h + 6

        # body rows
        for row_i, r in enumerate(rows):
            # if we don't have room for another row, start a new page and continue table
            if y <= bottom + 60:
                new_page(with_header=True)
                y = H - top - 18

                # Continue the SAME table on a new page using remaining rows
                remaining = rows[row_i:]  # <-- THIS is the indexing you were missing
                y = draw_table(
                    title=f"{title} (continued)",
                    headers=headers,
                    rows=remaining
                )
                return y  # recursion draws remaining rows and exits

            x = left
            c.setFont(FONT, 10)

            # draw each cell in the row
            for i, cell in enumerate(r):
                cell = (cell or "").strip()
                lines = wrap_lines(cell, FONT, 10, col_widths[i] - 12)
                c.drawString(x + 6, y - 10, lines[0] if lines else "")
                x += col_widths[i]

            # row separator
            c.setStrokeColor(colors.HexColor("#e5e7eb"))
            c.setLineWidth(1)
            c.line(left, y - 16, left + sum(col_widths), y - 16)

            y -= row_h

        return y - 6

    # ---------- Build a “flat” section list with final bodies ----------
    final_sections = []
    for s in proposal_text_by_section:
        final_sections.append({
            "title": s.get("title") or "Section",
            "body": s.get("body") or "",
        })

    # ---------- COVER PAGE ----------
        page_num = 1

    banner_h = 1.90 * inch
    c.setFillColor(colors.HexColor("#E8F4FA"))
    c.rect(0, H - banner_h, W, banner_h, stroke=0, fill=1)
    c.setFillColor(colors.black)

    # --- Big, obvious positioning knobs ---
    # (0,0 is bottom-left; bigger Y means higher up)
    LOGO_W = 2.35 * inch
    LOGO_H = 0.85 * inch

    # Put logo near the page edge (NOT aligned to left margin)
    LOGO_X = 0.45 * inch
    LOGO_Y = H - 0.50 * inch - LOGO_H  # anchor from absolute top

    # Move title noticeably to the right + up (more separation from logo)
    TITLE_X = W * 0.70     # right of center
    TITLE_Y = H - 0.72 * inch

    SUBTITLE_X = TITLE_X
    SUBTITLE_Y = TITLE_Y - 0.35 * inch

    def draw_logo_on_cover():
        if not logo_path:
            return
        try:
            c.drawImage(
                logo_path,
                LOGO_X,
                LOGO_Y,
                width=LOGO_W,
                height=LOGO_H,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    draw_logo_on_cover()

    # Title + subtitle (bigger + more “cover page”)
    c.setFont(FONT_B, 30)
    c.drawCentredString(TITLE_X, TITLE_Y, suite_title)

    c.setFont(FONT, 14)
    c.setFillColor(colors.HexColor("#4b5563"))
    c.drawCentredString(SUBTITLE_X, SUBTITLE_Y, subtitle)
    c.setFillColor(colors.black)

    # Main content starts LOWER so header feels separated
    y = H - banner_h - 0.80 * inch

    # Section heading
    c.setFont(FONT_B, 16)
    c.drawString(left, y, "Grant Proposal Package")
    y -= 28

    meta_lines = [
        ("Community", community_name),
        ("Region", region),
        ("Program", program_name),
        ("Requested Funding", f"${requested_budget:,}"),
        ("Date", date.today().strftime("%B %d, %Y")),
        ("Prepared for", prepared_for),
        ("Prepared by", prepared_by),
    ]

    # Wider key/value spacing so it looks cleaner
    label_x = left
    value_x = left + 1.85 * inch

    # Subtle divider under “Grant Proposal Package”
    c.setStrokeColor(colors.HexColor("#cce7f2"))
    c.setLineWidth(1.2)
    c.line(left, y + 10, W - right, y + 10)
    c.setStrokeColor(colors.black)

    c.setFont(FONT_B, 12)
    for label, value in meta_lines:
        c.drawString(label_x, y, f"{label}:")
        c.setFont(FONT, 12)
        c.drawString(value_x, y, value)
        c.setFont(FONT_B, 12)
        y -= 20

    # footer on cover
    draw_footer()
    new_page(with_header=True)


    # ---------- APPLICATION CHECKLIST / COMPLIANCE MAP ----------
    y = H - top - 18
    required_items = get_required_items(requirements)
    if not required_items:
        # fallback from gaps (e.g., "Required item not found: 'budget'")
        for g in gaps:
            if "Required item not found:" in g:
                required_items.append(g.split("Required item not found:", 1)[1].strip().strip("'").strip('"'))

    # Build compliance rows
    comp_rows = []
    if required_items:
        for item in required_items[:30]:  # keep sane
            where = find_best_section_for_item(item, final_sections)
            status = "OK" if where != "Not clearly addressed" else "Missing"
            comp_rows.append([item, where, status])
    else:
        comp_rows.append(["(No structured required_items detected from parser)", "—", "—"])

    y = draw_table(
        title="Application Checklist / Compliance Map",
        headers=["Requirement", "Where addressed", "Status"],
        rows=comp_rows,
        col_widths=[usable_w * 0.42, usable_w * 0.40, usable_w * 0.18],
        y=y,
    )

    # Quick summary
    y = draw_section_title("Compliance Summary (Auto)", y)
    if not gaps and not warns:
        y = draw_paragraph("No major gaps or warnings were detected based on the provided requirements.", left, y, FONT, 11, 14)
    else:
        if gaps:
            y = draw_paragraph("Gaps to address:", left, y, FONT_B, 11, 14)
            for g in gaps[:12]:
                y = draw_paragraph(f"• {g}", left + 10, y, FONT, 11, 14)
            y -= 6
        if warns:
            y = draw_paragraph("Warnings / checks:", left, y, FONT_B, 11, 14)
            for w in warns[:12]:
                y = draw_paragraph(f"• {w}", left + 10, y, FONT, 11, 14)

    new_page(with_header=True)

    # ---------- BUDGET TABLE ----------
    y = H - top - 18
    budget_rows = extract_budget_items(final_sections)
    budget_table_rows = [[cat, amt, just] for (cat, amt, just) in budget_rows]

    y = draw_table(
        title="Budget Summary",
        headers=["Category", "Amount", "Justification"],
        rows=budget_table_rows,
        col_widths=[usable_w * 0.30, usable_w * 0.18, usable_w * 0.52],
        y=y,
    )

    budget_note = (
        "Note: This summary is generated from the draft content. "
        "Confirm exact line items and eligible expense categories against the funder’s guidelines before submission."
    )
    y = draw_paragraph(budget_note, left, y, FONT, 10, 13)

    new_page(with_header=True)

    # ---------- PROPOSAL BODY ----------
    y = H - top - 18
    c.setFont(FONT_B, 18)
    c.drawString(left, y, "Proposal Narrative")
    y -= 18
    c.setStrokeColor(colors.HexColor("#cce7f2"))
    c.setLineWidth(1)
    c.line(left, y, W - right, y)
    c.setStrokeColor(colors.black)
    y -= 18

    for s in final_sections:
        title = (s.get("title") or "Section").strip()
        body = (s.get("body") or "").strip()
        if not body:
            continue

        y = draw_section_title(title, y)

        # preserve your LLM long-form (split on blank lines only)
        for para in body.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            y = draw_paragraph(para, left, y, FONT, 11, 14)
            y -= 8
        y -= 6

    new_page(with_header=True)

    # ---------- APPENDICES ----------
    y = H - top - 18
    c.setFont(FONT_B, 18)
    c.drawString(left, y, "Appendices")
    y -= 18
    c.setStrokeColor(colors.HexColor("#cce7f2"))
    c.setLineWidth(1)
    c.line(left, y, W - right, y)
    c.setStrokeColor(colors.black)
    y -= 18

    # Appendix A: Evidence note
    if evidence_note:
        y = draw_section_title("Appendix A — Evidence & Context Note", y)
        for para in evidence_note.split("\n\n"):
            para = para.strip()
            if para:
                y = draw_paragraph(para, left, y, FONT, 11, 14)
                y -= 8
        y -= 6

    # Appendix B: Indicators before/after
    if indicators_before or indicators_after:
        y = draw_section_title("Appendix B — Indicators (Before vs After)", y)
        keys = sorted(set(list(indicators_before.keys()) + list(indicators_after.keys())))
        if not keys:
            keys = ["(no indicators provided)"]

        rows = []
        for k in keys[:20]:
            b = indicators_before.get(k, "—")
            a = indicators_after.get(k, "—")
            rows.append([str(k), str(b), str(a)])

        y = draw_table(
            title="Indicator Table",
            headers=["Indicator", "Before", "After"],
            rows=rows,
            col_widths=[usable_w * 0.45, usable_w * 0.275, usable_w * 0.275],
            y=y,
        )

    # Appendix C: Scenario sliders
    if scenario:
        y = draw_section_title("Appendix C — Scenario Assumptions (What-if Sliders)", y)
        for k, v in list(scenario.items())[:20]:
            y = draw_paragraph(f"• {k}: {v}", left, y, FONT, 11, 14)

    c.save()
    buf.seek(0)
    return buf.read()


# ------------------------------
# Build inputs from your current page state
# ------------------------------
gaps = validation.get("gaps", []) or []
warns = validation.get("warnings", []) or []

proposal_sections_for_pdf = []
for sec in sections:
    title = sec.get("title", "Section")
    key = sec.get("key")
    body = enhanced.get(key) or sec.get("body", "")
    proposal_sections_for_pdf.append({"title": title, "body": as_text(body)})

evidence_note = (profile.get("evidence_note") or "").strip() or None
ind_before = profile.get("indicators_before", {}) or {}
ind_after = profile.get("indicators_after", {}) or {}
scenario = profile.get("scenario", {}) or {}

# Program name: safe fallback (no undefined variable)
program = st.session_state.get("gw_selected_program")
program_name = (
    program.get("name")
    if isinstance(program, dict)
    else (req.get("grant_name") or req.get("program_name") or "")
)

# Optional: try to infer project title from first section title/body
project_title = None
if proposal_sections_for_pdf:
    project_title = proposal_sections_for_pdf[0]["title"]

pdf_bytes = make_grant_package_pdf_bytes(
    suite_title="Grant Proposal Draft",
    subtitle="Evidence → Program Fit → Draft Grants",
    prepared_for="Future Cities Institute (FCI)",
    prepared_by="Future Cities Institute — Prototype Tool",
    community_name=profile.get("community_name", ""),
    region=profile.get("region", ""),
    program_name=program_name,
    requested_budget=budget,
    proposal_text_by_section=proposal_sections_for_pdf,
    evidence_note=evidence_note,
    indicators_before=ind_before,
    indicators_after=ind_after,
    scenario=scenario,
    requirements=req,
    compliance_gaps=gaps,
    compliance_warnings=warns,
    logo_path="assets/fci_logo.png",   # change to your actual file path (png works best)
    project_title=project_title,
    project_duration=req.get("duration") if isinstance(req, dict) else None,
    # contact fields are optional (you can wire these from UI later)
    contact_name=profile.get("ed_officer") if isinstance(profile, dict) else None,
)

st.download_button(
    "⬇️ Download Grant Package (PDF)",
    data=pdf_bytes,
    file_name="grant_application_package.pdf",
    mime="application/pdf",
    key="btn_download_package_pdf"
)

# Optional: keep TXT download for copy/paste
lines = [
    "Grant Proposal Draft",
    "",
    f"Community: {profile.get('community_name','')}",
    f"Region: {profile.get('region','')}",
    f"Local Priority: {profile.get('local_priority','')}",
    f"Requested Funding: ${budget:,}",
    f"Program: {program_name}",
    "",
]
if evidence_note:
    lines += ["=== Evidence Note ===", evidence_note, ""]
lines += ["=== Proposal ===", ""]
for s in proposal_sections_for_pdf:
    lines += [f"=== {s['title']} ===", s["body"], ""]
lines += ["=== Compliance Summary ==="]
for g in gaps:
    lines.append(f"- GAP: {g}")
for w in warns:
    lines.append(f"- WARN: {w}")

proposal_text = "\n".join(lines)

st.download_button(
    "⬇️ Download Draft (TXT)",
    data=proposal_text,
    file_name="proposal_draft.txt",
    mime="text/plain",
    key="btn_download_proposal_txt"
)
