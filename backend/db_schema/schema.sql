-- PortfolioNarrator — Supabase schema (10 tables)
-- Run this once in the Supabase SQL editor before rls.sql and seed.sql.

-- 1. Relationship Managers ─────────────────────────────────────────────
create table if not exists rms (
    id          uuid primary key default gen_random_uuid(),
    email       text unique not null,
    name        text not null,
    firm_name   text,
    designation text default 'Relationship Manager',
    phone       text,
    created_at  timestamptz default now()
);

-- 2. HNI Clients (full PMS profile) ────────────────────────────────────
create table if not exists clients (
    id                   uuid primary key default gen_random_uuid(),
    rm_id                uuid references rms(id) on delete cascade,
    -- Personal
    name                 text not null,
    pan_last4            text,
    dob                  date,
    client_since         date,
    -- Financial profile
    aum_cr               numeric(10,2),
    risk_profile         text,
    investment_horizon   text,
    liquidity_need_pct   numeric(5,2),
    income_need_monthly  numeric(12,2),
    tax_bracket          text,
    -- Communication
    language_pref        text default 'english',
    tone_pref            text default 'warm',
    -- Relationship
    next_review_date     date,
    last_meeting_date    date,
    last_meeting_notes   text,
    referral_source      text,
    rm_phone             text,
    rm_email             text,
    created_at           timestamptz default now()
);

-- 3. Portfolio Holdings ────────────────────────────────────────────────
create table if not exists portfolios (
    id                   uuid primary key default gen_random_uuid(),
    client_id            uuid references clients(id) on delete cascade,
    holdings             jsonb not null,
    benchmark            text default 'NIFTY50',
    inception_date       date,
    inception_return     numeric(8,4),
    xirr                 numeric(8,4),
    sharpe_ratio         numeric(6,4),
    max_drawdown         numeric(8,4),
    fees_this_quarter    numeric(12,2),
    fees_since_inception numeric(12,2),
    updated_at           timestamptz default now()
);

-- 4. Transaction History ───────────────────────────────────────────────
create table if not exists transactions (
    id          uuid primary key default gen_random_uuid(),
    client_id   uuid references clients(id) on delete cascade,
    txn_type    text,
    ticker      text,
    isin        text,
    quantity    numeric,
    price       numeric(12,2),
    total_value numeric(14,2),
    txn_date    date,
    rationale   text,
    executed_by text,
    created_at  timestamptz default now()
);

-- 5. Daily News Headlines ──────────────────────────────────────────────
create table if not exists daily_news (
    id          uuid primary key default gen_random_uuid(),
    date        date not null,
    category    text not null,
    headline    text not null,
    summary     text,
    source      text,
    created_at  timestamptz default now()
);
create index if not exists idx_daily_news_date on daily_news(date);
create index if not exists idx_daily_news_category on daily_news(category);

-- 6. Weekly AI Summaries ───────────────────────────────────────────────
create table if not exists weekly_summaries (
    id          uuid primary key default gen_random_uuid(),
    week_start  date not null,
    week_end    date not null,
    summaries   jsonb not null,
    created_at  timestamptz default now()
);
create index if not exists idx_weekly_summaries_week
    on weekly_summaries(week_start);

-- 7. Generated Reports ─────────────────────────────────────────────────
create table if not exists reports (
    id              uuid primary key default gen_random_uuid(),
    client_id       uuid references clients(id) on delete cascade,
    month           text not null,
    generated_text  text,
    hindi_text      text,
    qa_score        integer,
    pdf_url         text,
    created_at      timestamptz default now()
);
create index if not exists idx_reports_client_id on reports(client_id);
create index if not exists idx_reports_month on reports(month);

-- 8. Price Cache ───────────────────────────────────────────────────────
create table if not exists price_cache (
    ticker      text primary key,
    price       numeric(12,2),
    change_pct  numeric(8,4),
    fetched_at  timestamptz default now()
);

-- 9. Error Logs ────────────────────────────────────────────────────────
create table if not exists error_logs (
    id          uuid primary key default gen_random_uuid(),
    job         text not null,
    error       text not null,
    context     jsonb default '{}',
    timestamp   timestamptz default now()
);
create index if not exists idx_error_logs_timestamp
    on error_logs(timestamp desc);

-- 10. Job Run Log ──────────────────────────────────────────────────────
create table if not exists job_runs (
    id          uuid primary key default gen_random_uuid(),
    job_name    text not null,
    status      text,
    records     integer,
    duration_ms integer,
    run_at      timestamptz default now()
);
create index if not exists idx_job_runs_run_at on job_runs(run_at desc);
