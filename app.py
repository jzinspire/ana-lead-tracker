import streamlit as st
import pandas as pd
import json
import time
import os
from datetime import datetime, date
from supabase import create_client, Client
import anthropic

# Load .env so SUPABASE_URL / SUPABASE_KEY / APIFY_API_TOKEN are available via
# os.getenv() when running locally. On Streamlit Cloud, the secrets.toml managed
# by the platform takes precedence (see _get_secret() below).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on env vars set in the shell


def _get_secret(key: str, default: str = "") -> str:
    """Read a secret from Streamlit secrets if available, else from env vars.

    Workaround for a Streamlit gotcha: `st.secrets.get(...)` raises
    StreamlitSecretNotFoundError when no secrets.toml file exists at all,
    instead of returning the supplied default. This helper makes the lookup
    safe in local development (.env only, no secrets.toml).
    """
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


def _call_anthropic_api(user_prompt: str, system_prompt: str = "", max_tokens: int = 2048) -> str:
    """Call the Anthropic API directly. Used as fallback when Claude CLI/SDK unavailable."""
    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        return "[No ANTHROPIC_API_KEY configured. Add it to Streamlit secrets or .env]"
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system_prompt if system_prompt else anthropic.NOT_GIVEN,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return msg.content[0].text


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Ana Lead Tracker",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Password gate — prevents anyone with the public Streamlit Cloud URL from
# accessing leads, call notes, and scoring data. Only Josue and Santiago
# know the password (shared via Slack/text, set via APP_PASSWORD env var).
# ---------------------------------------------------------------------------
def _check_password() -> bool:
    """Returns True if the user has entered the correct password, False otherwise.
    Stores the result in session state so it's only asked once per session."""
    expected = _get_secret("APP_PASSWORD")
    if not expected:
        # No password configured = no gate. Helpful for first-time local setup
        # before user has added APP_PASSWORD to .env.
        return True
    if st.session_state.get("password_correct"):
        return True

    st.title("🔒 Ana Lead Tracker")
    st.caption("Internal Itxaz sales tool — partner access only.")
    pwd = st.text_input("Password", type="password", key="pwd_input")
    if pwd:
        if pwd == expected:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not _check_password():
    st.stop()


STATUSES = [
    "New",
    "Research Done",
    "Call 1 Made",
    "Call 2 Made",
    "Call 3 Made",
    "Voicemail Left",
    "No Answer (3+ attempts)",
    "Interested - Demo Booked",
    "Not Interested",
    "Do Not Contact",
    "Closed Won",
    "Closed Lost",
]

SCORE_FIELDS = [
    ("score_call_volume", "Call Volume"),
    ("score_missed_call_pain", "Missed Call Pain"),
    ("score_bilingual", "Bilingual Opportunity"),
    ("score_tech_readiness", "Tech Readiness"),
    ("score_ease_of_closing", "Ease of Closing"),
    ("score_urgency", "Urgency"),
]

DEFAULT_WEIGHTS = {
    "call_volume": 1.0,
    "missed_call_pain": 1.0,
    "bilingual": 1.0,
    "tech_readiness": 1.0,
    "ease_of_closing": 1.0,
    "urgency": 1.0,
}

# ---------------------------------------------------------------------------
# Supabase connection
# ---------------------------------------------------------------------------
@st.cache_resource
def get_supabase() -> Client:
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_KEY")
    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_KEY. Check your .env or Streamlit secrets.")
        st.stop()
    return create_client(url, key)


def sb() -> Client:
    return get_supabase()


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def load_businesses(archived: bool = False) -> pd.DataFrame:
    resp = (
        sb()
        .table("businesses")
        .select("*")
        .eq("archived", archived)
        .order("overall_score", desc=True)
        .execute()
    )
    if not resp.data:
        return pd.DataFrame()
    return pd.DataFrame(resp.data)


def load_top_n(n: int = 50) -> pd.DataFrame:
    resp = (
        sb()
        .table("businesses")
        .select("*")
        .eq("archived", False)
        .order("overall_score", desc=True)
        .limit(n)
        .execute()
    )
    if not resp.data:
        return pd.DataFrame()
    return pd.DataFrame(resp.data)


def load_business(business_id: str) -> dict | None:
    resp = sb().table("businesses").select("*").eq("id", business_id).single().execute()
    return resp.data if resp.data else None


def update_business(business_id: str, updates: dict):
    sb().table("businesses").update(updates).eq("id", business_id).execute()


