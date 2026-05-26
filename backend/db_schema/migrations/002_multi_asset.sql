-- Phase 1: Multi-asset data model (10 new tables).
-- Apply AFTER schema.sql, rls.sql, seed.sql. Wraps everything in one transaction.
-- Column names MUST match those used in:
--   backend/models/wealth.py             (Task 3)
--   backend/db/*_db.py                   (Task 4)
--   backend/services/valuators/*         (Tasks 5-8)
--   backend/services/wealth_aggregator.py (Task 11)
--   backend/db_schema/seed_v2.sql        (Task 13)
begin;

-- 1. Mutual fund holdings ─────────────────────────────────────────────
create table if not exists mutual_funds (
    id             uuid primary key default gen_random_uuid(),
    client_id      uuid not null references clients(id) on delete cascade,
    scheme_code    text not null,
    scheme_name    text not null,
    amc            text,
    category       text check (category in ('equity','debt','hybrid','liquid')),
    sub_category   text,
    units          numeric(18,4) not null,
    purchase_nav   numeric(12,4) not null,
    purchase_date  date not null,
    created_at     timestamptz default now()
);
create index if not exists idx_mutual_funds_client on mutual_funds(client_id);
create index if not exists idx_mutual_funds_scheme on mutual_funds(scheme_code);

-- 2. Bond holdings ───────────────────────────────────────────────────
create table if not exists bonds (
    id                 uuid primary key default gen_random_uuid(),
    client_id          uuid not null references clients(id) on delete cascade,
    isin               text not null,
    issuer             text not null,
    bond_type          text not null check (bond_type in ('gsec','corporate','tax_free','perpetual')),
    face_value         numeric(12,2) not null,
    units              numeric(14,2) not null,
    coupon_pct         numeric(6,4) not null,
    payment_frequency  integer not null default 1 check (payment_frequency in (1,2,4)),
    purchase_price     numeric(12,2) not null,
    maturity_date      date,
    credit_rating      text,
    credit_spread_bps  integer default 0,
    purchase_date      date not null,
    created_at         timestamptz default now()
);
create index if not exists idx_bonds_client on bonds(client_id);
create index if not exists idx_bonds_isin on bonds(isin);

-- 3. Gold holdings ───────────────────────────────────────────────────
create table if not exists gold_holdings (
    id                       uuid primary key default gen_random_uuid(),
    client_id                uuid not null references clients(id) on delete cascade,
    form                     text not null check (form in ('physical','sgb','etf','fund')),
    weight_grams             numeric(10,4) not null,
    purity                   text not null check (purity in ('999','916')),
    purchase_price_per_gram  numeric(10,2) not null,
    purchase_date            date not null,
    created_at               timestamptz default now()
);
create index if not exists idx_gold_client on gold_holdings(client_id);

-- 4. Cash balances ───────────────────────────────────────────────────
create table if not exists cash_balances (
    id            uuid primary key default gen_random_uuid(),
    client_id     uuid not null references clients(id) on delete cascade,
    account_type  text not null check (account_type in ('savings','sweep','current')),
    bank          text not null,
    balance       numeric(14,2) not null,
    created_at    timestamptz default now()
);
create index if not exists idx_cash_client on cash_balances(client_id);

-- 5. Fixed deposits ──────────────────────────────────────────────────
create table if not exists fixed_deposits (
    id             uuid primary key default gen_random_uuid(),
    client_id      uuid not null references clients(id) on delete cascade,
    bank           text not null,
    principal      numeric(14,2) not null,
    rate_pct       numeric(6,4) not null,
    start_date     date not null,
    maturity_date  date not null,
    compounding    text not null check (compounding in ('simple','daily','monthly','quarterly','annual')),
    created_at     timestamptz default now()
);
create index if not exists idx_fds_client on fixed_deposits(client_id);

-- 6. Insurance policies ──────────────────────────────────────────────
create table if not exists insurance_policies (
    id                 uuid primary key default gen_random_uuid(),
    client_id          uuid not null references clients(id) on delete cascade,
    policy_type        text not null check (policy_type in ('term','endowment','ulip','health','whole_life','annuity','money_back')),
    insurer            text not null,
    sum_assured        numeric(14,2) not null,
    premium_amount     numeric(12,2) not null,
    premium_frequency  text not null check (premium_frequency in ('monthly','quarterly','semiannual','annual','single')),
    start_date         date not null,
    maturity_date      date,
    created_at         timestamptz default now()
);
create index if not exists idx_insurance_client on insurance_policies(client_id);

-- 7. Liabilities ─────────────────────────────────────────────────────
create table if not exists liabilities (
    id               uuid primary key default gen_random_uuid(),
    client_id        uuid not null references clients(id) on delete cascade,
    loan_type        text not null check (loan_type in ('home','car','personal','credit_card','loan_against_securities')),
    lender           text not null,
    original_amount  numeric(14,2) not null,
    rate_pct         numeric(6,4) not null,
    tenor_months     integer not null,
    emi              numeric(12,2),
    start_date       date not null,
    created_at       timestamptz default now()
);
create index if not exists idx_liabilities_client on liabilities(client_id);

-- 8. Market yields (support) — keyed by curve+tenor, idempotent upserts
create table if not exists market_yields (
    curve        text not null,
    tenor_years  numeric(5,2) not null,
    yield_pct    numeric(6,4) not null,
    as_of_date   date not null,
    primary key (curve, tenor_years)
);

-- 9. NAV cache (support) — one row per scheme_code ───────────────────
create table if not exists nav_cache (
    scheme_code  text primary key,
    amc          text,
    scheme_name  text,
    nav          numeric(12,4) not null,
    nav_date     date not null,
    fetched_at   timestamptz default now()
);

-- 10. Gold price cache (support) — many rows; latest by fetched_at ───
create table if not exists gold_price_cache (
    id              uuid primary key default gen_random_uuid(),
    purity          text not null check (purity in ('999','916')),
    price_per_gram  numeric(10,2) not null,
    source          text not null,
    fetched_at      timestamptz default now()
);
create index if not exists idx_gold_cache_purity_time
    on gold_price_cache(purity, fetched_at desc);

-- RLS — client-scoped tables filter by rm_id chain via clients
alter table mutual_funds      enable row level security;
alter table bonds             enable row level security;
alter table gold_holdings     enable row level security;
alter table cash_balances     enable row level security;
alter table fixed_deposits    enable row level security;
alter table insurance_policies enable row level security;
alter table liabilities       enable row level security;

-- Policies: RM can see/modify rows for clients they own.
-- (Mirrors the pattern in rls.sql for portfolios/transactions.)
create policy mf_rm_select on mutual_funds for select using (
    exists (select 1 from clients c where c.id = mutual_funds.client_id and c.rm_id = auth.uid())
);
create policy mf_rm_modify on mutual_funds for all using (
    exists (select 1 from clients c where c.id = mutual_funds.client_id and c.rm_id = auth.uid())
);
create policy bond_rm_select on bonds for select using (
    exists (select 1 from clients c where c.id = bonds.client_id and c.rm_id = auth.uid())
);
create policy bond_rm_modify on bonds for all using (
    exists (select 1 from clients c where c.id = bonds.client_id and c.rm_id = auth.uid())
);
create policy gold_rm_select on gold_holdings for select using (
    exists (select 1 from clients c where c.id = gold_holdings.client_id and c.rm_id = auth.uid())
);
create policy gold_rm_modify on gold_holdings for all using (
    exists (select 1 from clients c where c.id = gold_holdings.client_id and c.rm_id = auth.uid())
);
create policy cash_rm_select on cash_balances for select using (
    exists (select 1 from clients c where c.id = cash_balances.client_id and c.rm_id = auth.uid())
);
create policy cash_rm_modify on cash_balances for all using (
    exists (select 1 from clients c where c.id = cash_balances.client_id and c.rm_id = auth.uid())
);
create policy fd_rm_select on fixed_deposits for select using (
    exists (select 1 from clients c where c.id = fixed_deposits.client_id and c.rm_id = auth.uid())
);
create policy fd_rm_modify on fixed_deposits for all using (
    exists (select 1 from clients c where c.id = fixed_deposits.client_id and c.rm_id = auth.uid())
);
create policy ins_rm_select on insurance_policies for select using (
    exists (select 1 from clients c where c.id = insurance_policies.client_id and c.rm_id = auth.uid())
);
create policy ins_rm_modify on insurance_policies for all using (
    exists (select 1 from clients c where c.id = insurance_policies.client_id and c.rm_id = auth.uid())
);
create policy liab_rm_select on liabilities for select using (
    exists (select 1 from clients c where c.id = liabilities.client_id and c.rm_id = auth.uid())
);
create policy liab_rm_modify on liabilities for all using (
    exists (select 1 from clients c where c.id = liabilities.client_id and c.rm_id = auth.uid())
);

-- Support tables: read-public, write only via service_role
alter table market_yields    enable row level security;
alter table nav_cache        enable row level security;
alter table gold_price_cache enable row level security;
create policy yields_read    on market_yields    for select using (true);
create policy nav_read       on nav_cache        for select using (true);
create policy gold_read      on gold_price_cache for select using (true);

commit;
