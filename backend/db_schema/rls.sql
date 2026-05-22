-- PortfolioNarrator — Row Level Security policies
-- Run after schema.sql.

-- ─── Clients: each RM sees only their own ─────────────────────────────
alter table clients enable row level security;

drop policy if exists "RMs see own clients" on clients;
create policy "RMs see own clients" on clients
    for all
    using (rm_id = auth.uid());

-- ─── Portfolios: through client ownership ─────────────────────────────
alter table portfolios enable row level security;

drop policy if exists "RMs see own portfolios" on portfolios;
create policy "RMs see own portfolios" on portfolios
    for all
    using (
        client_id in (
            select id from clients where rm_id = auth.uid()
        )
    );

-- ─── Transactions: same as portfolios ─────────────────────────────────
alter table transactions enable row level security;

drop policy if exists "RMs see own transactions" on transactions;
create policy "RMs see own transactions" on transactions
    for all
    using (
        client_id in (
            select id from clients where rm_id = auth.uid()
        )
    );

-- ─── Reports: same as portfolios ──────────────────────────────────────
alter table reports enable row level security;

drop policy if exists "RMs see own reports" on reports;
create policy "RMs see own reports" on reports
    for all
    using (
        client_id in (
            select id from clients where rm_id = auth.uid()
        )
    );

-- ─── News + summaries: public read (no PII) ───────────────────────────
alter table daily_news enable row level security;

drop policy if exists "Public read daily_news" on daily_news;
create policy "Public read daily_news" on daily_news
    for select
    using (true);

alter table weekly_summaries enable row level security;

drop policy if exists "Public read weekly_summaries" on weekly_summaries;
create policy "Public read weekly_summaries" on weekly_summaries
    for select
    using (true);

-- price_cache, error_logs, job_runs, rms — server-only (service key
-- bypasses RLS), no policies needed for the demo build.
