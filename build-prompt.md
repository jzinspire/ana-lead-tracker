# Ana Lead Tracker — Master Build Prompt

Copy everything below the line into a fresh Claude Code session opened from `~/dev/ana-lead-tracker/`.

---

You are an expert at building simple but powerful sales tools. Read the CLAUDE.md in this repo first — it has all the project rules, stack constraints, and scoring criteria.

Build a clean, effective lead tracking system called "Ana Lead Tracker" using **Streamlit + Supabase**.

## What this tool does

This is an internal sales tool for Itxaz. We sell Ana Receptionist (an AI voice receptionist for SMBs). This tool helps us find, score, and track the best-fit prospects in the Phoenix metro area so we can call them efficiently.

## Key Requirements

1. **On-demand deep research.** When the user clicks "Run Weekly Deep Research" (or "Run Daily"), the system should:
   - Pull fresh candidate businesses from reliable sources (Google Maps, Yelp, job boards, etc.) using Apify or similar
   - Send the data to Claude (Anthropic API, Sonnet 4) for deep analysis and scoring
   - Generate a new Top 50 ranked list with clear scores and explanations
   - Save the new list and update the database
   - Use prompt caching on the scoring system prompt for efficiency

2. **Scoring system** — six criteria, each 1-10:
   - **Call Volume** — how many inbound calls the business handles daily
   - **Missed Call Pain** — how much they lose from missed/abandoned calls
   - **Bilingual Opportunity** — whether they serve Spanish-speaking customers
   - **Tech Readiness** — existing tech stack + willingness to adopt AI
   - **Ease of Closing** — decision-maker accessibility, budget signals, buying readiness
   - **Urgency** — time-sensitive pain (seasonal, growth, staff turnover)
   - Overall score = weighted average (default weights equal; adjustable in settings)

3. **Feedback loop.** Users update statuses and add notes/feedback after calls. The system stores this feedback and uses it to improve future research and scoring over time.

4. **UI: clean, fast, simple** — focused on daily calling efficiency. No over-engineering.

## Main Features

- **Dashboard** with current Top 50
- **"Run Deep Research" button** (weekly or daily option)
- **All Businesses table** (searchable + filterable by industry, city, status, score range)
- **Lead Detail page** with score breakdown, call history, notes, and personalized call script
- **Status tracking** using these exact statuses:
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
- **CSV Export**
- **Settings page** (research frequency, scoring weights)

## Database

Use Supabase with minimal, clean tables. Design for:
- Businesses (with all scoring fields)
- Research runs (history of each research execution)
- Call history / notes (per business)
- Settings (scoring weights, research config)

Soft-delete only — never hard-delete lead data.

## Output order

1. First: complete Supabase database schema (SQL) — I'll run this in Supabase SQL editor
2. Then: full working Streamlit Python code
3. Then: clear setup instructions (local run + free deployment to Streamlit Community Cloud)
4. Make the Research feature practical and effective (Apify for collection, Claude for analysis)

## Seed Data

Pre-load these businesses with the scores shown. These are real Phoenix-area prospects already researched:

| Business Name | Industry | City | Website | Google Reviews | Overall Score | Key Evidence / Why High Fit | Initial Status |
|---|---|---|---|---|---|---|---|
| Parker & Sons | HVAC / Plumbing / Electrical | Phoenix metro | parkerandsons.com | 15,000+ | 9.6 | 50+ years, 24/7, massive volume, summer emergencies | Research Done |
| Chas Roberts | HVAC / Plumbing | Phoenix metro | chasroberts.com | Very High | 9.5 | Largest in AZ, 80+ years, 1M+ installs, 24/7 | Research Done |
| Goettl Air Conditioning | HVAC / Plumbing | Phoenix | goettl.com | High | 9.2 | Multiple locations, heavy local marketing | Research Done |
| Howard Air | HVAC / Plumbing | Phoenix | howardair.com | High | 9.0 | #1 on Angie's, long-established, high demand | Research Done |
| Way Cool Plumbing & Air | HVAC / Plumbing | Phoenix | callwaycool.com | Medium-High | 8.7 | 24/7 service, growing operation | Research Done |
| Anytime Dental Phoenix | Dental | Phoenix | anytimedentalphx.com | Medium | 9.1 | Extended hours, high new-patient demand | Research Done |
| Dental on Central | Dental (Multi-specialty) | Phoenix | dentaloncentral.com | Medium-High | 8.9 | 10,000+ patients, complex cases, high call volume | Research Done |
| S&L Dental | Dental | Phoenix area | (Yelp high volume) | 325+ | 8.5 | Busy practice with documented scheduling pressure | Research Done |
| Scott Roofing Company | Roofing | Phoenix | scottroofingco.com | High | 8.8 | 40+ years, 40,000+ customers, insurance claims | Research Done |
| Arizona Roofers | Roofing | Phoenix | arizonaroofers.com | High | 8.6 | Large crew, 1,000+ installs/year, storm surges | Research Done |
| Westridge Animal Hospital | Veterinary | Phoenix/Glendale/Peoria | wah.vet | Medium | 8.4 | Since 1982, multi-location, explicit high call volume | Research Done |
| Flush King Plumbing | Plumbing | Phoenix | (High Yelp) | High | 8.3 | Strong emergency 24/7 reputation | Research Done |
| Ideal Air Conditioning | HVAC | Phoenix | idealairaz.com | Medium | 8.5 | Growing, strong local reviews | Research Done |
| Desert Diamond Air | HVAC / Plumbing | Phoenix | desertdiamondhvac.com | Medium | 8.4 | Fast response focus, high urgency fit | Research Done |
| Robins Plumbing | Plumbing | Phoenix | robinsplumbing.com | Medium | 8.2 | Award-winning, hiring signals | Research Done |
| Platinum Plumbers | Plumbing | Phoenix | platinumplumbersaz.com | Medium | 8.1 | 23+ years, residential + commercial | Research Done |
| Radiant Smiles Phoenix | Dental | Phoenix | radiantsmilesphoenix.com | Medium | 8.3 | Flexible scheduling, busy patient flow | Research Done |
| Phoenix Arizona Dentistry | Dental | Phoenix | phoenixarizonadentistry.com | Medium | 8.0 | Weekend appointments, high demand | Research Done |
| SUNVEK Roofing | Roofing | Phoenix | sunvek.com | Medium | 8.2 | Long-established, strong reviews | Research Done |
| Mr. Rooter of Phoenix | Plumbing | Phoenix | mrrooter.com/phoenix | High | 8.0 | National brand with local volume | Research Done |
