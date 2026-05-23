# Ana Lead Tracker — Lessons Learned

(newest first)

## 2026-05-23: Default lists need to be audited against the actual proof points
Research config originally had 8 industries but didn't include Insurance Agencies — yet Ricardo Diaz Insurance is our ONLY live client and entire sales proof point. Lesson: when defining "ideal customer profile" defaults, start from "who already bought" and work outward. The flagship customer's industry should never be missing from the search list.

## 2026-05-23: Generic Apify queries pull garbage
"Medical" and "Legal" as Apify search terms returned random clinics and big law firms — not the sub-verticals Ana actually sells well to. Built `INDUSTRY_QUERY_MAP` to translate display names to specific search keywords ("Immigration Law" → "immigration lawyer", "Bail Bonds" → "bail bonds agent"). Future industries added to the default list must also get a mapping or fall back to a generic lowercased version.

## 2026-05-23: Pre-filter saves credits AND improves quality
Adding `min_reviews`, `max_reviews`, `require_website`, `require_phone` filters BEFORE Claude sees candidates drops 30-50% of obvious bad fits. This saves Apify credits AND keeps Claude focused on real prospects. Default thresholds should match the customer profile: <20 reviews = too new, >5000 = enterprise outside Ana's $20K-$50K sweet spot.

## 2026-05-22: Six scoring criteria need six data sources
Original scoring rubric had 6 criteria but the research pipeline only collected 3 data points (industry name, city, Google star rating). All 6 scores were therefore inference from the same minimal signal. **Fix:** rebuilt with `enrichment.py` that fetches website HTML + 30 reviews per business, so each criterion now scores from real observable signals. If you add a new criterion, you must also extend the signal extractors.

## 2026-05-22: "Run Deep Research" doesn't update existing businesses
The save loop deliberately skips businesses whose name already exists (`if biz["name"].lower() in existing_names: continue`). This is to preserve call notes / status / partner edits. **Implication:** to upgrade scores on existing businesses, use the per-business "Re-research this business" or the bulk Settings button — both call `_rescore_single_business()` which does UPDATE not INSERT.

## 2026-05-22: Apify's `totalScore` is the star rating, not the review count
We were storing `totalScore` (e.g., 4.5) into `google_reviews` thinking it was the count. The actual count is `reviewsCount`. **Fix:** the new pipeline captures both — `reviewsCount` for the real volume signal, `totalScore` for the rating.

## 2026-05-22: Streamlit Cloud cannot run Claude Code CLI / Agent SDK
Both partners have Claude Max subscriptions and run the app locally for free Claude inference. Streamlit Cloud serves as a read-only fallback — Claude-powered features (Generate Script, Run Deep Research) degrade there because the CLI isn't installed and `ANTHROPIC_API_KEY` is deliberately not set to avoid charges.

## 2026-05-22: Mojibake from prior insertion
Original seed data was inserted with a UTF-8 → Windows-1252 encoding mismatch, leaving `‚Äî` instead of `—` in 10 objection records (both EN and ES fields). **Fix:** `text.encode('cp1252').decode('utf-8')` round-trip on the corrupted strings. When ingesting seed text via SQL Editor copy-paste, verify a sample row before assuming the load was clean.

## 2026-05-22: Don't trust task files — read the code
Reported "Phase 2 incomplete" based on `todo.md` when the entire Sales Engine was already shipped and running. Josue: "seems like you lost memory." Stale docs lag the codebase. Always verify with the actual code and database before briefing.

## 2026-05-22: Seed data needs to be marked as such
20 hardcoded "Phoenix prospects" had no `last_research_run_id` and no `enrichment_completed_at`. Josue caught this when asking where Parker & Sons' 9.6 came from. **Fix:** Lead Detail page now shows a data-provenance badge (✅ Evidence-backed / ℹ️ Researched / ⚠️ Seed-data) so it's never ambiguous again.
