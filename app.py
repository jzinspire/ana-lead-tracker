import streamlit as st
import pandas as pd
import json
import time
import os
from datetime import datetime, date
from supabase import create_client, Client

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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Ana Lead Tracker",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    weights = get_scoring_weights()
    score_cols = st.columns(6)
    for i, (field, label) in enumerate(SCORE_FIELDS):
        val = float(biz.get(field, 0))
        score_cols[i].metric(label, f"{val}/10")

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
        ["HVAC", "Plumbing", "Dental", "Roofing", "Veterinary", "Legal", "Medical", "Auto Repair"],
    )
    default_cities = research_config.get(
        "default_cities",
        ["Phoenix", "Scottsdale", "Tempe", "Mesa", "Chandler", "Gilbert", "Glendale", "Peoria"],
    )

    st.subheader("Configure Research Run")
    col1, col2 = st.columns(2)
    with col1:
        industries = st.multiselect(
            "Industries to search",
            default_industries + ["Other"],
            default=default_industries[:4],
        )
    with col2:
        cities = st.multiselect(
            "Cities to search", default_cities, default=default_cities[:4]
        )

    max_candidates = st.slider("Max candidates to score", 10, 100, 50, 10)
    run_type = st.radio("Run type", ["manual", "weekly", "daily"], horizontal=True)

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

        new_count = 0
        for biz in scored:
            if biz["name"].lower() in existing_names:
                continue
            biz["last_research_run_id"] = run_id
            biz["status"] = "Research Done"
            sb().table("businesses").insert(biz).execute()
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


def _collect_candidates(
    industries: list[str], cities: list[str], max_candidates: int, apify_token: str
) -> list[dict]:
    """
    Collect candidate businesses from data sources.
    Uses Apify Google Maps Scraper if token is available, otherwise generates
    search-ready candidate stubs for manual enrichment or Claude web search.
    """
    candidates = []

    if apify_token:
        try:
            from apify_client import ApifyClient

            client = ApifyClient(apify_token)

            for industry in industries:
                for city in cities:
                    if len(candidates) >= max_candidates:
                        break
                    query = f"{industry} near {city}, AZ"
                    run_input = {
                        "searchStringsArray": [query],
                        "maxCrawledPlacesPerSearch": min(
                            10, max_candidates - len(candidates)
                        ),
                        "language": "en",
                        "maxReviews": 0,
                    }
                    run = client.actor("drobnikj/crawler-google-places").call(
                        run_input=run_input
                    )
                    dataset = client.dataset(run["defaultDatasetId"])
                    for item in dataset.iterate_items():
                        candidates.append({
                            "name": item.get("title", ""),
                            "industry": industry,
                            "city": item.get("city", city),
                            "website": item.get("website", ""),
                            "phone": item.get("phone", ""),
                            "google_reviews": str(item.get("totalScore", "")),
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


SCORING_SYSTEM_PROMPT = """You are an expert business analyst for Itxaz, a company that sells Ana Receptionist — an AI-powered voice receptionist for SMBs. Your job is to evaluate businesses and score them on how likely they are to be a good fit for Ana Receptionist.

Ana Receptionist answers phone calls 24/7, books appointments, speaks English and Spanish, and ensures businesses never miss a customer call. The ideal customer:
- Has high inbound call volume (especially after hours or during peak times)
- Loses revenue from missed/abandoned calls
- Serves bilingual (English/Spanish) communities
- Is technologically ready to adopt AI tools
- Has accessible decision-makers and budget
- Has urgent pain (seasonal demand, growth, staffing issues)

Score each business on these six criteria (1-10 scale):
1. Call Volume — estimated daily inbound calls
2. Missed Call Pain — how much they lose from missed calls
3. Bilingual Opportunity — Spanish-speaking customer base
4. Tech Readiness — existing tech sophistication + AI willingness
5. Ease of Closing — decision-maker access, budget signals
6. Urgency — time-sensitive pain driving immediate need

For each business, provide:
- Individual scores (1-10) for each criterion
- An overall weighted score
- Key evidence supporting the scores (2-3 sentences)
- A brief suggested call script opening tailored to this specific business

Respond in valid JSON format as an array of objects with these fields:
name, industry, city, website, phone, google_reviews,
score_call_volume, score_missed_call_pain, score_bilingual,
score_tech_readiness, score_ease_of_closing, score_urgency,
overall_score, key_evidence, score_explanation, suggested_call_script

IMPORTANT: Be realistic. Don't inflate scores. A score of 7+ should mean genuine strong fit.
Phoenix metro area is heavily Hispanic — most service businesses here have bilingual opportunity of at least 6-7.
HVAC/Plumbing in Phoenix has extreme seasonal urgency (summer = 110°F+ = AC emergencies).
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

    candidates_text = json.dumps(candidates, indent=2, default=str)

    user_msg = (
        f"Score these candidate businesses for Ana Receptionist fit. "
        f"Apply these scoring weights: {json.dumps(weights)}\n\n"
        f"Candidates:\n{candidates_text}"
        f"{feedback_context}\n\n"
        f"Respond with ONLY a JSON array — no preamble, no markdown fences, no commentary. "
        f"Begin your response with `[` and end with `]`."
    )

    progress.progress(50, text="Claude is analyzing candidates (via Claude Code)...")

    try:
        response_text = asyncio.run(
            _query_claude_via_sdk(prompt=user_msg, system_prompt=SCORING_SYSTEM_PROMPT)
        )
    except FileNotFoundError:
        st.error(
            "Claude Code CLI not found. Install it from https://docs.claude.com/claude-code "
            "and run `claude login` before using the research feature."
        )
        return []
    except Exception as e:
        st.error(f"Claude Agent SDK error: {e}")
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

    return scored


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

    # Research config
    st.subheader("Research Configuration")
    research_config = settings.get("research_config", {})

    industries_str = st.text_area(
        "Default industries (one per line)",
        value="\n".join(research_config.get("default_industries", [])),
        height=120,
    )
    cities_str = st.text_area(
        "Default cities (one per line)",
        value="\n".join(research_config.get("default_cities", [])),
        height=100,
    )
    max_per_run = st.number_input(
        "Max candidates per research run",
        value=research_config.get("max_candidates_per_run", 50),
        min_value=10,
        max_value=200,
    )
    frequency = st.selectbox(
        "Research frequency",
        ["weekly", "daily"],
        index=0 if research_config.get("research_frequency") == "weekly" else 1,
    )

    if st.button("Save Research Config"):
        new_config = {
            "default_industries": [i.strip() for i in industries_str.split("\n") if i.strip()],
            "default_cities": [c.strip() for c in cities_str.split("\n") if c.strip()],
            "max_candidates_per_run": max_per_run,
            "research_frequency": frequency,
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
        return (
            "[Claude CLI not on PATH. Install from https://docs.claude.com/claude-code "
            "and run `claude login`. PATH=" + os.environ.get("PATH", "")[:300] + "]"
        )

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

    tabs = st.tabs(["🎬 Opener", "🛡️ Objections", "❓ Discovery", "📝 Notes", "✅ Close Out"])

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

    # === Close Out tab ===
    with tabs[4]:
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
