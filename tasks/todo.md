# Ana Lead Tracker — Tasks

## Phase 1: Core Lead Tracker (COMPLETE)
- [x] Supabase schema — `supabase_schema.sql`
- [x] Streamlit app scaffolding — `app.py`
- [x] Dashboard with Top 50 view + pipeline summary + metrics
- [x] All Businesses table (search, filter by industry/city/status/score, CSV export)
- [x] Lead Detail page (score breakdown, call history, notes, call script, status updates)
- [x] Status tracking with full 12-status list + auto-advance logic
- [x] Settings page (scoring weights, research config, integration status)
- [x] Seed data loaded (20 Phoenix-area prospects)
- [x] Research feature (Claude-powered scoring via Agent SDK, prompt caching, feedback loop)
- [x] Manual business entry
- [x] Setup instructions — `SETUP.md`

## Phase 2: Sales Engine (COMPLETE)
- [x] Sales Engine schema — `supabase_schema_sales_engine.sql` (sales_calls, objections, objection_encounters)
- [x] Daily Cockpit (caller selector, language toggle, today's stats, smart call list curation)
- [x] Personalized openers (Connor Murray 3-Part Framework, Claude-generated, cached)
- [x] Live Call interface (5 tabs: Opener, Objections, Discovery, Notes, Close Out)
- [x] Live call timer + auto-advance status on close out
- [x] Objection Bible (10 pre-seeded bilingual objections, Acknowledge/Reframe/Reclose)
- [x] Objection tracking (encounters, success rate analytics, edit/add)
- [x] Discovery questions (8 questions, bilingual EN/ES)
- [x] Full bilingual support (EN/ES) across Sales Engine

## Phase 3: Infrastructure & Launch (TODO)
- [ ] Initialize git repo and push to `jzinspire/ana-lead-tracker`
- [ ] Set up Supabase project and run both schemas
- [ ] Test full research pipeline end-to-end with live database
- [ ] Deploy to Streamlit Community Cloud
- [ ] First real research run against Phoenix metro
