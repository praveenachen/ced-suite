import streamlit as st

# ==============================
# GLOBAL THEME (match app.py)
# ==============================
st.markdown(
    """
<style>
html, body { margin: 0 !important; padding: 0 !important; }

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
main,
.block-container {
  background: #000000 !important;
  color: #ffffff !important;
}

[data-testid="stHeader"],
[data-testid="stSidebar"] { background: #000000 !important; }

.stApp p, .stApp li, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp div {
  color: #ffffff;
}

hr {
  border: none !important;
  height: 2px !important;
  background-color: #f5c400 !important;
  margin: 2rem 0 !important;
}

/* Widgets: white background, black text, yellow border */
.stTextInput input, .stNumberInput input {
  background: #ffffff !important;
  color: #111111 !important;
  border: 2px solid #f5c400 !important;
  border-radius: 10px !important;
}

.stTextArea textarea {
  background: #ffffff !important;
  color: #111111 !important;
  border: 2px solid #f5c400 !important;
  border-radius: 10px !important;
}

div[data-baseweb="slider"] * { color: #ffffff !important; } /* keep slider labels visible */

details, summary { color: #ffffff !important; }

[data-testid="stAlert"] * { color: inherit !important; }

/* =========================
   GLOBAL BUTTON STYLE
========================= */
/* =========================
   FORCE ALL STREAMLIT BUTTONS
   YELLOW BG + BLACK TEXT
========================= */

/* Base button */
.stButton > button {
  background-color: #f5c400 !important;
  color: #111111 !important;
  border: 2px solid #f5c400 !important;
  font-weight: 700 !important;
  border-radius: 10px !important;
}

/* Text inside button (nested spans/divs) */
.stButton > button *,
button[kind] * {
  color: #111111 !important;
}

/* Hover */
.stButton > button:hover {
  background-color: #e6b800 !important;
  border-color: #e6b800 !important;
  color: #111111 !important;
}

/* Active / focus (THIS fixes the white Save Profile issue) */
.stButton > button:active,
.stButton > button:focus,
.stButton > button:focus-visible {
  background-color: #f5c400 !important;
  border-color: #f5c400 !important;
  color: #111111 !important;
  outline: none !important;
  box-shadow: none !important;
}

/* Form submit buttons (Save profile lives here) */
form button {
  background-color: #f5c400 !important;
  color: #111111 !important;
  border: 2px solid #f5c400 !important;
}

/* Disabled */
.stButton > button:disabled {
  background-color: #d1d5db !important;
  border-color: #d1d5db !important;
  color: #6b7280 !important;
}

</style>
""",
    unsafe_allow_html=True,
)

st.header("📊 Community Needs & Impact Planner")
st.caption("Enter your community context → model improvements → generate evidence notes → send to Grant Writer (auto-filled).")

# Load Demo Data (for internal testing)
if st.button("🧪 Load Demo Data", use_container_width=True):
    st.session_state["impact_profile"] = {
        "community_name": "Kinngait",
        "region": "Nunavut",
        "local_priority": "Water infrastructure",
        "challenges": "Frequent boil-water advisories; aging distribution pipes; high operating costs for repairs.",
        "timeline": "Apr–Dec 2026",
    }
    st.session_state["impact_indicators"] = {
        "water_reliability": 55.0,
        "unemployment_rate": 13.2,
        "internet_access": 62.0,
    }
    st.session_state["impact_budget"] = 250_000
    st.success("Demo data loaded. Scroll down to review/edit.")

# ------------------------------
# Helpers
# ------------------------------
def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))

def compute_need_index(water_reliability, unemployment_rate, internet_access):
    water_bad = 1 - (water_reliability / 100.0)
    internet_bad = 1 - (internet_access / 100.0)
    unemp_bad = clamp(unemployment_rate, 0, 30) / 30.0
    need = 0.4 * water_bad + 0.3 * internet_bad + 0.3 * unemp_bad
    return round(need, 3)

def apply_scenario(base_water, base_unemp, base_internet, improve_water_pct, reduce_unemp_pct, improve_internet_pct):
    new_water = clamp(base_water * (1 + improve_water_pct / 100.0), 0, 100)
    new_unemp = clamp(base_unemp * (1 - reduce_unemp_pct / 100.0), 0, 100)
    new_internet = clamp(base_internet * (1 + improve_internet_pct / 100.0), 0, 100)
    return new_water, new_unemp, new_internet

