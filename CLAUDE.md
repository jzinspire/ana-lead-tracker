# CLAUDE.md — Ana Lead Tracker

**Last updated:** 2026-05-20
**Owner:** Josue (tech@itxaz.com)
**Status:** Build phase — internal Itxaz sales tool

---

## What this project is

Ana Lead Tracker is an internal sales tool for Itxaz. It finds, scores, and tracks SMB prospects who are the best fit for **Ana Receptionist** (our live AI receptionist product). It's NOT a product we sell — it's a tool we use to sell.

**Stack:** Streamlit (UI) + Supabase (database) + Claude API (research analysis) + Apify or similar (data collection)

**Repo:** `jzinspire/ana-lead-tracker`
**Docs:** `Projects/Josue Workspace/Ana Lead Tracker/` (Google Drive)

---

## Itxaz context (read once, apply always)

This project exists within the Itxaz ecosystem. Key context:

- **Ana** = the family brand / platform. **Ana Receptionist** = the specific live product (Ricardo Diaz Insurance is our first client).
- The scoring criteria reflect what makes a business a good Ana Receptionist candidate: high call volume, missed-call pain, bilingual need, tech readiness, ease of closing, urgency.
- The leads this tool finds will eventually be contacted by Josue and/or Santiago. The tool should optimize for **daily calling efficiency**.
- Refer to the Itxaz shared vocabulary: never say "the bot" or "the AI" — say "Ana Receptionist" when talking about the product.

**Reference files (in Google Drive, not this repo):**
- `Projects/CLAUDE.md` — master Itxaz partner rules (destructive ops protocol, coordination norms)
- `Projects/Consulting Toolkit/02-gotchas/master-list.md` — lessons learned across all projects
- `Projects/Itxaz Products/Ana Cross-Sell/` — product spec (for understanding what we're selling)

---

## Technical rules

### Stack constraints
- **Frontend:** Streamlit only. No React, no Next.js. Keep it simple — this is an internal tool.
- **Database:** Supabase (PostgreSQL). Minimal clean tables. Use Row Level Security if exposing publicly, skip if local-only.
- **AI analysis:** Anthropic Claude API (Sonnet 4). Use prompt caching for the scoring system prompt.
- **Data collection:** Apify, Google Maps API, or similar. Keep data sources pluggable — don't hardcode to one provider.

### Code standards
- Python 3.11+
- Use `requirements.txt` (not Poetry/Pipenv — keep it simple)
- All secrets via `.env` file locally, Streamlit secrets for deployment
- Never commit `.env` or `secrets.toml`
- Type hints on all function signatures
- Docstrings on all public functions

### Scoring system
Six criteria, each scored 1-10:

| Criterion | What it measures |
|-----------|-----------------|
| Call Volume | How many inbound calls the business handles daily |
| Missed Call Pain | How much they lose from missed/abandoned calls |
| Bilingual Opportunity | Whether they serve Spanish-speaking customers |
| Tech Readiness | Existing tech stack sophistication + willingness to adopt AI |
| Ease of Closing | Decision-maker accessibility, budget signals, buying readiness |
| Urgency | Time-sensitive pain (seasonal, growth, staff turnover) |

**Overall score** = weighted average (default weights equal; user can adjust in settings).

### Research feature
- "Run Weekly Deep Research" pulls fresh candidates from data sources
- Sends raw data to Claude for scoring + explanation
- Generates ranked Top 50 list
- Stores results + updates database
- **Feedback loop:** user call notes and outcomes feed back into future research scoring

### Statuses (exact list, do not modify)
```
New
Research Done
Call 1 Made
Call 2 Made
Call 3 Made
Voicemail Left
No Answer (3+ attempts)
Interested - Demo Booked
Not Interested (require reason)
Do Not Contact
Closed Won
Closed Lost
```

---

## Task management

- Write plans to `tasks/todo.md` before starting multi-step work
- Track lessons in `tasks/lessons.md`
- Mark items complete as you go

---

## Destructive operations

Inherits the master protocol from `Projects/CLAUDE.md` Section 3. In this project specifically:
- **Never drop Supabase tables** without verbatim confirmation
- **Never delete lead data** — soft-delete only (add `archived` flag)
- **Never overwrite research results** — append new research runs, keep history

---

## Deployment

- **Local:** `streamlit run app.py`
- **Production:** Streamlit Community Cloud (free tier) or similar
- **NOT on Vercel** — this is a Python app, keep it in the Streamlit ecosystem
