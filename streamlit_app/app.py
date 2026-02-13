import streamlit as st
from datetime import date

st.set_page_config(page_title="CED Suite", page_icon="🧭", layout="wide")

# =========================================================
# GLOBAL STYLES (DO NOT TOUCH UNLESS YOU MEAN IT)
# =========================================================
st.markdown(
    """
<style>

/* -------- REMOVE WEIRD TOP GAPS -------- */
html, body {
  margin: 0 !important;
  padding: 0 !important;
}

/* -------- BLACK BACKGROUND EVERYWHERE -------- */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
main,
.block-container {
  background-color: #000000 !important;
  color: #ffffff !important;
}

/* Header + sidebar */
[data-testid="stHeader"],
[data-testid="stSidebar"] {
  background-color: #000000 !important;
}

/* Default text = white */
.stApp {
  color: #ffffff !important;
}

/* -------- YELLOW DIVIDERS -------- */
hr {
  border: none !important;
  height: 2px !important;
  background-color: #f5c400 !important;
  margin: 2rem 0 !important;
}

/* =========================================================
   🔥 THE FIX: FORCE BLACK TEXT INSIDE WHITE CARDS
   ========================================================= */
.stApp .white-card,
.stApp .white-card *,
.stApp .white-card p,
.stApp .white-card li,
.stApp .white-card span,
.stApp .white-card div,
.stApp .white-card b,
.stApp .white-card strong,
.stApp .white-card em,
.stApp .white-card a,
.stApp .white-card h1,
.stApp .white-card h2,
.stApp .white-card h3,
.stApp .white-card h4 {
  color: #111111 !important;
}

/* =========================
   GLOBAL BUTTON STYLE
========================= */
.stButton > button {
  background-color: #f5c400 !important;   /* yellow */
  color: #111111 !important;              /* black text */
  border: 2px solid #f5c400 !important;
  font-weight: 700 !important;
  border-radius: 10px !important;
}

/* Hover state */
.stButton > button:hover {
  filter: brightness(0.95) !important;
}

/* Disabled buttons */
.stButton > button:disabled {
  background-color: #d1d5db !important;
  border-color: #d1d5db !important;
  color: #6b7280 !important;
}


</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# HEADER
# =========================================================
logo_col, title_col, spacer_col = st.columns([1.3, 3.2, 1])

with logo_col:
    st.image("assets/fci_logo2.jpg", width=200)

with title_col:
    st.markdown(
        """
        <div style="text-align:center;">
            <div style="font-size:3.2rem;font-weight:900;">
                🧭 CED Suite
            </div>
            <div style="font-size:1.2rem;color:#d6d6d6;">
                Evidence → Program Fit → Draft Grants
            </div>
            <div style="font-size:0.95rem;color:#bdbdbd;max-width:900px;margin:10px auto;">
                <em>
                Prototype tool by the <strong>Future Cities Institute (FCI)</strong> to support
                community-led, data-informed Community Economic Development (CED)
                planning and grant/proposal drafting.
                </em>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# =========================================================
# CONTEXT BANNER
# =========================================================
ctx = st.session_state.get("community_context", None)
has_ctx = isinstance(ctx, dict) and bool(ctx.get("community_name")) and bool(ctx.get("local_priority"))

def _fmt_money(x):
    try:
        return f"${int(x):,}"
    except Exception:
        return "—"

if has_ctx:
    st.success(
        f"Workspace loaded from Impact Planner: **{ctx.get('community_name')}** "
        f"(Need Index {ctx.get('need_index_before')} → {ctx.get('need_index_after')})"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Region")
        st.write(ctx.get("region", "—"))
    with c2:
        st.caption("Local priority")
        st.write(ctx.get("local_priority", "—"))
    with c3:
        st.caption("Target funding request")
        st.write(_fmt_money(ctx.get("requested_budget")))

    with st.expander("View evidence note"):
        st.write(ctx.get("evidence_note", "—"))

    with st.expander("Start fresh"):
        if st.button("🗑️ Clear workspace", use_container_width=True):
            st.session_state.pop("community_context", None)
            st.success("Cleared.")

    st.divider()

# =========================================================
# MAIN CARDS
# =========================================================
st.markdown("### What You Can Do Here")

col1, col2 = st.columns(2, gap="large")

card_style = """
background-color:#ffffff;
padding:24px;
border-radius:14px;
border:2px solid #f5c400;
height:100%;
"""

with col1:
    st.markdown(
        f"""
        <div class="white-card" style="{card_style}">
            <h3>📊 Impact Planner</h3>
            <ul>
                <li>Enter community context (name, region, priority)</li>
                <li>Set baseline indicators and generate a <b>Need Index</b></li>
                <li>Use <b>sliders</b> to test what-if scenarios</li>
                <li>Create a copy-ready <b>Evidence / Planning Note</b></li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="white-card" style="{card_style}">
            <h3>📝 Grant Writer</h3>
            <ul>
                <li>Upload grant applications (PDF / DOCX / TXT)</li>
                <li>Generate <b>requirements-aligned</b> drafts</li>
                <li>Run a <b>compliance check</b></li>
                <li>Download submission-ready PDFs</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("### 🚀 Ready to Start?")

if st.button("Start Now →", type="primary", use_container_width=True):
    if has_ctx:
        st.switch_page("pages/Grant_Writer.py")
    else:
        st.switch_page("pages/Impact_Planner.py")

st.divider()

# =========================================================
# WHO IT SERVES
# =========================================================
st.markdown("### Who It Serves")

c1, c2, c3 = st.columns(3, gap="large")

bottom_card_style = """
background-color:#ffffff;
padding:20px;
border-radius:12px;
border:2px solid #f5c400;
height:100%;
"""

with c1:
    st.markdown(
        f"""
        <div class="white-card" style="{bottom_card_style}">
            <h4>🤝 Economic Development Officers</h4>
            <ul>
                <li>Move from evidence to drafts fast</li>
                <li>Aligned proposal structure</li>
                <li>Copy-ready outputs</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="white-card" style="{bottom_card_style}">
            <h4>🧭 Community Leaders & Elders</h4>
            <ul>
                <li>Plain-language planning</li>
                <li>Scenario testing</li>
                <li>Evidence-backed outcomes</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="white-card" style="{bottom_card_style}">
            <h4>🔬 Researchers & Partners</h4>
            <ul>
                <li>Reproducible workflows</li>
                <li>Structured + unstructured inputs</li>
                <li>Extensible architecture</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.caption(f"© {date.today().year} Future Cities Institute — Prototype tool")