def build_planning_note(profile, before_vals, after_vals, before_need, after_need, scenario, requested_budget=None):
    c = profile.get("community_name", "your community")
    region = profile.get("region", "")
    priority = profile.get("local_priority", "")
    challenges = profile.get("challenges", "")
    timeline = profile.get("timeline", "")

    bw, bu, bi = before_vals
    aw, au, ai = after_vals

    lines = []
    lines.append(f"**Community context:** {c}" + (f" ({region})" if region else "") + ".")
    if priority:
        lines.append(f"**Local priority:** {priority}.")
    if requested_budget:
        lines.append(f"**Target funding request:** ${int(requested_budget):,}.")
    if challenges:
        lines.append(f"**Key challenges (local context):** {challenges}")
    if timeline:
        lines.append(f"**Timeline:** {timeline}")

    lines.append("")
    lines.append("**Baseline indicators (current):**")
    lines.append(f"- Water reliability: {bw:.1f}/100")
    lines.append(f"- Unemployment rate: {bu:.1f}%")
    lines.append(f"- Internet access: {bi:.1f}/100")
    lines.append(f"- Need Index (before): {before_need}")

    lines.append("")
    lines.append("**Scenario (proposed improvements):**")
    lines.append(f"- Improve water reliability by {scenario['improve_water_pct']}% → {aw:.1f}/100")
    lines.append(f"- Reduce unemployment by {scenario['reduce_unemp_pct']}% → {au:.1f}%")
    lines.append(f"- Improve internet access by {scenario['improve_internet_pct']}% → {ai:.1f}/100")
    lines.append(f"- Need Index (after): {after_need}")

    delta = round(before_need - after_need, 3)
    lines.append("")
    lines.append(
        f"**Estimated impact:** Need Index decreases by **{delta}** (from {before_need} → {after_need}), "
        "indicating a measurable reduction in service gaps aligned with the proposed project."
    )

    lines.append("")
    lines.append("**Copy-ready evidence statement (for grant applications):**")
    evidence = (
        f"{c} is proposing targeted investments to address {priority or 'key community needs'}. "
        f"Based on current indicators (water reliability {bw:.1f}/100, unemployment {bu:.1f}%, internet access {bi:.1f}/100), "
        f"our baseline Need Index is {before_need}. Under the proposed scenario, these indicators improve "
        f"(water reliability {aw:.1f}/100, unemployment {au:.1f}%, internet access {ai:.1f}/100), reducing the Need Index to {after_need}. "
        f"This provides evidence of measurable community-level impact aligned with funder priorities."
    )
    lines.append(evidence)

    return "\n".join(lines)

# ------------------------------
# Session state defaults
# ------------------------------
if "impact_profile" not in st.session_state:
    st.session_state["impact_profile"] = {
        "community_name": "",
        "region": "",
        "local_priority": "",
        "challenges": "",
        "timeline": "",
    }

if "impact_indicators" not in st.session_state:
    st.session_state["impact_indicators"] = {
        "water_reliability": 55.0,
        "unemployment_rate": 13.2,
        "internet_access": 62.0,
    }

if "impact_budget" not in st.session_state:
    st.session_state["impact_budget"] = 250_000

# ------------------------------
# 1) Community profile inputs
# ------------------------------
st.subheader("1) Community profile (enter your info)")

with st.form("impact_profile_form", clear_on_submit=False):
    c1, c2 = st.columns(2)
    with c1:
        st.session_state["impact_profile"]["community_name"] = st.text_input(
            "Community name",
            value=st.session_state["impact_profile"]["community_name"],
            placeholder="e.g., Kinngait"
        )
        st.session_state["impact_profile"]["region"] = st.text_input(
            "Region / Province",
            value=st.session_state["impact_profile"]["region"],
            placeholder="e.g., Nunavut"
        )
    with c2:
        st.session_state["impact_profile"]["local_priority"] = st.text_input(
            "Local priority (what you’re trying to improve)",
            value=st.session_state["impact_profile"]["local_priority"],
            placeholder="e.g., Water infrastructure"
        )
        st.session_state["impact_profile"]["timeline"] = st.text_input(
            "Timeline (optional)",
            value=st.session_state["impact_profile"]["timeline"],
            placeholder="e.g., Apr–Dec 2026"
        )

    st.session_state["impact_profile"]["challenges"] = st.text_area(
        "Key challenges (1–3 bullets or short paragraph)",
        value=st.session_state["impact_profile"]["challenges"],
        placeholder="e.g., Frequent boil-water advisories; aging pipes; high operating costs..."
    )

    st.session_state["impact_budget"] = st.number_input(
        "Target funding request ($)",
        min_value=10_000,
        max_value=5_000_000,
        value=int(st.session_state["impact_budget"]),
        step=5_000
    )

    saved = st.form_submit_button("Save profile")

