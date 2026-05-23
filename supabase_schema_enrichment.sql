-- Ana Lead Tracker — Enrichment Schema (Module 3)
-- Adds per-criterion evidence + parsed signals so every score is backed
-- by real data, not just Claude's inference.
--
-- Run this in Supabase SQL Editor AFTER supabase_schema.sql and
-- supabase_schema_sales_engine.sql.
-- ============================================================

-- 1. Per-criterion evidence text (what data backed each score)
alter table businesses
    add column if not exists evidence_call_volume text,
    add column if not exists evidence_missed_call_pain text,
    add column if not exists evidence_bilingual text,
    add column if not exists evidence_tech_readiness text,
    add column if not exists evidence_ease_of_closing text,
    add column if not exists evidence_urgency text;

-- 2. Parsed signals (machine-readable, for re-analysis and transparency)
alter table businesses
    add column if not exists website_signals jsonb,
    add column if not exists review_signals jsonb,
    add column if not exists review_count integer,  -- real count, not avg rating
    add column if not exists enrichment_completed_at timestamptz;

-- 3. Index for filtering enriched vs seed businesses
create index if not exists idx_businesses_enriched
    on businesses(enrichment_completed_at)
    where enrichment_completed_at is not null;
