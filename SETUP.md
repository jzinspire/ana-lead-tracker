# Ana Lead Tracker — Setup Guide

## Prerequisites

- Python 3.11+
- A Supabase account (free tier works)
- **Claude Code installed and logged in** — scoring uses the Claude Agent SDK
  which delegates to your local Claude Code (draws from your Claude Max
  subscription, no API key needed).
  Install: https://docs.claude.com/claude-code
  After install, run `claude login` once.
- (Optional) An Apify API token (for Google Maps data collection)

---

## Step 1: Set up Supabase

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Once the project is created, go to **SQL Editor** in the sidebar
3. Paste the contents of `supabase_schema.sql` and click **Run**
   - This creates the Lead Tracker tables, indexes, default settings, and seeds 20 pre-researched Phoenix prospects
4. **Then** paste the contents of `supabase_schema_sales_engine.sql` and click **Run**
   - This adds the Sales Engine tables (sales_calls, objections, objection_encounters) + pre-seeds 10 bilingual objection handlers
5. Get your credentials from **Settings > API > Legacy anon, service_role API keys**:
   - **Project URL** (e.g., `https://abc123.supabase.co`)
   - **anon public key** (the long `eyJ...` key)

---

## Step 2: Local Setup

```bash
# Navigate to this directory
cd "/path/to/Ana Lead Tracker"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your actual keys (use TextEdit, VS Code, etc.)
```