if saved:
    st.success("Saved. Continue to indicators & scenario.")

profile = st.session_state["impact_profile"]
if not profile.get("community_name") or not profile.get("local_priority"):
    st.info("Enter at least **Community name** and **Local priority** to proceed.")
    st.stop()

st.divider()

# ------------------------------
# 2) Current indicators (manual entry)
# ------------------------------
st.subheader("2) Current indicators (baseline)")

i1, i2, i3 = st.columns(3)
with i1:
    st.session_state["impact_indicators"]["water_reliability"] = st.number_input(
        "Water reliability (0–100)",
        min_value=0.0, max_value=100.0,
        value=float(st.session_state["impact_indicators"]["water_reliability"]),
        step=1.0
    )
with i2:
    st.session_state["impact_indicators"]["unemployment_rate"] = st.number_input(
        "Unemployment rate (%)",
        min_value=0.0, max_value=100.0,
        value=float(st.session_state["impact_indicators"]["unemployment_rate"]),
        step=0.1
    )
with i3:
    st.session_state["impact_indicators"]["internet_access"] = st.number_input(
        "Internet access (0–100)",
        min_value=0.0, max_value=100.0,
        value=float(st.session_state["impact_indicators"]["internet_access"]),
        step=1.0
    )

bw = st.session_state["impact_indicators"]["water_reliability"]
bu = st.session_state["impact_indicators"]["unemployment_rate"]
bi = st.session_state["impact_indicators"]["internet_access"]

before_need = compute_need_index(bw, bu, bi)

st.divider()

# ------------------------------
# 3) Scenario sliders (what-if)
# ------------------------------
st.subheader("3) Scenario sliders (what-if improvements)")
st.caption("Simulate proposed impact. The Need Index updates automatically.")

s1 = st.slider("Improve water reliability by (%)", 0, 50, 10)
s2 = st.slider("Reduce unemployment by (%)", 0, 50, 10)
s3 = st.slider("Improve internet access by (%)", 0, 50, 10)

scenario = {"improve_water_pct": s1, "reduce_unemp_pct": s2, "improve_internet_pct": s3}

aw, au, ai = apply_scenario(bw, bu, bi, s1, s2, s3)
after_need = compute_need_index(aw, au, ai)

m1, m2 = st.columns(2)
with m1:
    st.metric("Need Index (Before)", before_need)
with m2:
    st.metric("Need Index (After)", after_need)

st.divider()

# ------------------------------
# 4) Draft planning notes + send to grant writer
# ------------------------------
st.subheader("4) Evidence & planning notes")

note = build_planning_note(
    profile=profile,
    before_vals=(bw, bu, bi),
    after_vals=(aw, au, ai),
    before_need=before_need,
    after_need=after_need,
    scenario=scenario,
    requested_budget=st.session_state["impact_budget"],
)

st.text_area("Planning Note (copy/paste ready)", value=note, height=280)

community_context = {
    "community_name": profile.get("community_name", ""),
    "region": profile.get("region", ""),
    "local_priority": profile.get("local_priority", ""),
    "challenges": profile.get("challenges", ""),
    "timeline": profile.get("timeline", ""),
    "requested_budget": st.session_state["impact_budget"],
    "indicators_before": {"water_reliability": bw, "unemployment_rate": bu, "internet_access": bi},
    "indicators_after": {"water_reliability": aw, "unemployment_rate": au, "internet_access": ai},
    "need_index_before": before_need,
    "need_index_after": after_need,
    "evidence_note": note,
    "scenario": scenario,
}

c1, c2 = st.columns([1, 1])

with c1:
    if st.button("➡️ Send to Grant Writer", type="primary", use_container_width=True):
        st.session_state["community_context"] = community_context
        st.success("Sent! You can jump to Grant Writer now.")

with c2:
    if st.button("📝 Go to Grant Writer", use_container_width=True):
        st.session_state["community_context"] = community_context
        st.switch_page("pages/Grant_Writer.py")
