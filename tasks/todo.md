# Ana Lead Tracker — Tasks

## Phase 1: Core Lead Tracker (COMPLETE)
- [x] Supabase schema — `supabase_schema.sql`
- [x] Streamlit app scaffolding — `app.py`
- [x] Dashboard with Top 50 view + pipeline summary + metrics
- [x] All Businesses table (search, filter by industry/city/status/score, CSV export)
- [x] Lead Detail page (score breakdown, call history, notes, call script, status updates)
- [x] Status tracking with full 12-status list + auto-advance logic
- [x] Settings page (scoring weights, research config, integration status)
- [x] Seed data loaded (20 Phoenix-area prospects — **hardcoded estimates, not researched**)
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
- [x] Fixed mojibake encoding in objection data (em-dashes, Spanish accents)

## Phase 3: Infrastructure & Launch (COMPLETE)
- [x] Git repo pushed to `jzinspire/ana-lead-tracker` (public)
- [x] Supabase project set up, both schemas loaded
- [x] First real research run (May 23, 2026 — 13 businesses scored)
- [x] Deployed to Streamlit Community Cloud
- [x] Sales Engine PDF guide generated (`Ana_Lead_Tracker_Sales_Engine_Guide.pdf`)
- [x] Santiago setup guide (`SETUP-SANTIAGO.md`)

## Phase 4: Real-Data Scoring (COMPLETE)
- [x] Designed evidence-based scoring rubric (no inference, observable signals only)
- [x] Built `enrichment.py` — website scraper + review miner
- [x] Added 30-review fetch to Apify pipeline
- [x] Rewrote `SCORING_SYSTEM_PROMPT` to require evidence per criterion
- [x] Added per-criterion evidence fields to scoring output
- [x] Updated Lead Detail UI with data-provenance badge + evidence expander
- [x] Added "Re-research this business" button to upgrade seed data
- [x] Created `supabase_schema_enrichment.sql` migration
- [x] Ran schema migration in Supabase
- [x] Added bulk "Re-research all unverified businesses" button in Settings

## Phase 5: Smart Research Config (COMPLETE — 2026-05-23)
- [x] Expanded to 16 industries (added Insurance Agencies, Immigration Law, Electrical, Pest Control, Pool Service, Solar, Locksmith, Water Damage Restoration, Bail Bonds, Property Management)
- [x] Expanded to 16 Phoenix Valley cities (added Surprise, Avondale, Goodyear, Buckeye, Queen Creek, Apache Junction, Maricopa, Tolleson)
- [x] Built `INDUSTRY_QUERY_MAP` for smart Apify queries
- [x] Built `_passes_prefilter()` to drop bad candidates before Claude scoring
- [x] Added pre-filter knobs to Settings UI (min/max reviews, require website/phone)
- [x] Added budget estimator on Research page (combos × candidates)
- [x] Updated `supabase_schema.sql` defaults for fresh deployments

## Phase 6: Call Brief (PROPOSED, NOT BUILT)
- [ ] Pre-populate Live Call Opener with personalized opener referencing real review quotes
- [ ] Pre-populate Live Call Notes tab with one-page briefing card
- [ ] Pre-rank Top 3 anticipated objections per business
- [ ] (Optional Phase B) Smart Discovery — hide already-known questions, add data-grounded ones
- [ ] (Optional Phase B) Close Out follow-up email templates

## Phase 7: Business Association Detection (COMPLETE — 2026-05-23)
- [x] BBB Accreditation detection (domain ref + phrase patterns)
- [x] Hispanic Chamber detection (AZ, Phoenix, East Valley) — STRONG bilingual signal
- [x] Generic Chamber of Commerce detection (Phoenix Valley chambers)
- [x] NFIB membership detection
- [x] Industry-specific: ACCA, PHCC, NAIFA, NPMA, SEIA, Trusted Choice, AAA
- [x] Wired into enrichment fact sheet
- [x] Updated scoring rubric: Bilingual gives 9-10 for Hispanic Chamber, Ease of Closing boosts for any association

## Phase 8: Scoring Rubric Recalibration (COMPLETE — 2026-05-23)
- [x] Expanded high-pain industry list (Insurance, Solar, Roofing, Restoration, Locksmith, etc.)
- [x] Recalibrated Tech Readiness thresholds (2 signals = 5-6, 3-4 = 7-8, 5+ = 9-10)
- [x] Removed "high review count = enterprise" penalty in Ease of Closing
- [x] Added rule: only treat as enterprise if multi-location/franchise signals visible

## Pending User Action
- [ ] Restart Streamlit to pick up 2026-05-23 changes
- [ ] Test "🔄 Re-research this business" on Parker & Sons
- [ ] Run bulk re-research on all unverified businesses
- [ ] Run a new "Run Deep Research" with the new 16×16 defaults
- [ ] Decide on Phase 6 Call Brief build