def load_call_notes(business_id: str) -> list[dict]:
    resp = (
        sb()
        .table("call_notes")
        .select("*")
        .eq("business_id", business_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def add_call_note(business_id: str, note: dict):
    note["business_id"] = business_id
    sb().table("call_notes").insert(note).execute()


def load_settings() -> dict:
    resp = sb().table("settings").select("*").execute()
    settings = {}
    for row in (resp.data or []):
        settings[row["key"]] = row["value"]
    return settings


def save_setting(key: str, value):
    sb().table("settings").upsert({"key": key, "value": json.loads(json.dumps(value))}).execute()


def load_research_runs() -> list[dict]:
    resp = (
        sb()
        .table("research_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(20)
        .execute()
    )
    return resp.data or []


def get_scoring_weights() -> dict:
    settings = load_settings()
    return settings.get("scoring_weights", DEFAULT_WEIGHTS)


def compute_overall_score(scores: dict, weights: dict) -> float:
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0
    field_to_weight_key = {
        "score_call_volume": "call_volume",
        "score_missed_call_pain": "missed_call_pain",
        "score_bilingual": "bilingual",
        "score_tech_readiness": "tech_readiness",
        "score_ease_of_closing": "ease_of_closing",
        "score_urgency": "urgency",
    }
    weighted_sum = 0
    for field, weight_key in field_to_weight_key.items():
        weighted_sum += float(scores.get(field, 0)) * weights.get(weight_key, 1.0)
    return round(weighted_sum / total_weight, 2)


def get_feedback_history() -> list[dict]:
    resp = (
        sb()
        .table("call_notes")
        .select("*, businesses(name, industry)")
        .not_.is_("scoring_feedback", "null")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return resp.data or []


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def score_color(score: float) -> str:
    if score >= 9.0:
        return "🟢"
    elif score >= 8.0:
        return "🔵"
    elif score >= 6.0:
        return "🟡"
    else:
        return "🔴"


def status_emoji(status: str) -> str:
    mapping = {
        "New": "⬜",
        "Research Done": "🔍",
        "Call 1 Made": "📞",
        "Call 2 Made": "📞📞",
        "Call 3 Made": "📞📞📞",
        "Voicemail Left": "📩",
        "No Answer (3+ attempts)": "❌",
        "Interested - Demo Booked": "🎯",
        "Not Interested": "👎",
        "Do Not Contact": "🚫",
        "Closed Won": "✅",
        "Closed Lost": "💀",
    }
    return mapping.get(status, "")


# ---------------------------------------------------------------------------
# PAGE: Dashboard
# ---------------------------------------------------------------------------
def page_dashboard():
    st.title("Ana Lead Tracker")
    st.caption("Internal sales tool — Find, score, and track the best prospects for Ana Receptionist")

    df = load_businesses()
    if df.empty:
        st.info("No businesses in the database yet. Run a Deep Research to get started, or check your Supabase connection.")
        return

    # Quick stats
    col1, col2, col3, col4, col5 = st.columns(5)
    active = df[~df["status"].isin(["Do Not Contact", "Closed Lost", "Not Interested"])]
    col1.metric("Total Leads", len(df))
    col2.metric("Active Leads", len(active))
    col3.metric("Avg Score", f"{df['overall_score'].mean():.1f}")
    col4.metric("Demos Booked", len(df[df["status"] == "Interested - Demo Booked"]))
    col5.metric("Closed Won", len(df[df["status"] == "Closed Won"]))

    st.divider()

    # Pipeline summary
    st.subheader("Pipeline Summary")
    status_counts = df["status"].value_counts()
    cols = st.columns(4)
    for i, status in enumerate(STATUSES):
        count = status_counts.get(status, 0)
        if count > 0:
            cols[i % 4].markdown(f"{status_emoji(status)} **{status}:** {count}")

    st.divider()

    # Top 50
    st.subheader("Top 50 Prospects")
    top = load_top_n(50)
    if top.empty:
        st.info("No leads scored yet.")
        return

    for _, row in top.iterrows():
        score = float(row.get("overall_score", 0))
        col_score, col_name, col_industry, col_city, col_status, col_action = st.columns(
            [1, 3, 2, 1.5, 2, 1]
        )
        col_score.markdown(f"### {score_color(score)} {score}")
        col_name.markdown(f"**{row['name']}**")
        col_industry.markdown(row.get("industry", "—"))
        col_city.markdown(row.get("city", "—"))
        col_status.markdown(f"{status_emoji(row.get('status', ''))} {row.get('status', '—')}")
        if col_action.button("View", key=f"view_{row['id']}"):
            st.session_state["selected_business_id"] = row["id"]
            st.session_state["page"] = "Lead Detail"
            st.rerun()


# ---------------------------------------------------------------------------
# PAGE: All Businesses
# ---------------------------------------------------------------------------
def page_all_businesses():
    st.title("All Businesses")

    df = load_businesses()
    if df.empty:
        st.info("No businesses in the database.")
        return

    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        search = st.text_input("Search by name", "")
    with col2:
        industries = ["All"] + sorted(df["industry"].dropna().unique().tolist())
        sel_industry = st.selectbox("Industry", industries)
    with col3:
        cities = ["All"] + sorted(df["city"].dropna().unique().tolist())
        sel_city = st.selectbox("City", cities)
    with col4:
        sel_status = st.selectbox("Status", ["All"] + STATUSES)

    score_range = st.slider("Score range", 0.0, 10.0, (0.0, 10.0), 0.1)

    # Apply filters
    filtered = df.copy()
    if search:
        filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]
    if sel_industry != "All":
        filtered = filtered[filtered["industry"] == sel_industry]
    if sel_city != "All":
        filtered = filtered[filtered["city"] == sel_city]
    if sel_status != "All":
        filtered = filtered[filtered["status"] == sel_status]
    filtered = filtered[
        (filtered["overall_score"] >= score_range[0])
        & (filtered["overall_score"] <= score_range[1])
    ]

    st.caption(f"Showing {len(filtered)} of {len(df)} businesses")

    # Display table
    display_cols = ["name", "industry", "city", "overall_score", "status", "website"]
    display_df = filtered[display_cols].copy()
    display_df.columns = ["Name", "Industry", "City", "Score", "Status", "Website"]
    display_df = display_df.sort_values("Score", ascending=False).reset_index(drop=True)
    display_df.index = display_df.index + 1

    st.dataframe(display_df, use_container_width=True, height=500)

    # Click to view detail
    st.subheader("Open Lead Detail")
    business_names = filtered["name"].tolist()
    if business_names:
        selected_name = st.selectbox("Select a business", business_names, key="biz_select")
        if st.button("Open Detail"):
            biz_row = filtered[filtered["name"] == selected_name].iloc[0]
            st.session_state["selected_business_id"] = biz_row["id"]
            st.session_state["page"] = "Lead Detail"
            st.rerun()

    # CSV export
    st.divider()
    csv = filtered.to_csv(index=False)
    st.download_button(
        label="Export Filtered Results (CSV)",
        data=csv,
        file_name=f"ana_leads_{date.today().isoformat()}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# PAGE: Lead Detail
# ---------------------------------------------------------------------------
def page_lead_detail():
    business_id = st.session_state.get("selected_business_id")
    if not business_id:
        st.info("Select a business from the Dashboard or All Businesses page.")
        if st.button("Go to Dashboard"):
            st.session_state["page"] = "Dashboard"
            st.rerun()
        return

    biz = load_business(business_id)
    if not biz:
        st.error("Business not found.")
        return

    # Header
    score = float(biz.get("overall_score", 0))
    st.title(f"{score_color(score)} {biz['name']}")
    st.caption(f"{biz.get('industry', '—')} · {biz.get('city', '—')}, {biz.get('state', 'AZ')}")

    # Quick info
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Score", score)
    col2.markdown(f"**Status:** {status_emoji(biz.get('status', ''))} {biz.get('status', '—')}")
    if biz.get("website"):
        col3.markdown(f"**Website:** [{biz['website']}](https://{biz['website']})")
    if biz.get("phone"):
        col4.markdown(f"**Phone:** {biz['phone']}")

    st.divider()

    # Score Breakdown
    st.subheader("Score Breakdown")

    # Data-provenance badge: distinguish real research from hardcoded seed data
    is_enriched = bool(biz.get("enrichment_completed_at"))
    has_research_run = bool(biz.get("last_research_run_id"))
    if is_enriched:
        st.success("✅ **Evidence-backed scores** — each criterion below was scored from real signals (Google reviews, website inspection).")
    elif has_research_run:
        st.info("ℹ️ **Researched scores** — scored by Claude from limited data (no per-criterion evidence captured). Re-run research to enrich.")
    else:
        st.warning("⚠️ **Seed-data scores (unverified)** — these numbers were hardcoded as starting estimates, not researched. Click **Re-research this business** below to replace with real evidence.")

    weights = get_scoring_weights()
    score_cols = st.columns(6)
    for i, (field, label) in enumerate(SCORE_FIELDS):
        val = float(biz.get(field, 0))
        score_cols[i].metric(label, f"{val}/10")

    # Per-criterion evidence (only present on enrichment-driven scores)
    evidence_fields = [
        ("evidence_call_volume", "Call Volume"),
        ("evidence_missed_call_pain", "Missed Call Pain"),
        ("evidence_bilingual", "Bilingual Opportunity"),
        ("evidence_tech_readiness", "Tech Readiness"),
        ("evidence_ease_of_closing", "Ease of Closing"),
        ("evidence_urgency", "Urgency"),
    ]
    has_any_evidence = any(biz.get(f) for f, _ in evidence_fields)
    if has_any_evidence:
        with st.expander("📋 Evidence per criterion (real data behind each score)", expanded=True):
            for field, label in evidence_fields:
                ev = biz.get(field)
                if ev:
                    st.markdown(f"**{label}:** {ev}")

    # Raw signals (for full transparency)
    if biz.get("website_signals") or biz.get("review_signals"):
        with st.expander("🔬 Raw signals (scraped data)"):
            ws = biz.get("website_signals")
            rs = biz.get("review_signals")
            if rs:
                st.markdown("**Review signals**")
                st.json(rs)
            if ws:
                st.markdown("**Website signals**")
                st.json(ws)

    if biz.get("key_evidence"):
        st.markdown(f"**Key Evidence:** {biz['key_evidence']}")
    if biz.get("score_explanation"):
        with st.expander("Full Score Explanation"):
            st.markdown(biz["score_explanation"])

    st.divider()

    # Status Update
    st.subheader("Update Status")
    col_status, col_save = st.columns([3, 1])
    current_idx = STATUSES.index(biz["status"]) if biz["status"] in STATUSES else 0
    new_status = col_status.selectbox("Status", STATUSES, index=current_idx, key="status_select")

    not_interested_reason = None
    if new_status == "Not Interested":
        not_interested_reason = st.text_input(
            "Reason (required)", value=biz.get("not_interested_reason", ""), key="ni_reason"
        )

    if col_save.button("Save Status"):
        if new_status == "Not Interested" and not not_interested_reason:
            st.error("Please provide a reason for Not Interested.")
        else:
            updates = {"status": new_status}
            if not_interested_reason is not None:
                updates["not_interested_reason"] = not_interested_reason
            update_business(business_id, updates)
            st.success(f"Status updated to: {new_status}")
            st.rerun()

    # Re-research this business — replaces hardcoded/inferred scores with
    # evidence-backed ones from the enrichment pipeline.
    if st.button("🔄 Re-research this business (real-data scoring)"):
        with st.spinner("Fetching website + reviews + scoring with evidence..."):
            try:
                _rescore_single_business(biz)
                st.success("Re-researched with real evidence. Reloading…")
                st.rerun()
            except Exception as e:
                st.error(f"Re-research failed: {e}")

    st.divider()

    # Call Script
    st.subheader("Personalized Call Script")
    if biz.get("suggested_call_script"):
        st.markdown(biz["suggested_call_script"])
    else:
        st.markdown(_generate_default_script(biz))

    st.divider()

    # Call History & Notes
    st.subheader("Call History & Notes")
    notes = load_call_notes(business_id)
    if notes:
        for note in notes:
            ts = note.get("created_at", "")[:16].replace("T", " ")
            note_type = note.get("note_type", "call").upper()
            st.markdown(f"**[{note_type}] {ts}** — {note.get('contact_name', 'Unknown')}")
            st.markdown(note.get("content", ""))
            if note.get("outcome"):
                st.markdown(f"*Outcome:* {note['outcome']}")
            if note.get("next_action"):
                st.markdown(f"*Next action:* {note['next_action']} (by {note.get('next_action_date', '—')})")
            st.divider()
    else:
        st.caption("No notes yet.")

    # Add new note
    st.subheader("Add Note")
    with st.form("add_note_form"):
        note_type = st.selectbox("Type", ["call", "email", "voicemail", "research", "internal"])
        contact_name = st.text_input("Contact name")
        contact_role = st.text_input("Contact role")
        content = st.text_area("Notes", height=100)
        outcome = st.text_input("Outcome")
        next_action = st.text_input("Next action")
        next_action_date = st.date_input("Next action date", value=None)

        st.markdown("---")
        st.markdown("**Feedback for scoring improvement** (optional)")
        actual_interest = st.selectbox(
            "Actual interest level",
            [None, "very_high", "high", "medium", "low", "none"],
            format_func=lambda x: "— Select —" if x is None else x.replace("_", " ").title(),
        )
        scoring_feedback = st.text_area(
            "How should scoring change for businesses like this?",
            height=60,
            placeholder="e.g., 'Bilingual score was too high — they only serve English speakers'",
        )

        submitted = st.form_submit_button("Save Note")
        if submitted and content:
            note_data = {
                "note_type": note_type,
                "contact_name": contact_name or None,
                "contact_role": contact_role or None,
                "content": content,
                "outcome": outcome or None,
                "next_action": next_action or None,
                "next_action_date": str(next_action_date) if next_action_date else None,
                "actual_interest_level": actual_interest,
                "scoring_feedback": scoring_feedback or None,
            }
            add_call_note(business_id, note_data)
            st.success("Note saved!")
            st.rerun()

    # Back button
    st.divider()
    if st.button("← Back to Dashboard"):
        st.session_state["page"] = "Dashboard"
        st.rerun()


def _generate_default_script(biz: dict) -> str:
    name = biz.get("name", "the business")
    industry = biz.get("industry", "your industry")
    city = biz.get("city", "Phoenix")
    evidence = biz.get("key_evidence", "")

    return f"""
> **Opening:**
> "Hi, this is [Your Name] from Itxaz. I'm reaching out because we work with {industry.lower()} businesses in {city} to make sure they never miss a customer call — even after hours or during busy times."

> **Value hook (based on research):**
> "I noticed {name} {('— ' + evidence[:120]) if evidence else 'handles a lot of inbound calls'}. A lot of businesses like yours tell us they lose 20-30% of calls during peak hours. Our AI receptionist Ana picks up every call, books appointments, and speaks English and Spanish."

> **Ask:**
> "Would you be open to a quick 10-minute demo to see how it works? We're already live with another {industry.split('/')[0].strip().lower()} business in the Valley."

> **If objection — "we're fine":**
> "Totally understand. Quick question though — do you know roughly how many calls go to voicemail during your busiest hours? Most businesses we work with are surprised by the number."

> **Close:**
> "Great, let me send you a calendar link. What email works best?"
"""


# ---------------------------------------------------------------------------
# PAGE: Run Deep Research
# ---------------------------------------------------------------------------
def page_research():
    st.title("Deep Research")
    st.caption("Find and score new prospects using web data + Claude AI analysis")

    # Research history
    runs = load_research_runs()
    if runs:
        st.subheader("Recent Research Runs")
        for run in runs[:5]:
            ts = run.get("started_at", "")[:16].replace("T", " ")
            status = run.get("status", "unknown")
            found = run.get("total_candidates_found", 0)
            scored = run.get("total_scored", 0)
            avg = run.get("avg_score", 0)
            icon = "✅" if status == "completed" else ("🔄" if status == "running" else "❌")
            st.markdown(
                f"{icon} **{ts}** — {run.get('run_type', 'manual')} | "
                f"Found: {found} | Scored: {scored} | Avg: {avg or '—'} | "
                f"Status: {status}"
            )
        st.divider()

    # Research config
    settings = load_settings()
    research_config = settings.get("research_config", {})
    default_industries = research_config.get(
        "default_industries",
        [
            "Insurance Agencies", "Immigration Law", "HVAC", "Plumbing",
            "Electrical Contractors", "Pest Control", "Pool Service",
            "Solar Installation", "Roofing", "Locksmith",
            "Water Damage Restoration", "Bail Bonds", "Dental",
            "Veterinary", "Property Management", "Auto Repair",
        ],
    )
    default_cities = research_config.get(
        "default_cities",
        [
            "Phoenix", "Scottsdale", "Tempe", "Mesa", "Chandler", "Gilbert",
            "Glendale", "Peoria", "Surprise", "Avondale", "Goodyear",
            "Buckeye", "Queen Creek", "Apache Junction", "Maricopa", "Tolleson",
        ],
    )

    st.subheader("Configure Research Run")
    st.caption(
        "Industries and cities below come from your Settings page. "
        "All are pre-selected — uncheck any you want to skip for this run."
    )
    col1, col2 = st.columns(2)
    with col1:
        industries = st.multiselect(
            "Industries to search",
            default_industries,
            default=default_industries,
        )
    with col2:
        cities = st.multiselect(
            "Cities to search",
            default_cities,
            default=default_cities,
        )

    max_candidates = st.slider("Max candidates to score", 10, 200, 50, 10)
    run_type = st.radio("Run type", ["manual", "weekly", "daily"], horizontal=True)

    # Show the candidate budget estimate so user understands cost
    combos = len(industries) * len(cities)
    if combos > 0:
        st.caption(
            f"📊 {len(industries)} industries × {len(cities)} cities = {combos} search combinations. "
            f"Each combo pulls up to 10 places (capped at {max_candidates} total) and uses ~1 Apify credit."
        )

    st.divider()

    # Run research
    col_run, col_info = st.columns([1, 3])
    run_button = col_run.button("Run Deep Research", type="primary")
    col_info.caption(
        "This will search for businesses via configured data sources, "
        "then use Claude AI to score each candidate. Typical run: 2-5 minutes."
    )

    if run_button:
        _execute_research(industries, cities, max_candidates, run_type)

    # Manual add
    st.divider()
    st.subheader("Add Business Manually")
    with st.form("manual_add"):
        m_col1, m_col2, m_col3 = st.columns(3)
        m_name = m_col1.text_input("Business name")
        m_industry = m_col2.text_input("Industry")
        m_city = m_col3.text_input("City", value="Phoenix")
        m_col4, m_col5, m_col6 = st.columns(3)
        m_website = m_col4.text_input("Website")
        m_phone = m_col5.text_input("Phone")
        m_reviews = m_col6.text_input("Google reviews")

        if st.form_submit_button("Add Business"):
            if m_name:
                sb().table("businesses").insert({
                    "name": m_name,
                    "industry": m_industry or None,
                    "city": m_city or None,
                    "website": m_website or None,
                    "phone": m_phone or None,
                    "google_reviews": m_reviews or None,
                    "status": "New",
                }).execute()
                st.success(f"Added: {m_name}")
                st.rerun()
            else:
                st.error("Business name is required.")


def _execute_research(
    industries: list[str], cities: list[str], max_candidates: int, run_type: str
):
    """Run the deep research pipeline: collect data → score with Claude → save results.

    Scoring uses the Claude Agent SDK, which delegates to your locally-installed
    Claude Code. That means scoring draws from your Claude Max subscription rather
    than the metered Anthropic API. Claude Code must be installed and logged in on
    the machine running this app.
    """
    # Verify Claude Agent SDK is available before doing any work
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions  # noqa: F401
    except ImportError:
        st.error(
            "Claude Agent SDK is not installed. Run: `pip install claude-agent-sdk`\n\n"
            "You also need Claude Code installed and logged in: "
            "https://docs.claude.com/claude-code"
        )
        return

    apify_token = _get_secret("APIFY_API_TOKEN")

    # Create research run record
    run_resp = sb().table("research_runs").insert({
        "run_type": run_type,
        "status": "running",
        "industries_searched": industries,
        "cities_searched": cities,
    }).execute()
    run_id = run_resp.data[0]["id"]

    progress = st.progress(0, text="Starting research...")
    start_time = time.time()

    try:
        # Step 1: Collect candidate data
        progress.progress(10, text="Collecting candidate businesses...")
        candidates = _collect_candidates(industries, cities, max_candidates, apify_token)

        if not candidates:
            progress.progress(100, text="No candidates found. Try different search parameters.")
            sb().table("research_runs").update({
                "status": "completed",
                "total_candidates_found": 0,
                "completed_at": datetime.utcnow().isoformat(),
                "duration_seconds": int(time.time() - start_time),
            }).eq("id", run_id).execute()
            return

        progress.progress(30, text=f"Found {len(candidates)} candidates. Scoring with Claude (via Claude Code)...")

        # Step 2: Score with Claude (via Claude Agent SDK — uses your Claude Max subscription)
        weights = get_scoring_weights()
        feedback = get_feedback_history()
        scored = _score_candidates_with_claude(candidates, weights, feedback, progress)

        progress.progress(80, text=f"Scored {len(scored)} businesses. Saving to database...")

        # Step 3: Save results
        existing_names = set()
        existing_resp = sb().table("businesses").select("name").execute()
        if existing_resp.data:
            existing_names = {r["name"].lower() for r in existing_resp.data}

        # Whitelist of columns that exist on the businesses table. Anything
        # else on the scored dict (e.g., enrichment artifacts) gets dropped
        # to avoid Supabase "column does not exist" errors.
        allowed_cols = {
            "name", "industry", "city", "state", "website", "phone", "email",
            "google_reviews", "yelp_url", "google_maps_url",
            "score_call_volume", "score_missed_call_pain", "score_bilingual",
            "score_tech_readiness", "score_ease_of_closing", "score_urgency",
            "overall_score", "score_explanation", "key_evidence",
            "suggested_call_script", "status", "not_interested_reason",
            "last_research_run_id", "research_data", "data_source", "archived",
            "evidence_call_volume", "evidence_missed_call_pain",
            "evidence_bilingual", "evidence_tech_readiness",
            "evidence_ease_of_closing", "evidence_urgency",
            "website_signals", "review_signals", "review_count",
            "enrichment_completed_at",
        }

        new_count = 0
        for biz in scored:
            if biz["name"].lower() in existing_names:
                continue
            biz["last_research_run_id"] = run_id
            biz["status"] = "Research Done"
            row = {k: v for k, v in biz.items() if k in allowed_cols}
            sb().table("businesses").insert(row).execute()
            new_count += 1

        # Step 4: Update run record
        scores = [float(b.get("overall_score", 0)) for b in scored]
        duration = int(time.time() - start_time)
        sb().table("research_runs").update({
            "status": "completed",
            "total_candidates_found": len(candidates),
            "total_scored": len(scored),
            "top_score": max(scores) if scores else None,
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
            "completed_at": datetime.utcnow().isoformat(),
            "duration_seconds": duration,
        }).eq("id", run_id).execute()

        progress.progress(100, text="Research complete!")
        st.success(
            f"Research complete! Found {len(candidates)} candidates, "
            f"scored {len(scored)}, added {new_count} new businesses. "
            f"({duration}s)"
        )
        st.balloons()

    except Exception as e:
        sb().table("research_runs").update({
            "status": "failed",
            "error_message": str(e),
            "completed_at": datetime.utcnow().isoformat(),
            "duration_seconds": int(time.time() - start_time),
        }).eq("id", run_id).execute()
        st.error(f"Research failed: {e}")
        raise


# Maps each industry name from research_config to the Google Maps search
# keyword that actually returns the right businesses. Without this, generic
# names like "Medical" or "Legal" pull in random clinics and large law firms
# that aren't a fit for Ana ($20K–$50K SMB consultative sale).
INDUSTRY_QUERY_MAP = {
    "Insurance Agencies": "insurance agency",
    "Immigration Law": "immigration lawyer",
    "HVAC": "HVAC contractor",
    "Plumbing": "plumbing contractor",
    "Electrical Contractors": "electrical contractor",
    "Pest Control": "pest control service",
    "Pool Service": "pool cleaning service",
    "Solar Installation": "solar installation company",
    "Roofing": "roofing contractor",
    "Locksmith": "locksmith",
    "Water Damage Restoration": "water damage restoration",
    "Bail Bonds": "bail bonds agent",
    "Dental": "dentist",
    "Veterinary": "veterinarian",
    "Property Management": "property management company",
    "Auto Repair": "auto repair shop",
    # Legacy fallbacks (kept so old data still resolves)
    "Medical": "medical clinic",
    "Legal": "law firm",
}


def _search_query_for(industry: str, city: str) -> str:
    """Build a Google Maps search query optimized for the target industry."""
    keyword = INDUSTRY_QUERY_MAP.get(industry, industry.lower())
    return f"{keyword} in {city}, AZ"


def _passes_prefilter(item: dict, config: dict) -> tuple[bool, str]:
    """Apply pre-Claude filters to drop obvious bad-fit candidates.

    Returns (passed, rejection_reason). Saves Apify+Claude credits on
    candidates that have no chance of being a fit.
    """
    review_count = item.get("reviewsCount") or item.get("reviewsTotalCount") or 0
    website = (item.get("website") or "").strip()
    phone = (item.get("phone") or "").strip()

    min_reviews = int(config.get("min_reviews", 20))
    max_reviews = int(config.get("max_reviews", 5000))
    require_website = config.get("require_website", True)
    require_phone = config.get("require_phone", True)

    if review_count < min_reviews:
        return False, f"too few reviews ({review_count} < {min_reviews})"
    if review_count > max_reviews:
        return False, f"too big ({review_count} > {max_reviews} reviews — likely enterprise)"
    if require_website and not website:
        return False, "no website (can't enrich or build credibility)"
    if require_phone and not phone:
        return False, "no phone number (defeats the purpose of Ana)"

    return True, ""


def _collect_candidates(
    industries: list[str], cities: list[str], max_candidates: int, apify_token: str
) -> list[dict]:
    """
    Collect candidate businesses from data sources.
    Uses Apify Google Maps Scraper if token is available, otherwise generates
    search-ready candidate stubs for manual enrichment or Claude web search.
    """
    candidates: list[dict] = []
    rejected: list[str] = []  # reasons, for transparency on the UI

    # Load filter knobs from research_config
    config = load_settings().get("research_config", {}) or {}

    if apify_token:
        try:
            from apify_client import ApifyClient

            client = ApifyClient(apify_token)

            for industry in industries:
                for city in cities:
                    if len(candidates) >= max_candidates:
                        break
                    query = _search_query_for(industry, city)
                    run_input = {
                        "searchStringsArray": [query],
                        "maxCrawledPlacesPerSearch": min(
                            10, max_candidates - len(candidates)
                        ),
                        "language": "en",
                        # Pull the latest 30 reviews per business so we can
                        # mine them for missed-call complaints, Spanish
                        # usage, and review velocity. This is what gives
                        # the scoring real evidence instead of inference.
                        "maxReviews": 30,
                    }
                    run = client.actor("drobnikj/crawler-google-places").call(
                        run_input=run_input
                    )
                    dataset = client.dataset(run.default_dataset_id)
                    for item in dataset.iterate_items():
                        # Pre-filter to drop obvious bad-fit candidates BEFORE
                        # we spend website-fetch + Claude tokens on them.
                        passed, reason = _passes_prefilter(item, config)
                        if not passed:
                            rejected.append(
                                f"{item.get('title', '(unnamed)')}: {reason}"
                            )
                            continue

                        # Capture real review count + rating separately
                        review_count = (
                            item.get("reviewsCount")
                            or item.get("reviewsTotalCount")
                            or 0
                        )
                        candidates.append({
                            "name": item.get("title", ""),
                            "industry": industry,
                            "city": item.get("city", city),
                            "website": item.get("website", ""),
                            "phone": item.get("phone", ""),
                            "google_reviews": (
                                f"{review_count} reviews"
                                f" · {item.get('totalScore', '?')}★"
                            ),
                            "google_maps_url": item.get("url", ""),
                            "research_data": json.dumps(item),
                            "data_source": "apify_google_maps",
                        })
                        if len(candidates) >= max_candidates:
                            break
        except ImportError:
            st.warning(
                "apify-client not installed. Install with: pip install apify-client. "
                "Falling back to Claude-only research."
            )
            candidates = _generate_search_stubs(industries, cities, max_candidates)
        except Exception as e:
            st.warning(f"Apify error: {e}. Falling back to Claude-only research.")
            candidates = _generate_search_stubs(industries, cities, max_candidates)
    else:
        st.info(
            "No APIFY_API_TOKEN configured. Using Claude AI to generate research candidates. "
            "For better results, add an Apify token in Settings."
        )
        candidates = _generate_search_stubs(industries, cities, max_candidates)

    # Show pre-filter rejections so the user understands why a search returned
    # fewer candidates than expected (e.g., too few reviews, no website).
    if rejected:
        with st.expander(f"ℹ️ {len(rejected)} candidates filtered out before scoring"):
            for r in rejected[:50]:
                st.markdown(f"- {r}")

    # Enrichment pass: fetch each candidate's website + parse review patterns.
    # This is what makes the scoring evidence-based instead of inferred.
    try:
        from enrichment import enrich_candidate
        for i, c in enumerate(candidates):
            enrich_candidate(c)
    except ImportError:
        st.warning(
            "Enrichment module not available. Scores will be less precise. "
            "Run: pip install beautifulsoup4 requests"
        )
    except Exception as e:
        st.warning(f"Enrichment partial failure (continuing): {e}")

    return candidates


def _generate_search_stubs(
    industries: list[str], cities: list[str], max_candidates: int
) -> list[dict]:
    """Generate search query stubs for Claude to research and score."""
    stubs = []
    for industry in industries:
        for city in cities:
            stubs.append({
                "name": f"[Research needed: {industry} in {city}]",
                "industry": industry,
                "city": city,
                "data_source": "claude_research",
                "search_query": f"Best {industry} companies in {city} AZ with high call volume",
            })
            if len(stubs) >= max_candidates:
                return stubs
    return stubs


SCORING_SYSTEM_PROMPT = """You are an expert business analyst for Itxaz, a company that sells Ana Receptionist — an AI-powered voice receptionist for SMBs. Your job is to score prospect businesses for Ana Receptionist fit using REAL observable data, not inference.

Ana Receptionist answers phone calls 24/7, books appointments, speaks English and Spanish, and ensures businesses never miss a customer call. The ideal customer has high inbound call volume, loses revenue from missed calls, serves bilingual communities, is tech-ready, has accessible decision-makers, and faces urgent pain.

## CRITICAL RULE: EVIDENCE-BASED SCORING

For each business you will receive a fact sheet of observable signals scraped from Google Maps reviews and the business's website. You MUST ground each score in those signals. If a signal is missing or the website couldn't be fetched, lower the score AND explicitly say "data unavailable" in the evidence field — do NOT invent.

## SCORING RUBRIC (1-10 scale)

**1. Call Volume** — proxy via the data we have
  - Score from: Google review count (heavy proxy for customer volume), industry baseline (HVAC/plumbing/dental/law = high; retail = low), multiple locations indicator
  - 9-10: 500+ Google reviews AND high-call industry
  - 7-8: 200-500 reviews in a high-call industry, OR 500+ in moderate-call industry
  - 5-6: 50-200 reviews
  - 1-4: <50 reviews or low-call industry
  - Evidence MUST cite the actual review count provided

**2. Missed Call Pain** — direct evidence from review mining + industry economics
  - Score primarily from `missed_call_complaint_count` in the fact sheet (reviews mentioning "couldn't reach", "no answer", "voicemail", etc.)
  - "High-pain industries" (each missed call = significant lost revenue): HVAC, Plumbing, Electrical, Roofing, Restoration, Water Damage, Insurance, Solar, Legal/Law, Bail Bonds, Locksmith, Towing, Funeral Homes
  - 9-10: 3+ documented missed-call complaints in reviews, OR (500+ reviews AND high-pain industry — the volume × industry pattern makes missed calls a near certainty)
  - 7-8: 1-2 missed-call complaints, OR (200+ reviews AND high-pain industry), OR very high-volume after-hours business
  - 5-6: No complaints found but high-pain industry, OR moderate volume (50-200 reviews) in any service industry
  - 1-4: No complaints AND low-stakes industry (per-call value is small)
  - Evidence MUST quote actual complaints when present, or say "no complaints found in {N} reviews sampled; scoring from {volume} + {industry} pattern"

**3. Bilingual Opportunity** — direct evidence from website + reviews + memberships
  - Score from: `has_spanish_version`, `spanish_review_count`, `hispanic_chamber_member` (Phase 7 — STRONG signal), Phoenix demographics (~43% Hispanic) as baseline
  - 9-10: Hispanic Chamber member, OR (Spanish website version AND multiple Spanish reviews)
  - 7-8: One strong signal (Hispanic Chamber, OR Spanish site, OR 3+ Spanish reviews)
  - 5-6: No direct Spanish signals but Phoenix service industry baseline (they likely serve some Spanish-speaking customers but haven't built explicit infrastructure)
  - 1-4: Low-demand industry for Spanish AND no signals
  - Evidence MUST cite the specific signals (e.g., "Hispanic Chamber member — direct membership badge on site" or "5 Spanish reviews in sample of 30, website has /es/ page")

**4. Tech Readiness** — direct evidence from website scraping
  - Score from: `has_https`, `has_mobile_viewport`, `has_online_booking`, `has_chat_widget`, `has_modern_framework`, `has_spanish_version`, `copyright_year` (recent = active site)
  - The bar here is "can they integrate Ana into their workflow?" — NOT "are they a tech company." A clean modern website with HTTPS + mobile + 1 other signal already means they're capable of adopting a SaaS phone tool.
  - 9-10: 5+ signals present (truly tech-forward business)
  - 7-8: 3-4 signals present (clearly modern + capable)
  - 5-6: 2 signals present (minimum viable tech literacy — they have a site that works)
  - 3-4: Only 1 signal (very basic)
  - 1-2: Site couldn't be fetched (no website = can't integrate anyway)
  - Evidence MUST list which signals were present

**5. Ease of Closing** — proxy via observable business-structure signals + memberships
  - Score from: `family_business_signal` on website, ownership clarity, true enterprise signals, `bbb_accredited`, `nfib_member`, `chamber_member`, `industry_associations` (Phase 7)
  - IMPORTANT: high review count alone does NOT mean enterprise. A single-location insurance agency or HVAC company with 1,000+ reviews has accumulated those over years of service — it's still owner-operated and closeable. Only treat as enterprise if you see ACTUAL enterprise signals: "12 locations across AZ", "Fortune 500", "subsidiary of", explicit corporate HQ language, parent company name, or franchise structure.
  - Association memberships strongly signal "real, mature, accessible SMB owner" — boost the score when present.
  - 9-10: Strong family/owner signal (e.g., "Family-owned since 1985") AND association membership (BBB / NFIB / Chamber / industry-specific), AND no enterprise signals
  - 7-8: ANY of: family signal, NFIB member, BBB accredited, multiple association memberships, OR clearly local/independent SMB
  - 5-6: No clear ownership signal but no enterprise signals either — assume SMB by default if industry is service-based
  - 3-4: Multi-location chain (3-10 locations) OR clear franchise
  - 1-2: True enterprise (10+ locations, corporate HQ, subsidiary, etc.) OR no website to inspect
  - Evidence MUST cite the actual signal (e.g., "Family-owned + BBB accredited + NFIB member — classic owner-operated SMB")

**6. Urgency** — proxy via observable signals
  - Score from: industry seasonality (HVAC + Phoenix = extreme summer urgency), `has_careers_page` (hiring = growth pain), `review_velocity_signal` (accelerating = growing), `recent_review_count_90d`
  - 9-10: Industry in peak season AND visible growth signals (hiring, accelerating reviews)
  - 7-8: One strong signal (seasonal peak OR clear growth)
  - 5-6: Industry baseline, no specific signals
  - 1-4: No urgency signals at all
  - Evidence MUST cite specific signals

## OUTPUT FORMAT

Respond with a JSON array, one object per business. Required fields:

```
{
  "name": "...",
  "industry": "...",
  "city": "...",
  "website": "...",
  "phone": "...",
  "google_reviews": "...",  // copy the input value as-is
  "score_call_volume": 8,
  "evidence_call_volume": "342 Google reviews, HVAC industry in Phoenix.",
  "score_missed_call_pain": 9,
  "evidence_missed_call_pain": "3 reviews quote missed-call complaints: 'never returned my call', 'phone goes straight to voicemail'.",
  "score_bilingual": 7,
  "evidence_bilingual": "5 Spanish reviews out of 30 sampled. Website has no Spanish version. Phoenix HVAC industry baseline.",
  "score_tech_readiness": 6,
  "evidence_tech_readiness": "HTTPS yes, mobile viewport yes, online booking no, chat widget no, modern framework no.",
  "score_ease_of_closing": 8,
  "evidence_ease_of_closing": "Homepage states 'Family-owned and operated since 1985'. Single-location business.",
  "score_urgency": 9,
  "evidence_urgency": "HVAC in Phoenix during summer = peak urgency. Careers page present (hiring signal). Review velocity: accelerating (8 reviews in last 90 days).",
  "overall_score": 7.8,  // will be recomputed by the system, just give your best estimate
  "key_evidence": "2-3 sentence summary of why this is a fit",
  "score_explanation": "Brief overall reasoning",
  "suggested_call_script": "Personalized 2-3 sentence opener tailored to specific evidence above"
}
```

## ANTI-INFLATION RULES

- A score of 9-10 requires MULTIPLE concrete signals. Never give 9+ from inference alone.
- If `website_signals.fetched = false`, cap Tech Readiness at 3 and Ease of Closing at 5.
- If `total_review_count < 20`, cap Call Volume at 5.
- If `missed_call_complaint_count = 0` AND industry is NOT in the high-pain list (HVAC, Plumbing, Electrical, Roofing, Restoration, Water Damage, Insurance, Solar, Legal, Bail Bonds, Locksmith, Towing, Funeral Homes), cap Missed Call Pain at 6.
- Do NOT penalize Ease of Closing for high review count alone. Only penalize when explicit enterprise/multi-location signals are visible on the site.
- Be brutally honest. A 6 with real evidence is better than a 9 from imagination.
- But equally: don't artificially suppress a legitimately strong fit. If a business clearly checks the boxes for a criterion, score it high.

Return ONLY the JSON array. No preamble. Begin with `[` end with `]`.
"""


async def _query_claude_via_sdk(prompt: str, system_prompt: str) -> str:
    """Send a one-shot prompt to Claude Code via the Agent SDK and return the full text.

    Uses your Claude Max subscription (via locally-installed Claude Code) rather than
    the metered Anthropic API. No tools are enabled — this is pure inference.
    """
    from claude_agent_sdk import query, ClaudeAgentOptions

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=[],  # pure inference, no tool use
        permission_mode="bypassPermissions",
    )

    full_text = ""
    async for message in query(prompt=prompt, options=options):
        # AssistantMessage carries content blocks with text
        content = getattr(message, "content", None)
        if content:
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    full_text += text
    return full_text


def _score_candidates_with_claude(
    candidates: list[dict],
    weights: dict,
    feedback: list[dict],
    progress,
) -> list[dict]:
    """Send candidates to Claude (via Claude Agent SDK / Claude Code) for scoring."""
    import asyncio

    feedback_context = ""
    if feedback:
        feedback_lines = []
        for fb in feedback[:20]:
            biz_name = fb.get("businesses", {}).get("name", "Unknown") if fb.get("businesses") else "Unknown"
            feedback_lines.append(
                f"- {biz_name}: {fb.get('scoring_feedback', '')} "
                f"(actual interest: {fb.get('actual_interest_level', 'unknown')})"
            )
        feedback_context = (
            "\n\nPrior feedback from our sales team on scoring accuracy:\n"
            + "\n".join(feedback_lines)
            + "\n\nAdjust your scoring based on this feedback where applicable."
        )

    # Build human-readable evidence briefs for each candidate.
    # Falls back to raw JSON if the enrichment module isn't available
    # (e.g., legacy code path).
    try:
        from enrichment import signals_to_evidence_brief
        briefs = []
        for c in candidates:
            briefs.append(signals_to_evidence_brief(c))
        candidates_text = "\n\n---\n\n".join(briefs)
    except ImportError:
        candidates_text = json.dumps(candidates, indent=2, default=str)

    user_msg = (
        f"Score these candidate businesses for Ana Receptionist fit. "
        f"Apply these scoring weights: {json.dumps(weights)}\n\n"
        f"## CANDIDATES (real data — score from these signals only):\n\n"
        f"{candidates_text}"
        f"{feedback_context}\n\n"
        f"Return ONE JSON object per candidate above, in the same order. "
        f"Every score MUST cite the evidence field from the fact sheet. "
        f"Respond with ONLY a JSON array — no preamble, no markdown fences, no commentary. "
        f"Begin your response with `[` and end with `]`."
    )

    progress.progress(50, text="Claude is analyzing candidates (via Claude Code)...")

    try:
        response_text = asyncio.run(
            _query_claude_via_sdk(prompt=user_msg, system_prompt=SCORING_SYSTEM_PROMPT)
        )
    except Exception:
        try:
            response_text = _call_anthropic_api(
                user_prompt=user_msg,
                system_prompt=SCORING_SYSTEM_PROMPT,
                max_tokens=4096,
            )
        except Exception as e:
            st.error(f"Claude scoring error: {e}")
            return []

    progress.progress(70, text="Parsing results...")

    json_start = response_text.find("[")
    json_end = response_text.rfind("]") + 1
    if json_start == -1 or json_end == 0:
        st.error("Claude did not return valid JSON. Raw response shown below.")
        st.code(response_text)
        return []

    try:
        scored = json.loads(response_text[json_start:json_end])
    except json.JSONDecodeError as e:
        st.error(f"Could not parse Claude's JSON: {e}")
        st.code(response_text[json_start:json_end])
        return []

    # Merge Claude's scores + per-criterion evidence back onto the original
    # candidate records (so we keep enrichment signals + Apify URLs intact).
    by_name = {(c.get("name") or "").lower().strip(): c for c in candidates}
    merged: list[dict] = []
    for biz in scored:
        scores = {
            "score_call_volume": biz.get("score_call_volume", 5),
            "score_missed_call_pain": biz.get("score_missed_call_pain", 5),
            "score_bilingual": biz.get("score_bilingual", 5),
            "score_tech_readiness": biz.get("score_tech_readiness", 5),
            "score_ease_of_closing": biz.get("score_ease_of_closing", 5),
            "score_urgency": biz.get("score_urgency", 5),
        }
        biz["overall_score"] = compute_overall_score(scores, weights)
        biz.update(scores)

        # Pull enrichment signals back from the original candidate
        original = by_name.get((biz.get("name") or "").lower().strip())
        if original:
            biz["website_signals"] = original.get("website_signals")
            biz["review_signals"] = original.get("review_signals")
            biz["review_count"] = original.get("review_count")
            biz["research_data"] = original.get("research_data")
            biz["data_source"] = original.get("data_source")
            biz["google_maps_url"] = original.get("google_maps_url")
        biz["enrichment_completed_at"] = datetime.utcnow().isoformat()
        merged.append(biz)

    return merged


def _rescore_single_business(biz: dict) -> None:
    """Re-research one existing business with the enrichment pipeline.

    Used by the "Re-research this business" button on Lead Detail to
    upgrade hardcoded seed-data scores to evidence-backed ones.
    """
    import asyncio
    from enrichment import enrich_candidate, signals_to_evidence_brief

    # Build a candidate dict from the existing business record
    candidate = {
        "name": biz.get("name", ""),
        "industry": biz.get("industry", ""),
        "city": biz.get("city", ""),
        "website": biz.get("website", ""),
        "phone": biz.get("phone", ""),
        "google_maps_url": biz.get("google_maps_url", ""),
        "research_data": biz.get("research_data"),
        "data_source": biz.get("data_source") or "manual_rescore",
    }

    # If we have an Apify token AND no existing research_data, try to fetch
    # fresh Google Maps data first so review mining has something to work with.
    apify_token = _get_secret("APIFY_API_TOKEN")
    if apify_token and not candidate.get("research_data"):
        try:
            from apify_client import ApifyClient
            client = ApifyClient(apify_token)
            query = f"{candidate['name']} {candidate['city']} AZ"
            run = client.actor("drobnikj/crawler-google-places").call(
                run_input={
                    "searchStringsArray": [query],
                    "maxCrawledPlacesPerSearch": 1,
                    "language": "en",
                    "maxReviews": 30,
                }
            )
            for item in client.dataset(run.default_dataset_id).iterate_items():
                candidate["research_data"] = json.dumps(item)
                candidate["website"] = candidate["website"] or item.get("website", "")
                candidate["phone"] = candidate["phone"] or item.get("phone", "")
                candidate["google_maps_url"] = item.get("url", "")
                review_count = item.get("reviewsCount") or 0
                candidate["google_reviews"] = (
                    f"{review_count} reviews · {item.get('totalScore', '?')}★"
                )
                break
        except Exception as e:
            st.warning(f"Apify fetch skipped: {e}. Will score from website only.")

    # Enrich + score
    enrich_candidate(candidate)
    weights = get_scoring_weights()
    feedback = get_feedback_history()

    class _NoOpProgress:
        def progress(self, *a, **kw): pass

    scored = _score_candidates_with_claude([candidate], weights, feedback, _NoOpProgress())
    if not scored:
        raise RuntimeError("Claude returned no scores")

    s = scored[0]
    updates = {
        "score_call_volume": s.get("score_call_volume"),
        "score_missed_call_pain": s.get("score_missed_call_pain"),
        "score_bilingual": s.get("score_bilingual"),
        "score_tech_readiness": s.get("score_tech_readiness"),
        "score_ease_of_closing": s.get("score_ease_of_closing"),
        "score_urgency": s.get("score_urgency"),
        "overall_score": s.get("overall_score"),
        "key_evidence": s.get("key_evidence"),
        "score_explanation": s.get("score_explanation"),
        "suggested_call_script": s.get("suggested_call_script"),
        "evidence_call_volume": s.get("evidence_call_volume"),
        "evidence_missed_call_pain": s.get("evidence_missed_call_pain"),
        "evidence_bilingual": s.get("evidence_bilingual"),
        "evidence_tech_readiness": s.get("evidence_tech_readiness"),
        "evidence_ease_of_closing": s.get("evidence_ease_of_closing"),
        "evidence_urgency": s.get("evidence_urgency"),
        "website_signals": candidate.get("website_signals"),
        "review_signals": candidate.get("review_signals"),
        "review_count": candidate.get("review_count"),
        "research_data": candidate.get("research_data"),
        "data_source": candidate.get("data_source"),
        "google_maps_url": candidate.get("google_maps_url") or biz.get("google_maps_url"),
        "website": candidate.get("website") or biz.get("website"),
        "phone": candidate.get("phone") or biz.get("phone"),
        "enrichment_completed_at": datetime.utcnow().isoformat(),
    }
    # Drop None values so we don't overwrite existing data with NULL
    updates = {k: v for k, v in updates.items() if v is not None}
    sb().table("businesses").update(updates).eq("id", biz["id"]).execute()


def _bulk_rescore_seed_data() -> None:
    """Loop through every unverified business and re-research it with the
    enrichment pipeline. Used from the Settings page."""
    rows = sb().table("businesses").select("*").is_("enrichment_completed_at", "null").eq("archived", False).execute()
    targets = rows.data or []
    if not targets:
        st.info("No unverified businesses to re-research.")
        return

    progress = st.progress(0, text=f"Starting bulk re-research of {len(targets)} businesses...")
    succeeded = 0
    failed: list[str] = []

    for i, biz in enumerate(targets):
        progress.progress(
            int((i / len(targets)) * 100),
            text=f"[{i + 1}/{len(targets)}] {biz.get('name', '(unnamed)')}",
        )
        try:
            _rescore_single_business(biz)
            succeeded += 1
        except Exception as e:
            failed.append(f"{biz.get('name')}: {e}")

    progress.progress(100, text=f"Done. {succeeded}/{len(targets)} re-researched.")
    if succeeded:
        st.success(f"✅ Upgraded {succeeded} businesses to real-evidence scoring.")
    if failed:
        with st.expander(f"⚠️ {len(failed)} failures"):
            for f in failed:
                st.markdown(f"- {f}")


# ---------------------------------------------------------------------------
# PAGE: Settings
# ---------------------------------------------------------------------------
def page_settings():
    st.title("Settings")

    settings = load_settings()

    # Scoring weights
    st.subheader("Scoring Weights")
    st.caption("Adjust the relative importance of each scoring criterion. Default is 1.0 (equal weight).")

    weights = settings.get("scoring_weights", DEFAULT_WEIGHTS)

    col1, col2, col3 = st.columns(3)
    new_weights = {}
    weight_labels = [
        ("call_volume", "Call Volume"),
        ("missed_call_pain", "Missed Call Pain"),
        ("bilingual", "Bilingual Opportunity"),
        ("tech_readiness", "Tech Readiness"),
        ("ease_of_closing", "Ease of Closing"),
        ("urgency", "Urgency"),
    ]
    for i, (key, label) in enumerate(weight_labels):
        col = [col1, col2, col3][i % 3]
        new_weights[key] = col.slider(
            label, 0.0, 3.0, float(weights.get(key, 1.0)), 0.1, key=f"w_{key}"
        )

    if st.button("Save Weights"):
        save_setting("scoring_weights", new_weights)
        st.success("Scoring weights saved!")

    if st.button("Recalculate All Scores"):
        _recalculate_all_scores(new_weights)

    st.divider()

    # Bulk re-research of seed-data businesses
    st.subheader("Upgrade Seed Data to Real Evidence")
    st.caption(
        "Businesses that were loaded from seed data (hardcoded estimates) need to be "
        "re-researched with real signals from their website + Google reviews. "
        "Click below to upgrade them all in one batch."
    )

    # Count how many are unverified (no enrichment yet)
    try:
        unverified = sb().table("businesses").select("id", count="exact").is_("enrichment_completed_at", "null").eq("archived", False).execute()
        seed_count = unverified.count
    except Exception:
        seed_count = "unknown"

    st.markdown(f"**Businesses needing real-data scoring:** {seed_count}")

    if st.button(f"🔄 Re-research all unverified businesses ({seed_count})"):
        _bulk_rescore_seed_data()

    st.divider()

    # Research config
    st.subheader("Research Configuration")
    research_config = settings.get("research_config", {})

    industries_str = st.text_area(
        "Default industries (one per line)",
        value="\n".join(research_config.get("default_industries", [])),
        height=240,
    )
    cities_str = st.text_area(
        "Default cities (one per line)",
        value="\n".join(research_config.get("default_cities", [])),
        height=240,
    )
    max_per_run = st.number_input(
        "Max candidates per research run",
        value=research_config.get("max_candidates_per_run", 50),
        min_value=10,
        max_value=500,
    )
    frequency = st.selectbox(
        "Research frequency",
        ["weekly", "daily"],
        index=0 if research_config.get("research_frequency") == "weekly" else 1,
    )

    # Pre-filter knobs — drop obvious bad-fit candidates BEFORE we spend
    # Claude tokens scoring them. Saves Apify credits + improves list quality.
    st.markdown("**Pre-filter rules (drop bad candidates before scoring)**")
    filter_cols = st.columns(2)
    with filter_cols[0]:
        min_reviews = st.number_input(
            "Minimum Google reviews",
            value=int(research_config.get("min_reviews", 20)),
            min_value=0,
            max_value=10000,
            help="Drops brand-new businesses too small to be a fit.",
        )
        require_website = st.checkbox(
            "Require website",
            value=research_config.get("require_website", True),
            help="Without a website we can't enrich or check tech readiness.",
        )
    with filter_cols[1]:
        max_reviews = st.number_input(
            "Maximum Google reviews",
            value=int(research_config.get("max_reviews", 5000)),
            min_value=100,
            max_value=100000,
            help="Drops enterprise-sized businesses outside Ana's $20K-$50K sweet spot.",
        )
        require_phone = st.checkbox(
            "Require phone number",
            value=research_config.get("require_phone", True),
            help="No phone = Ana has nothing to answer.",
        )

    if st.button("Save Research Config"):
        new_config = {
            "default_industries": [i.strip() for i in industries_str.split("\n") if i.strip()],
            "default_cities": [c.strip() for c in cities_str.split("\n") if c.strip()],
            "max_candidates_per_run": max_per_run,
            "research_frequency": frequency,
            "min_reviews": int(min_reviews),
            "max_reviews": int(max_reviews),
            "require_website": bool(require_website),
            "require_phone": bool(require_phone),
        }
        save_setting("research_config", new_config)
        st.success("Research configuration saved!")

    st.divider()

    # Integrations status
    st.subheader("Integrations Status")
    apify_token = _get_secret("APIFY_API_TOKEN")
    supabase_url = _get_secret("SUPABASE_URL")

    # Check Claude Agent SDK install
    try:
        import claude_agent_sdk  # noqa: F401
        sdk_status = "✅ Installed"
    except ImportError:
        sdk_status = "❌ Not installed (run `pip install claude-agent-sdk`)"

    # Check Claude Code CLI availability
    import subprocess
    try:
        cc_result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        if cc_result.returncode == 0:
            cc_status = f"✅ Installed ({cc_result.stdout.strip()})"
        else:
            cc_status = "⚠️ Installed but errored — try `claude login`"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        cc_status = "❌ Not installed — install from https://docs.claude.com/claude-code"

    st.markdown(f"- **Claude Agent SDK:** {sdk_status}")
    st.markdown(f"- **Claude Code CLI:** {cc_status}")
    st.markdown(f"- **Apify API Token:** {'✅ Configured' if apify_token else '⚠️ Not configured (optional — Claude-only research mode)'}")
    st.markdown(f"- **Supabase:** {'✅ Connected' if supabase_url else '❌ Not connected'}")
    st.caption(
        "Scoring uses Claude Code via the Agent SDK, which draws from your Claude Max "
        "subscription. No Anthropic API key needed."
    )

    st.divider()

    # Feedback summary
    st.subheader("Scoring Feedback Summary")
    feedback = get_feedback_history()
    if feedback:
        st.caption(f"{len(feedback)} feedback entries from call notes")
        for fb in feedback[:10]:
            biz_name = fb.get("businesses", {}).get("name", "Unknown") if fb.get("businesses") else "Unknown"
            st.markdown(
                f"- **{biz_name}**: {fb.get('scoring_feedback', '—')} "
                f"(interest: {fb.get('actual_interest_level', '—')})"
            )
    else:
        st.caption("No scoring feedback yet. Add feedback when logging call notes.")


def _recalculate_all_scores(weights: dict):
    """Recalculate overall scores for all businesses using current weights."""
    df = load_businesses()
    if df.empty:
        st.info("No businesses to recalculate.")
        return

    count = 0
    bar = st.progress(0, text="Recalculating scores...")
    total = len(df)
    for i, (_, row) in enumerate(df.iterrows()):
        scores = {
            "score_call_volume": float(row.get("score_call_volume", 0)),
            "score_missed_call_pain": float(row.get("score_missed_call_pain", 0)),
            "score_bilingual": float(row.get("score_bilingual", 0)),
            "score_tech_readiness": float(row.get("score_tech_readiness", 0)),
            "score_ease_of_closing": float(row.get("score_ease_of_closing", 0)),
            "score_urgency": float(row.get("score_urgency", 0)),
        }
        new_overall = compute_overall_score(scores, weights)
        update_business(row["id"], {"overall_score": new_overall})
        count += 1
        bar.progress((i + 1) / total, text=f"Recalculating... {i + 1}/{total}")

    bar.progress(1.0, text="Done!")
    st.success(f"Recalculated scores for {count} businesses.")


# ===========================================================================
# SALES ENGINE — Module 2: Conversion Machinery
# ===========================================================================
# Synthesized from Connor Murray (Oracle), Teddy Frank (UserGems), Jason Bay
# (Outbound Squad), and Superhuman Prospecting (H2H). Tuned for high-ticket
# consultative sales ($20k-$50k Ana Receptionist deals).
# ===========================================================================

OUTCOME_OPTIONS = [
    ("demo_booked", "✅ Demo Booked", "Interested - Demo Booked"),
    ("callback_requested", "📞 Callback Requested", None),
    ("voicemail_left", "📭 Voicemail Left", "Voicemail Left"),
    ("gatekeeper_only", "🚪 Gatekeeper Only", None),
    ("no_answer", "📵 No Answer", None),
    ("not_interested", "❌ Not Interested", "Not Interested"),
    ("wrong_number", "❓ Wrong Number", None),
    ("do_not_contact", "🚫 Do Not Contact", "Do Not Contact"),
]

CALLER_OPTIONS = ["josue", "santiago"]


def load_objections(category: str | None = None) -> pd.DataFrame:
    """Load all active objections from the bible."""
    q = sb().table("objections").select("*").eq("archived", False)
    if category and category != "All":
        q = q.eq("category", category)
    resp = q.execute()
    if not resp.data:
        return pd.DataFrame()
    return pd.DataFrame(resp.data)


def get_todays_call_list(limit: int = 10) -> pd.DataFrame:
    """Smart curation for the Daily Cockpit — high-ticket consultative tuning.

    Mix:
      50% fresh high-score leads (Research Done / New)
      30% stale follow-ups (Call 1/2 Made — don't let them cool)
      20% demo confirmations needed (Interested - Demo Booked)
    """
    df = load_businesses()
    if df.empty:
        return df

    fresh = df[df["status"].isin(["Research Done", "New"])].sort_values("overall_score", ascending=False)
    stale = df[df["status"].isin(["Call 1 Made", "Call 2 Made"])].sort_values("overall_score", ascending=False)
    demo_confirm = df[df["status"] == "Interested - Demo Booked"].sort_values("overall_score", ascending=False)

    fresh_n = max(1, int(limit * 0.5))
    stale_n = max(0, int(limit * 0.3))
    demo_n = max(0, limit - fresh_n - stale_n)

    parts = [fresh.head(fresh_n), stale.head(stale_n), demo_confirm.head(demo_n)]
    result = pd.concat([p for p in parts if not p.empty]) if any(not p.empty for p in parts) else pd.DataFrame()

    # If under-budget, top up from any active leads
    if len(result) < limit:
        active = df[df["status"].isin(["Research Done", "New", "Call 1 Made", "Call 2 Made"])]
        if not result.empty:
            active = active[~active["id"].isin(result["id"])]
        extra = active.sort_values("overall_score", ascending=False).head(limit - len(result))
        result = pd.concat([result, extra]) if not result.empty else extra

    return result.head(limit).reset_index(drop=True)


def _build_script_prompt(business: dict, language: str, caller_name: str = "Josue") -> str:
    """Build the full system+user prompt for script generation."""
    if language == "es":
        lang_directive = (
            "Generate the script in warm professional Mexican Spanish (formal 'usted' form) "
            "suitable for Phoenix Hispanic SMB owners. Natural, conversational, not robotic."
        )
    else:
        lang_directive = (
            "Generate the script in warm professional American English. Natural, conversational, "
            "sounds like a human talking, not a brochure."
        )

    return f"""You are an elite cold-call coach trained in Connor Murray's Oracle 3-Part Value Statement framework.
Your job: write a 30-45 second personalized cold-call opener for a specific SMB lead being pitched Ana Receptionist (an AI voice receptionist with native Spanish, sold by Itxaz).

**Important:** The caller's name is **{caller_name}**. Use this exact name when the caller introduces themselves. Do NOT substitute, anglicize, or change it to anything else.

Required structure (3 short paragraphs separated by blank lines):

1. OPENING — Assumptive Formality
   Casual, warm greeting with downward inflection. The caller introduces themselves by name.
   Example template: "Hey [prospect-name-or-friendly-substitute], this is {caller_name} from Itxaz — how are you?"
   Moves fast, no permission-asking, no nervous filler.

2. VALUE STATEMENT — the core (30-45 seconds when spoken aloud)
   - Who you are (Itxaz, makers of Ana Receptionist)
   - Why specifically THEM (cite their industry + 1 specific pain or trigger from the evidence)
   - Outcome/transformation (specific business outcome — not features)
   - Reference Ricardo Diaz Insurance as proof if it fits naturally
   - What you want (a meeting next week)

3. CLOSE — Assumptive Next Step
   Specific calendar ask. Example: "How's Wednesday at 10 or Thursday at 2?"
   NEVER ask "do you have a minute?" — assume the meeting is happening.

Style requirements:
- Short sentences, easy to say out loud
- Conversational, NOT script-y
- Tie to a real Ana benefit: missed calls captured, after-hours coverage, bilingual support, appointments booked directly to calendar
- Maximum ~120 words total (45 seconds spoken)
- Pitching to a $20k-$50k buyer — sound like a peer, not a vendor
- The caller's name is {caller_name} — use it verbatim, never change it

{lang_directive}

Return ONLY the three paragraphs — no headers, no markdown bullets, no preamble.

---

Lead details:
- Business: {business.get('name')}
- Industry: {business.get('industry', 'Unknown')}
- City: {business.get('city', 'Phoenix')}
- Score: {business.get('overall_score', 'N/A')}/10
- Key fit evidence: {business.get('key_evidence', 'High-volume SMB, likely missing calls during peak hours')}
- Caller introducing themselves: {caller_name}

Write the personalized 3-Part Value Statement now."""


def generate_personalized_script(business: dict, language: str = "en", caller_name: str = "Josue") -> str:
    """Generate a personalized opener by shelling out to the local `claude` CLI.

    Uses your Claude Max subscription via Claude Code (not the Anthropic API).
    Simpler and more reliable than the Agent SDK for one-shot inference.
    """
    import subprocess
    import os
    import shutil

    prompt = _build_script_prompt(business, language, caller_name)

    # Resolve the full path to claude so subprocess doesn't depend on PATH
    claude_path = shutil.which("claude")
    if not claude_path:
        return _call_anthropic_api(user_prompt=prompt)

    # Build an explicit environment to ensure HOME and shell env are inherited correctly
    env = os.environ.copy()

    try:
        result = subprocess.run(
            [claude_path, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=os.path.expanduser("~"),  # run from HOME so claude finds its auth
        )
    except FileNotFoundError:
        return f"[Claude Code CLI not found at {claude_path}.]"
    except subprocess.TimeoutExpired:
        return "[Claude CLI timed out after 120 seconds.]"
    except Exception as e:
        return f"[Subprocess error: {type(e).__name__}: {e}]"

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0:
        # Be verbose — exit-1 with no stderr is the worst case
        diag = (
            f"[Claude CLI exit {result.returncode}]\n"
            f"BINARY: {claude_path}\n"
            f"HOME: {env.get('HOME', '(unset)')}\n"
            f"CWD: {os.path.expanduser('~')}\n"
            f"STDOUT ({len(stdout)} chars): {stdout[:500] if stdout else '(empty)'}\n"
            f"STDERR ({len(stderr)} chars): {stderr[:500] if stderr else '(empty)'}"
        )
        return diag

    if not stdout:
        return (
            f"[Claude CLI returned exit 0 but empty stdout. "
            f"STDERR: {stderr[:300] if stderr else '(empty)'}]"
        )
    return stdout


def start_call(business_id: str, caller: str, language: str, opener_used: str | None = None) -> str:
    """Open a new sales_calls row and return its id."""
    resp = sb().table("sales_calls").insert({
        "business_id": business_id,
        "caller": caller,
        "language": language,
        "opener_used": opener_used,
    }).execute()
    return resp.data[0]["id"]


def end_call(call_id: str, **fields):
    """Close out the call by writing outcome fields + call_ended_at."""
    fields["call_ended_at"] = datetime.utcnow().isoformat()
    sb().table("sales_calls").update(fields).eq("id", call_id).execute()


def record_objection_encounter(call_id: str, objection_id: str, was_handled: bool, notes: str | None = None):
    """Log when an objection came up + increment its usage counters."""
    sb().table("objection_encounters").insert({
        "call_id": call_id,
        "objection_id": objection_id,
        "was_handled": was_handled,
        "notes": notes,
    }).execute()

    cur = sb().table("objections").select("times_used, times_succeeded").eq("id", objection_id).execute()
    if cur.data:
        row = cur.data[0]
        updates = {"times_used": (row.get("times_used") or 0) + 1}
        if was_handled:
            updates["times_succeeded"] = (row.get("times_succeeded") or 0) + 1
        sb().table("objections").update(updates).eq("id", objection_id).execute()


def _localize(row: dict, field_base: str, language: str) -> str:
    """Return Spanish version of a bilingual field if available + requested, else English."""
    if language == "es":
        es_val = row.get(f"{field_base}_es")
        if es_val:
            return es_val
    return row.get(f"{field_base}_en") or ""


# ---------------------------------------------------------------------------
# PAGE: Daily Call Cockpit
# ---------------------------------------------------------------------------
def page_call_cockpit():
    st.title("🎯 Daily Call Cockpit")
    st.caption("Top calls for today — auto-curated from fresh leads, stale follow-ups, and demo confirmations.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        caller = st.selectbox("Who's calling?", CALLER_OPTIONS, format_func=lambda x: x.capitalize())
    with col2:
        language = st.radio(
            "Language", ["en", "es"],
            format_func=lambda x: "🇺🇸 English" if x == "en" else "🇲🇽 Español",
            horizontal=True,
        )
    with col3:
        list_size = st.selectbox("List size", [5, 10, 15, 20], index=1,
                                  help="High-ticket = quality over volume. 10/day is the elite range.")

    st.divider()

    df = get_todays_call_list(limit=list_size)
    if df.empty:
        st.info("No active leads to call. Run Deep Research to find more candidates.")
        return

    st.markdown(f"### Your Top {len(df)} Calls — {datetime.now().strftime('%A, %B %d')}")

    # Today's stats
    today_iso = datetime.utcnow().strftime("%Y-%m-%d")
    today_resp = (sb().table("sales_calls").select("id, outcome, connected")
                  .gte("call_started_at", today_iso).eq("caller", caller).execute())
    today_calls = today_resp.data or []

    cols = st.columns(4)
    cols[0].metric("Calls today", len(today_calls))
    cols[1].metric("Connected", sum(1 for c in today_calls if c.get("connected")))
    cols[2].metric("Demos booked", sum(1 for c in today_calls if c.get("outcome") == "demo_booked"))
    if today_calls:
        connect_rate = sum(1 for c in today_calls if c.get("connected")) / len(today_calls) * 100
        cols[3].metric("Connect rate", f"{connect_rate:.0f}%",
                       help="Elite benchmark: 20-30%+")
    else:
        cols[3].metric("Connect rate", "—")

    st.divider()

    for idx, row in df.iterrows():
        with st.container(border=True):
            top1, top2, top3 = st.columns([3, 1, 1])
            with top1:
                st.markdown(f"### {idx + 1}. {row['name']}")
                st.caption(f"{row.get('industry', 'Unknown')} · {row.get('city', '')} · Score: **{row['overall_score']:.1f}/10**")
            with top2:
                st.markdown(f"**Status:** {row['status']}")
            with top3:
                if st.button("📞 Start Call", key=f"start_{row['id']}", type="primary", use_container_width=True):
                    call_id = start_call(row["id"], caller, language)
                    st.session_state["active_call_id"] = call_id
                    st.session_state["active_call_business_id"] = row["id"]
                    st.session_state["active_call_business_name"] = row["name"]
                    st.session_state["active_call_language"] = language
                    st.session_state["active_call_caller"] = caller
                    st.session_state["page"] = "Live Call"
                    st.rerun()

            if row.get("key_evidence"):
                st.markdown(f"**🎯 Why they're a fit:** {row['key_evidence']}")

            with st.expander("🎬 Personalized opener (Connor Murray 3-Part Framework)"):
                # Cache key includes caller so switching dropdown regenerates with right name
                script_key = f"script_{row['id']}_{language}_{caller}"
                if script_key not in st.session_state:
                    if st.button("✨ Generate Script", key=f"gen_{row['id']}"):
                        with st.spinner(f"Claude is writing your opener (as {caller.capitalize()})..."):
                            st.session_state[script_key] = generate_personalized_script(
                                row.to_dict(), language, caller.capitalize()
                            )
                            st.rerun()
                    else:
                        st.caption(f"Click 'Generate Script' to get a Claude-personalized opener (introduced as {caller.capitalize()}).")
                else:
                    st.markdown(st.session_state[script_key])
                    if st.button("🔄 Regenerate", key=f"regen_{row['id']}"):
                        del st.session_state[script_key]
                        st.rerun()


# ---------------------------------------------------------------------------
# PAGE: Live Call
# ---------------------------------------------------------------------------
def page_live_call():
    call_id = st.session_state.get("active_call_id")
    if not call_id:
        st.warning("No active call. Go to Daily Call Cockpit and click 'Start Call' on a lead.")
        if st.button("→ Daily Call Cockpit"):
            st.session_state["page"] = "Daily Cockpit"
            st.rerun()
        return

    business_id = st.session_state.get("active_call_business_id")
    business_name = st.session_state.get("active_call_business_name", "Unknown")
    language = st.session_state.get("active_call_language", "en")
    caller = st.session_state.get("active_call_caller", "josue")

    # Header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.title(f"📞 Live: {business_name}")
        st.caption(
            f"Caller: {caller.capitalize()} · "
            f"Language: {'🇺🇸 English' if language == 'en' else '🇲🇽 Español'} · "
            f"Call ID: {call_id[:8]}"
        )
    with col2:
        call_resp = sb().table("sales_calls").select("call_started_at").eq("id", call_id).execute()
        if call_resp.data:
            try:
                started = call_resp.data[0]["call_started_at"]
                started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                duration = int((datetime.now(started_dt.tzinfo) - started_dt).total_seconds())
                mins, secs = divmod(duration, 60)
                st.metric("⏱ Duration", f"{mins:02d}:{secs:02d}")
            except Exception:
                st.metric("⏱ Duration", "—")
    with col3:
        if st.button("← Cockpit", use_container_width=True):
            st.session_state["page"] = "Daily Cockpit"
            st.rerun()

    st.divider()

    tabs = st.tabs(["🎬 Opener", "🛡️ Objections", "❓ Discovery", "📝 Notes", "💰 ROI", "✅ Close Out"])

    # === Opener tab ===
    with tabs[0]:
        # Match Cockpit cache key so a script generated there shows up here automatically
        script_key = f"script_{business_id}_{language}_{caller}"
        if script_key in st.session_state:
            st.markdown(st.session_state[script_key])
        else:
            st.caption(f"No pre-generated script. Generate now (introduced as {caller.capitalize()}):")
            if st.button("✨ Generate Script", type="primary"):
                with st.spinner(f"Generating as {caller.capitalize()}..."):
                    biz_resp = sb().table("businesses").select("*").eq("id", business_id).execute()
                    if biz_resp.data:
                        st.session_state[script_key] = generate_personalized_script(
                            biz_resp.data[0], language, caller.capitalize()
                        )
                        st.rerun()

    # === Objections tab ===
    with tabs[1]:
        st.markdown("**Click an objection to open its handler:**")
        objections = load_objections()
        if objections.empty:
            st.info("No objections in the bible.")
        else:
            for _, obj in objections.iterrows():
                obj_dict = obj.to_dict()
                obj_text = _localize(obj_dict, "objection_text", language)
                with st.expander(f"💬 [{obj.get('category', 'misc').upper()}] {obj_text}"):
                    st.markdown(f"**🤝 Acknowledge:** {_localize(obj_dict, 'acknowledge', language)}")
                    st.markdown(f"**🔄 Reframe:** {_localize(obj_dict, 'reframe', language)}")
                    st.markdown(f"**🎯 Reclose:** {_localize(obj_dict, 'reclose', language)}")
                    proof = _localize(obj_dict, "social_proof", language)
                    if proof:
                        st.info(f"💡 Social proof: {proof}")

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("✅ Handled it", key=f"obj_yes_{obj['id']}_{call_id}", use_container_width=True):
                            record_objection_encounter(call_id, obj["id"], True)
                            st.toast(f"Logged: handled")
                    with btn_col2:
                        if st.button("❌ Didn't work", key=f"obj_no_{obj['id']}_{call_id}", use_container_width=True):
                            record_objection_encounter(call_id, obj["id"], False)
                            st.toast(f"Logged: did not work")

    # === Discovery tab ===
    with tabs[2]:
        st.markdown("**Discovery Questions** — earn the right with 8 questions before pitching:")
        if language == "es":
            st.markdown("""
1. **Volumen:** ¿Más o menos cuántas llamadas reciben al día?
2. **Manejo actual:** ¿Cómo manejan las llamadas entrantes cuando todos están ocupados?
3. **Pérdida:** ¿Qué pasa cuando una llamada no se contesta — buzón, ocupado, o el cliente cuelga?
4. **Costo:** Si capturáramos las llamadas que están perdiendo hoy, ¿cuánto valdría eso para su negocio?
5. **Bilingüe:** ¿Qué porcentaje de sus clientes prefieren hablar en español?
6. **Decisión:** ¿Quién más estaría involucrado en la decisión si avanzamos?
7. **Urgencia:** ¿Hay algo específico pasando ahora — temporada alta, crecimiento, falta de personal — que haga esto más urgente?
8. **Timeline:** ¿Qué tan rápido le gustaría tener esto operando?
            """)
        else:
            st.markdown("""
1. **Volume:** Roughly how many calls do you get a day?
2. **Current handling:** How do you handle inbound calls when everyone's busy?
3. **Loss:** What happens when a call isn't answered — voicemail, busy, customer hangs up?
4. **Opportunity cost:** If we captured the calls you're losing today, what would that be worth?
5. **Bilingual:** What percentage of your customers prefer Spanish?
6. **Decision:** Who else would be involved if you decide to move forward?
7. **Urgency:** Is there anything happening now — busy season, growth, staff shortage — that makes this more urgent?
8. **Timeline:** How fast would you want to have this running?
            """)
        st.caption("💡 Teddy Frank's edge: hyper-relevant questions tied to their actual pain. Listen 2x more than you talk.")

    # === Notes tab ===
    with tabs[3]:
        existing = ""
        notes_resp = sb().table("sales_calls").select("notes").eq("id", call_id).execute()
        if notes_resp.data and notes_resp.data[0].get("notes"):
            existing = notes_resp.data[0]["notes"]

        new_notes = st.text_area("Live notes (saves when you click Save below)", value=existing, height=300, key=f"notes_{call_id}")
        if st.button("💾 Save Notes"):
            sb().table("sales_calls").update({"notes": new_notes}).eq("id", call_id).execute()
            st.success("Saved ✓")

    # === ROI Calculator tab ===
    # Sales closing tool — feeds the prospect's own numbers back to them so
    # the cost of Ana ($24K/yr ongoing) becomes obviously trivial vs. their
    # missed-call losses.
    with tabs[4]:
        st.markdown("**Live ROI Calculator — fill in their numbers during/after Discovery, then close with the math.**")
        st.caption("All defaults are Phoenix Valley industry averages — edit anything based on what they tell you on the call.")

        # Industry presets — average revenue per converted call
        INDUSTRY_PRESETS = {
            "Insurance": 1500,
            "HVAC": 500,
            "Plumbing": 400,
            "Electrical": 450,
            "Solar": 10000,
            "Roofing": 8000,
            "Water Damage / Restoration": 5000,
            "Dental": 3000,
            "Legal / Immigration": 3500,
            "Veterinary": 250,
            "Pest Control": 350,
            "Pool Service": 200,
            "Locksmith": 250,
            "Bail Bonds": 800,
            "Auto Repair": 600,
            "Property Management": 1200,
            "Other / Custom": 500,
        }

        # Try to default to the business's industry if it matches
        biz_resp = sb().table("businesses").select("industry").eq("id", business_id).execute()
        default_industry = "Other / Custom"
        if biz_resp.data:
            biz_industry = (biz_resp.data[0].get("industry") or "").lower()
            for k in INDUSTRY_PRESETS.keys():
                if k.lower().split(" ")[0] in biz_industry:
                    default_industry = k
                    break

        roi_c1, roi_c2 = st.columns(2)
        with roi_c1:
            st.markdown("**Their current situation:**")
            monthly_calls = st.number_input(
                "Monthly inbound calls",
                min_value=0, max_value=10000, value=500, step=50,
                help="Ask: 'roughly how many calls do you get a month?'"
            )
            missed_pct = st.slider(
                "% of calls missed (voicemail/busy/after-hours)",
                min_value=0, max_value=80, value=25,
                help="Industry avg is 20-35% for SMBs without 24/7 coverage. Ana captures these."
            )
            preset = st.selectbox(
                "Industry preset (avg revenue per converted call)",
                list(INDUSTRY_PRESETS.keys()),
                index=list(INDUSTRY_PRESETS.keys()).index(default_industry),
            )
            avg_value = st.number_input(
                "Avg revenue per converted call ($)",
                min_value=0.0, value=float(INDUSTRY_PRESETS[preset]), step=50.0,
                help="What's the typical revenue when a missed call WOULD have converted?"
            )
            conv_rate = st.slider(
                "% of those missed calls that would have converted",
                min_value=0, max_value=100, value=30,
                help="Conservative — even if only 30% would've converted, the math still works"
            )

        with roi_c2:
            st.markdown("**Current receptionist setup:**")
            current_setup = st.selectbox(
                "What do they have today?",
                ["No receptionist (calls go to whoever's available)",
                 "Part-time receptionist (40 hours/week)",
                 "Full-time receptionist (40 hours/week)",
                 "Answering service",
                 "24/7 coverage (multiple people)"],
            )

            # Estimated cost of current setup
            current_cost_map = {
                "No receptionist (calls go to whoever's available)": 0,
                "Part-time receptionist (40 hours/week)": 28000,
                "Full-time receptionist (40 hours/week)": 50000,
                "Answering service": 8400,  # ~$700/mo typical
                "24/7 coverage (multiple people)": 200000,
            }
            current_cost = current_cost_map.get(current_setup, 0)
            st.metric("Their current annual cost", f"${current_cost:,}",
                      help="Fully-loaded: salary + benefits + taxes + equipment")

            st.markdown("**Ana Receptionist cost:**")
            ana_year1_cost = 46000  # $20K impl + $2K training + $24K licensing+maintenance
            ana_ongoing_cost = 24000  # $24K/yr ongoing
            st.metric("Ana Year 1 (one-time setup + ongoing)", f"${ana_year1_cost:,}")
            st.metric("Ana Year 2+ (ongoing only)", f"${ana_ongoing_cost:,}")

        st.divider()

        # === Live computed ROI ===
        monthly_missed = int(monthly_calls * (missed_pct / 100))
        monthly_lost_potential = monthly_missed * avg_value * (conv_rate / 100)
        annual_lost = monthly_lost_potential * 12

        # Year 1 net: revenue recovered (vs current setup) minus Ana cost
        # If they replace a $50K FTE with Ana, they ALSO save the FTE cost
        annual_savings_from_replacement = current_cost - ana_ongoing_cost  # Year 2+
        annual_net_recovery_y1 = annual_lost + (current_cost - ana_year1_cost)
        annual_net_recovery_y2 = annual_lost + annual_savings_from_replacement

        # Break-even in months
        monthly_ana_cost = ana_year1_cost / 12
        monthly_net_benefit = (monthly_lost_potential + current_cost / 12) - monthly_ana_cost
        if monthly_net_benefit > 0:
            breakeven_months = max(1, round(ana_year1_cost / (monthly_lost_potential + current_cost / 12)))
        else:
            breakeven_months = None

        st.markdown("### 💡 The math to share on the call")

        m1, m2, m3 = st.columns(3)
        m1.metric("Missed calls / month", f"{monthly_missed:,}",
                  help=f"{missed_pct}% of {monthly_calls:,} = {monthly_missed:,}")
        m2.metric("Revenue lost / month", f"${monthly_lost_potential:,.0f}",
                  help=f"{monthly_missed:,} missed × {conv_rate}% conv × ${avg_value:,.0f} = ${monthly_lost_potential:,.0f}")
        m3.metric("Revenue lost / year", f"${annual_lost:,.0f}",
                  delta=f"vs Ana ${ana_ongoing_cost:,}/yr",
                  help="What you're losing now annually to missed calls alone")

        st.divider()

        m4, m5, m6 = st.columns(3)
        m4.metric("Year 1 net benefit", f"${annual_net_recovery_y1:,.0f}",
                  help="Revenue recovered + current receptionist savings - Ana Year 1 cost")
        m5.metric("Year 2+ net benefit", f"${annual_net_recovery_y2:,.0f}",
                  help="Pure profit once setup is paid off")
        if breakeven_months:
            m6.metric("Break-even", f"{breakeven_months} months",
                      help="When recovered revenue + savings = Ana cost")
        else:
            m6.metric("Break-even", "N/A",
                      help="Numbers don't break even — likely too few calls. Reconsider fit.")

        st.divider()

        st.markdown("### 🎯 Closing lines to use")
        if annual_net_recovery_y2 > 50000:
            st.success(
                f"**Strong close:** \"On your own numbers, you're losing about "
                f"**${annual_lost:,.0f}** a year to missed calls. Ana costs **${ana_ongoing_cost:,}** a year ongoing. "
                f"Even if I'm only 50% right about those missed calls, you're netting "
                f"**${annual_net_recovery_y2 // 2:,.0f}** in your first year. "
                f"That's break-even in **{breakeven_months or '~7'} months**, then it's pure profit.\""
            )
        elif breakeven_months and breakeven_months <= 12:
            st.info(
                f"**Reasonable close:** \"You'd break even in **{breakeven_months} months**, "
                f"then recover **${annual_net_recovery_y2:,.0f}** per year going forward. "
                f"Want me to put together a 15-minute demo so you can decide if the numbers feel right?\""
            )
        else:
            st.warning(
                "Numbers suggest this might not be a strong fit — call volume too low or "
                "missed-call rate too low to justify Ana. Consider whether this prospect "
                "is in the right size range, or focus on non-financial benefits (24/7 coverage, bilingual, no sick days)."
            )

        st.markdown("**Concrete talking points:**")
        st.markdown(f"- **1 vs 100 concurrent calls.** Your receptionist takes one call. Customer #2 hears voicemail. Ana takes 100 simultaneously.")
        if current_cost > ana_ongoing_cost:
            st.markdown(f"- **You're paying ${current_cost:,} for current coverage.** Ana costs ${ana_ongoing_cost:,} ongoing — saves you **${current_cost - ana_ongoing_cost:,}/year** AND adds 24/7 + bilingual.")
        st.markdown(f"- **Ana works 24/7/365.** No sick days, no vacation, no training, no turnover.")
        st.markdown(f"- **Native bilingual.** No \"press 1 for English\" friction.")

    # === Close Out tab ===
    with tabs[5]:
        st.markdown("**End this call and log the outcome:**")

        outcome = st.selectbox(
            "Outcome",
            [opt[0] for opt in OUTCOME_OPTIONS],
            format_func=lambda x: next(opt[1] for opt in OUTCOME_OPTIONS if opt[0] == x),
        )

        c1, c2 = st.columns(2)
        with c1:
            connected = st.checkbox("Connected with a human",
                                     value=outcome not in ["no_answer", "voicemail_left", "wrong_number"])
            reached_dm = st.checkbox("Reached decision maker",
                                      value=outcome in ["demo_booked", "not_interested", "callback_requested"])
        with c2:
            conv_quality = st.slider("Conversation quality (1-10)", 1, 10, 5,
                                      help="Be honest — this trains future targeting")
            est_value = st.number_input("Estimated deal value ($)", min_value=0.0,
                                         value=35000.0, step=5000.0,
                                         help="Ana deals: $20k-$50k typical one-time + monthly recurring")

        next_action = st.text_input("Next action", placeholder="e.g., Follow up Friday with demo recap")
        next_action_date = st.date_input("Next action date", value=date.today())

        if st.button("🏁 Close Out Call", type="primary", use_container_width=True):
            new_status = next((opt[2] for opt in OUTCOME_OPTIONS if opt[0] == outcome and opt[2]), None)

            end_call(call_id,
                outcome=outcome,
                connected=connected,
                reached_decision_maker=reached_dm,
                conversation_quality_score=conv_quality,
                estimated_deal_value=est_value,
                next_action=next_action or None,
                next_action_date=next_action_date.isoformat() if next_action_date else None,
            )

            # Update business status
            if new_status:
                sb().table("businesses").update({"status": new_status}).eq("id", business_id).execute()
            else:
                # Auto-advance Call N counter
                biz_resp = sb().table("businesses").select("status").eq("id", business_id).execute()
                if biz_resp.data:
                    cur = biz_resp.data[0]["status"]
                    advance_map = {
                        "New": "Call 1 Made",
                        "Research Done": "Call 1 Made",
                        "Call 1 Made": "Call 2 Made",
                        "Call 2 Made": "Call 3 Made",
                    }
                    if cur in advance_map:
                        sb().table("businesses").update({"status": advance_map[cur]}).eq("id", business_id).execute()

            # Clear call session state
            for k in ["active_call_id", "active_call_business_id",
                      "active_call_business_name", "active_call_language"]:
                st.session_state.pop(k, None)

            st.session_state["page"] = "Daily Cockpit"
            st.success(f"Call logged: {outcome}")
            time.sleep(1)
            st.rerun()


# ---------------------------------------------------------------------------
# PAGE: Objection Bible
# ---------------------------------------------------------------------------
def page_objection_bible():
    st.title("🛡️ Objection Bible")
    st.caption("Acknowledge → Reframe → Reclose handlers, tuned for Ana Receptionist sales. Bilingual.")

    c1, c2 = st.columns(2)
    with c1:
        view_lang = st.radio("Display language", ["en", "es"],
                              format_func=lambda x: "🇺🇸 English" if x == "en" else "🇲🇽 Español",
                              horizontal=True)
    with c2:
        category_filter = st.selectbox("Filter by category",
            ["All", "price", "timing", "trust", "competition", "fit", "authority", "fear", "information"])

    objections = load_objections(category=category_filter)
    if objections.empty:
        st.info("No objections in the bible yet.")
    else:
        total_used = int(objections["times_used"].sum() or 0)
        total_succ = int(objections["times_succeeded"].sum() or 0)
        success_rate = (total_succ / total_used * 100) if total_used > 0 else 0

        cols = st.columns(3)
        cols[0].metric("Objections in bible", len(objections))
        cols[1].metric("Total encounters", total_used)
        cols[2].metric("Handler success rate", f"{success_rate:.0f}%")

        st.divider()

        for _, obj in objections.iterrows():
            obj_dict = obj.to_dict()
            obj_text = _localize(obj_dict, "objection_text", view_lang)
            used = obj.get("times_used") or 0
            succ = obj.get("times_succeeded") or 0
            rate = (succ / used * 100) if used > 0 else None
            extra = f" · {int(used)} uses · {rate:.0f}% handled" if rate is not None else ""
            with st.expander(f"💬 [{obj.get('category', 'misc').upper()}] {obj_text}{extra}"):
                st.markdown(f"**🤝 Acknowledge:** {_localize(obj_dict, 'acknowledge', view_lang)}")
                st.markdown(f"**🔄 Reframe:** {_localize(obj_dict, 'reframe', view_lang)}")
                st.markdown(f"**🎯 Reclose:** {_localize(obj_dict, 'reclose', view_lang)}")
                proof = _localize(obj_dict, "social_proof", view_lang)
                if proof:
                    st.info(f"💡 Social proof: {proof}")

                with st.expander("✏️ Edit this objection"):
                    with st.form(f"edit_obj_{obj['id']}"):
                        n_text_en = st.text_input("Objection (EN)", value=obj["objection_text_en"])
                        n_text_es = st.text_input("Objection (ES)", value=obj.get("objection_text_es") or "")
                        n_ack_en = st.text_area("Acknowledge (EN)", value=obj["acknowledge_en"])
                        n_ack_es = st.text_area("Acknowledge (ES)", value=obj.get("acknowledge_es") or "")
                        n_ref_en = st.text_area("Reframe (EN)", value=obj["reframe_en"])
                        n_ref_es = st.text_area("Reframe (ES)", value=obj.get("reframe_es") or "")
                        n_rec_en = st.text_area("Reclose (EN)", value=obj["reclose_en"])
                        n_rec_es = st.text_area("Reclose (ES)", value=obj.get("reclose_es") or "")
                        if st.form_submit_button("Save Changes"):
                            sb().table("objections").update({
                                "objection_text_en": n_text_en,
                                "objection_text_es": n_text_es or None,
                                "acknowledge_en": n_ack_en,
                                "acknowledge_es": n_ack_es or None,
                                "reframe_en": n_ref_en,
                                "reframe_es": n_ref_es or None,
                                "reclose_en": n_rec_en,
                                "reclose_es": n_rec_es or None,
                            }).eq("id", obj["id"]).execute()
                            st.success("Updated!")
                            st.rerun()

    st.divider()

    with st.expander("➕ Add new objection to the bible"):
        with st.form("new_objection"):
            n_code = st.text_input("Code (slug)", placeholder="e.g., needs_more_features")
            n_category = st.selectbox("Category",
                ["fit", "price", "timing", "trust", "competition", "authority", "fear", "information"])
            n_text_en = st.text_input("Objection (EN) *", placeholder="What the prospect actually says")
            n_text_es = st.text_input("Objection (ES)", placeholder="Spanish version (optional)")
            n_ack_en = st.text_area("Acknowledge (EN) *", placeholder="Validate their concern in 1-2 sentences")
            n_ref_en = st.text_area("Reframe (EN) *", placeholder="New angle with proof or context")
            n_rec_en = st.text_area("Reclose (EN) *", placeholder="Assumptive next step — specific calendar ask")

            if st.form_submit_button("Add to Bible"):
                if not all([n_code, n_text_en, n_ack_en, n_ref_en, n_rec_en]):
                    st.error("Fill all required fields (marked *)")
                else:
                    try:
                        sb().table("objections").insert({
                            "code": n_code,
                            "category": n_category,
                            "objection_text_en": n_text_en,
                            "objection_text_es": n_text_es or None,
                            "acknowledge_en": n_ack_en,
                            "reframe_en": n_ref_en,
                            "reclose_en": n_rec_en,
                        }).execute()
                        st.success("Added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")


# ---------------------------------------------------------------------------
# SIDEBAR + NAVIGATION
# ---------------------------------------------------------------------------
def main():
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/phone-ringing.png", width=48)
        st.title("Ana Lead Tracker")
        st.caption("Itxaz Internal Sales Tool")

        # Two groups: Lead Tracker (find leads) + Sales Engine (close them)
        st.markdown("**📊 Lead Tracker**")
        tracker_pages = ["Dashboard", "All Businesses", "Lead Detail", "Run Deep Research"]
        st.markdown("**🎯 Sales Engine**")
        engine_pages = ["Daily Cockpit", "Live Call", "Objection Bible"]
        st.markdown("**⚙️ System**")
        system_pages = ["Settings"]

        pages = tracker_pages + engine_pages + system_pages
        current = st.session_state.get("page", "Dashboard")
        if current not in pages:
            current = "Dashboard"

        page = st.radio("Navigate", pages, index=pages.index(current), label_visibility="collapsed")
        st.session_state["page"] = page

        st.divider()

        # Quick stats in sidebar
        try:
            df = load_businesses()
            if not df.empty:
                active = df[~df["status"].isin(["Do Not Contact", "Closed Lost", "Not Interested"])]
                st.metric("Active Leads", len(active))
                st.metric("Top Score", f"{df['overall_score'].max():.1f}")
                needs_call = df[df["status"].isin(["Research Done", "New"])]
                st.metric("Ready to Call", len(needs_call))
        except Exception:
            pass

        st.divider()
        st.caption("v1.0 · Built for Itxaz")

    # Route
    if page == "Dashboard":
        page_dashboard()
    elif page == "All Businesses":
        page_all_businesses()
    elif page == "Lead Detail":
        page_lead_detail()
    elif page == "Run Deep Research":
        page_research()
    elif page == "Daily Cockpit":
        page_call_cockpit()
    elif page == "Live Call":
        page_live_call()
    elif page == "Objection Bible":
        page_objection_bible()
    elif page == "Settings":
        page_settings()


if __name__ == "__main__":
    main()