Fill in your `.env`:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGc...your-anon-key
APIFY_API_TOKEN=apify_api_...  # optional
```

**Note:** No `ANTHROPIC_API_KEY` is required. Scoring runs through your local
Claude Code (which must be installed and logged in). Verify with:
```bash
claude --version
```

---

## Step 3: Run Locally

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. You should see the Dashboard with 20 pre-loaded prospects.

Open the **Settings** page to verify all integrations show ✅.

---

## Step 4: Deploy to Streamlit Community Cloud (Optional)

⚠️ **Important:** The deployed version cannot use your Claude Max subscription —
Streamlit Cloud has no way to access your local Claude Code login. You have two
options for the deployed version:

**Option A: Run locally only (recommended for now)**
Keep using `streamlit run app.py` on your laptop. The research feature works
because Claude Code is logged in locally. Most of the calling workflow happens
on your laptop anyway.

**Option B: Deploy with API fallback**
If you want the deployed version to support research, you'd need to add the
`anthropic` package back and use an API key as a fallback. This is not set up
by default — ask before adding it.

To deploy without the research feature (lead tracking + notes still work):

1. Push the code to a GitHub repo (e.g., `jzinspire/ana-lead-tracker`)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** and connect your GitHub repo
4. Set:
   - **Main file path:** `app.py`
   - **Python version:** 3.11
5. Go to **Advanced settings > Secrets** and paste:
   ```toml
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "eyJhbGc...your-anon-key"
   APIFY_API_TOKEN = "apify_api_..."  # optional
   ```
6. Click **Deploy**

The Research feature will show an error on the deployed version but everything
else (Dashboard, Lead Detail, All Businesses, status tracking, notes, CSV export)
works fine remotely.

---

## Using the App

The app has **two modules** in the sidebar:

### 📊 Lead Tracker (Module 1)
Finds and scores prospects. Use this to build your pipeline.

### 🎯 Sales Engine (Module 2)
Converts scored leads into closed Ana Receptionist deals. Use this daily for calls.

---

## Lead Tracker pages

### Dashboard
- Shows pipeline summary and Top 50 ranked prospects
- Click **View** on any business to open its detail page

### All Businesses
- Search by name, filter by industry/city/status/score range
- Export filtered results to CSV

### Lead Detail
- View score breakdown and key evidence
- Update lead status (e.g., after making a call)
- Read the personalized call script
- Add call notes with optional scoring feedback
- Feedback is used to improve future research scoring

### Run Deep Research
- Configure industries and cities to search
- Click **Run Deep Research** to find and score new candidates
- With Apify: pulls real business data from Google Maps
- Without Apify: Claude generates and scores candidates from its knowledge
- Results are saved to the database and appear on the Dashboard
- **Uses your Claude Max subscription** (via local Claude Code), not the API

---

## Sales Engine pages

### 🎯 Daily Cockpit
**The page you open every morning.** Auto-curates your top calls for today:
- 50% fresh high-score leads (Research Done / New)
- 30% stale follow-ups (Call 1/2 Made — don't let them cool)
- 20% demo confirmations needed

For each lead:
- **Personalized opener** generated by Claude using Connor Murray's Oracle 3-Part Value Statement framework
- Pre-call brief: key fit evidence, current status
- Bilingual toggle (🇺🇸 / 🇲🇽)
- "Start Call" button creates a sales_calls record and opens the Live Call view

**Tuned for high-ticket selling:** Default list size is 10/day (not 50/100). Ana deals are $20k-$50k — quality conversations > volume dials.

### 📞 Live Call
Active during a call. 5 tabs always visible:
- **🎬 Opener** — your personalized 3-Part Value Statement for this lead
- **🛡️ Objections** — full bilingual Objection Bible, one click to expand any handler. Log whether each one worked.
- **❓ Discovery** — 8 high-leverage questions (Teddy Frank's hyper-relevance approach)
- **📝 Notes** — live notes that save to the call record
- **✅ Close Out** — log outcome (Demo Booked / Voicemail / Not Interested / etc.), conversation quality, estimated deal value, next action. Updates business status automatically.

### 🛡️ Objection Bible
Browse, filter, edit, and add to the library of objection handlers. Pre-seeded with 10 SMB-specific objections for Ana Receptionist sales, fully bilingual EN/ES:

1. "We already have someone answering" (competition)
2. "Too expensive" (price) — with ROI math
3. "Customers won't trust AI" (trust) — with Ricardo Diaz proof
4. "We don't get that many calls" (fit) — pivot to free call audit
5. "Send me info" (information) — pivot to demo
6. "I need to ask my partner" (authority) — bring partner into demo
7. "How is this different from voicemail?" (fit) — Ana books, voicemail doesn't
8. "We tried something like this before" (trust) — that was IVR/chatbot, this is different
9. "Not ready / call back later" (timing) — get specific
10. "What about complex/Spanish calls?" (fit) — native Spanish, warm transfer for edge cases

Each tracks usage + success rate. The system learns which handlers actually work for you.

---

## Sales methodology references

The Sales Engine is built on synthesized best practices from the world's top cold callers:

| Source | Contribution |
|---|---|
| **Connor Murray (ex-Oracle #1 SDR, now Datadog AE)** | 3-Part Value Statement framework — used in personalized opener generation |
| **Teddy Frank (UserGems, 27.8% conversion rate)** | Hyper-targeted discovery questions, depth-over-volume approach |
| **Jason Bay (Outbound Squad, trains Shopify/Zoom/Gong)** | First 60 seconds focus, assumptive close patterns |
| **Superhuman Prospecting (H2H methodology)** | Acknowledge → Reframe → Reclose objection pattern, bilingual scripts |

Elite benchmarks to track:
- Dial → meeting: 2-3% average / 8-11% elite / 28% outlier (Teddy)
- Connect rate: 10-20% average / 30%+ elite
- Daily volume: **10-20 quality calls** for $20k-$50k tickets (not 100 spam dials)

---

## Settings
- Adjust scoring weights (e.g., increase Urgency weight for summer)
- Configure default research parameters
- Recalculate all scores after changing weights
- View integrations status (Claude Code, Supabase, Apify) and scoring feedback summary

---

## Data Flow

```
Data Sources (Apify / Google Maps)
        ↓
  Raw candidate list
        ↓
  Claude Code via Agent SDK (uses your Max subscription)
        ↓
  Ranked results → Supabase database
        ↓
  Dashboard (Top 50) → Call → Log notes
        ↓
  Feedback loop → improves next research run
```

---

## Troubleshooting

**"Claude Code CLI not found"** — Install Claude Code from
https://docs.claude.com/claude-code, then run `claude login` once.

**"Claude Agent SDK is not installed"** — Activate your venv and run
`pip install claude-agent-sdk`.

**Research hangs or errors** — Open Settings page and check both Claude
Agent SDK and Claude Code CLI show ✅. If either is missing, follow the
hint shown in the status line.

**"JSON decode error"** — Claude returned non-JSON text. This sometimes
happens on large candidate batches. Try reducing `max_candidates` to 10-20
in the Research page.

---

## Notes

- **Never hard-delete data** — use the `archived` flag for soft deletes
- **Research runs are logged** — check history in the Research page
- **Scoring feedback matters** — add it when logging calls to improve future research
- **Weights are live** — changing weights and clicking Recalculate updates all scores instantly
- **Scoring is free for you** — runs on your Claude Max subscription via Claude Code
