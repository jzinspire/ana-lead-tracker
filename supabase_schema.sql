-- ============================================================
-- Ana Lead Tracker — Supabase Schema
-- Run this in your Supabase SQL Editor (Dashboard > SQL Editor)
-- ============================================================

-- 1. SETTINGS TABLE
-- Stores scoring weights and research config as JSON
create table if not exists settings (
    id uuid default gen_random_uuid() primary key,
    key text unique not null,
    value jsonb not null,
    updated_at timestamptz default now()
);

-- 2. BUSINESSES TABLE
-- Core lead data with all scoring fields
create table if not exists businesses (
    id uuid default gen_random_uuid() primary key,
    name text not null,
    industry text,
    city text,
    state text default 'AZ',
    website text,
    phone text,
    email text,
    google_reviews text,
    yelp_url text,
    google_maps_url text,

    -- Scoring (each 1-10)
    score_call_volume numeric(3,1) default 0,
    score_missed_call_pain numeric(3,1) default 0,
    score_bilingual numeric(3,1) default 0,
    score_tech_readiness numeric(3,1) default 0,
    score_ease_of_closing numeric(3,1) default 0,
    score_urgency numeric(3,1) default 0,
    overall_score numeric(4,2) default 0,

    -- AI-generated analysis
    score_explanation text,
    key_evidence text,
    suggested_call_script text,

    -- Status tracking
    status text default 'New' check (status in (
        'New',
        'Research Done',
        'Call 1 Made',
        'Call 2 Made',
        'Call 3 Made',
        'Voicemail Left',
        'No Answer (3+ attempts)',
        'Interested - Demo Booked',
        'Not Interested',
        'Do Not Contact',
        'Closed Won',
        'Closed Lost'
    )),
    not_interested_reason text,

    -- Research metadata
    last_research_run_id uuid,
    research_data jsonb,
    data_source text,

    -- Soft delete
    archived boolean default false,

    -- Timestamps
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- 3. RESEARCH RUNS TABLE
-- History of each deep research execution
create table if not exists research_runs (
    id uuid default gen_random_uuid() primary key,
    run_type text default 'weekly' check (run_type in ('daily', 'weekly', 'manual')),
    status text default 'running' check (status in ('running', 'completed', 'failed')),
    industries_searched text[],
    cities_searched text[],
    total_candidates_found integer default 0,
    total_scored integer default 0,
    top_score numeric(4,2),
    avg_score numeric(4,2),
    model_used text default 'claude-sonnet-4-20250514',
    prompt_tokens_used integer,
    completion_tokens_used integer,
    cache_read_tokens integer,
    duration_seconds integer,
    error_message text,
    started_at timestamptz default now(),
    completed_at timestamptz
);

-- 4. CALL NOTES TABLE
-- Per-business call history and feedback
create table if not exists call_notes (
    id uuid default gen_random_uuid() primary key,
    business_id uuid not null references businesses(id) on delete cascade,
    note_type text default 'call' check (note_type in ('call', 'email', 'voicemail', 'research', 'internal')),
    content text not null,
    outcome text,
    contact_name text,
    contact_role text,
    next_action text,
    next_action_date date,
    -- Feedback for scoring improvement
    actual_call_volume_estimate text,
    actual_interest_level text check (actual_interest_level in ('very_high', 'high', 'medium', 'low', 'none', null)),
    scoring_feedback text,
    created_at timestamptz default now()
);

-- 5. INDEXES
create index if not exists idx_businesses_overall_score on businesses(overall_score desc);
create index if not exists idx_businesses_status on businesses(status);
create index if not exists idx_businesses_industry on businesses(industry);
create index if not exists idx_businesses_city on businesses(city);
create index if not exists idx_businesses_archived on businesses(archived);
create index if not exists idx_call_notes_business on call_notes(business_id);
create index if not exists idx_research_runs_started on research_runs(started_at desc);

-- 6. UPDATED_AT TRIGGER
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger businesses_updated_at
    before update on businesses
    for each row execute function update_updated_at();

create trigger settings_updated_at
    before update on settings
    for each row execute function update_updated_at();

-- 7. DEFAULT SETTINGS
insert into settings (key, value) values
    ('scoring_weights', '{
        "call_volume": 1.0,
        "missed_call_pain": 1.0,
        "bilingual": 1.0,
        "tech_readiness": 1.0,
        "ease_of_closing": 1.0,
        "urgency": 1.0
    }'::jsonb),
    ('research_config', '{
        "default_industries": ["HVAC", "Plumbing", "Dental", "Roofing", "Veterinary", "Legal", "Medical", "Auto Repair"],
        "default_cities": ["Phoenix", "Scottsdale", "Tempe", "Mesa", "Chandler", "Gilbert", "Glendale", "Peoria"],
        "max_candidates_per_run": 50,
        "min_google_reviews": 10,
        "research_frequency": "weekly"
    }'::jsonb)
on conflict (key) do nothing;

-- 8. SEED DATA — 20 pre-researched Phoenix-area prospects
insert into businesses (name, industry, city, website, google_reviews, overall_score,
    score_call_volume, score_missed_call_pain, score_bilingual, score_tech_readiness,
    score_ease_of_closing, score_urgency, key_evidence, status) values

('Parker & Sons', 'HVAC / Plumbing / Electrical', 'Phoenix metro', 'parkerandsons.com',
 '15,000+', 9.6, 10, 10, 9, 10, 9, 10,
 '50+ years in Phoenix, 24/7 emergency service, massive call volume, summer HVAC emergencies drive extreme phone traffic. 15K+ Google reviews indicate enormous customer base.',
 'Research Done'),

('Chas Roberts', 'HVAC / Plumbing', 'Phoenix metro', 'chasroberts.com',
 'Very High', 9.5, 10, 10, 9, 9, 9, 10,
 'Largest HVAC company in AZ, 80+ years in business, 1M+ installs. 24/7 service with massive inbound call volume. Legacy systems likely — high AI adoption potential.',
 'Research Done'),

('Goettl Air Conditioning', 'HVAC / Plumbing', 'Phoenix', 'goettl.com',
 'High', 9.2, 9, 9, 8, 9, 9, 10,
 'Multi-location across Phoenix metro. Heavy local TV/radio marketing drives high call volume. Summer surge creates missed-call pain.',
 'Research Done'),

('Howard Air', 'HVAC / Plumbing', 'Phoenix', 'howardair.com',
 'High', 9.0, 9, 9, 8, 9, 9, 8,
 '#1 on Angie''s List, long-established with strong reputation. High seasonal demand, likely overwhelmed phone lines during summer.',
 'Research Done'),

('Way Cool Plumbing & Air', 'HVAC / Plumbing', 'Phoenix', 'callwaycool.com',
 'Medium-High', 8.7, 8, 9, 8, 8, 9, 9,
 '24/7 emergency service, growing operation. Name/URL suggest phone-centric marketing. Growing fast — scaling pain likely.',
 'Research Done'),

('Anytime Dental Phoenix', 'Dental', 'Phoenix', 'anytimedentalphx.com',
 'Medium', 9.1, 9, 9, 9, 9, 9, 10,
 'Extended hours including evenings/weekends signals high demand. "Anytime" branding = phone-first patient acquisition. High new-patient volume.',
 'Research Done'),

('Dental on Central', 'Dental (Multi-specialty)', 'Phoenix', 'dentaloncentral.com',
 'Medium-High', 8.9, 9, 9, 8, 9, 8, 9,
 '10,000+ patients served, complex multi-specialty cases mean longer calls. High scheduling complexity = missed call opportunity.',
 'Research Done'),

('S&L Dental', 'Dental', 'Phoenix area', NULL,
 '325+', 8.5, 8, 8, 8, 8, 9, 8,
 'Busy practice with 325+ Yelp reviews (very high for dental). Documented scheduling pressure in reviews.',
 'Research Done'),

('Scott Roofing Company', 'Roofing', 'Phoenix', 'scottroofingco.com',
 'High', 8.8, 9, 9, 7, 8, 9, 9,
 '40+ years, 40,000+ customers served. Insurance claim work drives complex high-volume calls. Storm season = urgent phone traffic.',
 'Research Done'),

('Arizona Roofers', 'Roofing', 'Phoenix', 'arizonaroofers.com',
 'High', 8.6, 8, 9, 7, 8, 9, 9,
 'Large crew, 1,000+ installs/year. Monsoon storm surges create sudden call spikes they can''t staff for.',
 'Research Done'),

('Westridge Animal Hospital', 'Veterinary', 'Phoenix/Glendale/Peoria', 'wah.vet',
 'Medium', 8.4, 8, 8, 7, 8, 8, 9,
 'Since 1982, multi-location practice. Website explicitly mentions high call volume. Vet clinics = emotional, high-urgency calls.',
 'Research Done'),

('Flush King Plumbing', 'Plumbing', 'Phoenix', NULL,
 'High', 8.3, 8, 8, 7, 8, 8, 9,
 'Strong emergency 24/7 reputation on Yelp. Emergency plumbing = can''t miss calls. Likely small team = phone bottleneck.',
 'Research Done'),

('Ideal Air Conditioning', 'HVAC', 'Phoenix', 'idealairaz.com',
 'Medium', 8.5, 8, 8, 8, 8, 9, 8,
 'Growing mid-size HVAC company with strong local reviews. Sweet spot for Ana — big enough to need it, small enough to close.',
 'Research Done'),

('Desert Diamond Air', 'HVAC / Plumbing', 'Phoenix', 'desertdiamondhvac.com',
 'Medium', 8.4, 8, 8, 7, 8, 9, 9,
 'Fast response focus in marketing. High urgency fit — emergency HVAC in Phoenix summer is life-safety.',
 'Research Done'),

('Robins Plumbing', 'Plumbing', 'Phoenix', 'robinsplumbing.com',
 'Medium', 8.2, 8, 8, 7, 8, 8, 8,
 'Award-winning plumber with active hiring signals. Hiring = growth = scaling pain = missed calls.',
 'Research Done'),

('Platinum Plumbers', 'Plumbing', 'Phoenix', 'platinumplumbersaz.com',
 'Medium', 8.1, 8, 8, 7, 7, 8, 8,
 '23+ years, residential + commercial. Dual market means complex scheduling needs.',
 'Research Done'),

('Radiant Smiles Phoenix', 'Dental', 'Phoenix', 'radiantsmilesphoenix.com',
 'Medium', 8.3, 8, 8, 8, 8, 8, 8,
 'Flexible scheduling model signals high patient demand. Active new-patient acquisition.',
 'Research Done'),

('Phoenix Arizona Dentistry', 'Dental', 'Phoenix', 'phoenixarizonadentistry.com',
 'Medium', 8.0, 8, 8, 7, 8, 8, 8,
 'Weekend appointment availability = high demand overflow. Phone-first booking model.',
 'Research Done'),

('SUNVEK Roofing', 'Roofing', 'Phoenix', 'sunvek.com',
 'Medium', 8.2, 8, 8, 7, 8, 8, 8,
 'Long-established with strong review profile. Storm damage work = urgent inbound calls.',
 'Research Done'),

('Mr. Rooter of Phoenix', 'Plumbing', 'Phoenix', 'mrrooter.com/phoenix',
 'High', 8.0, 8, 8, 7, 7, 8, 8,
 'National franchise brand with local volume. Franchise = standardized ops = easier AI integration pitch.',
 'Research Done');
