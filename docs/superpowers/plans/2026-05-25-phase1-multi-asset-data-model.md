# Phase 1 — Multi-Asset Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 10 new tables (7 client-scoped + 3 support), 6 valuation services, 2 data fetchers, a wealth aggregator, and synthetic seed for 5 demo clients — without touching `prompt_builder`, `context_builder`, or any frontend file.

**Architecture:** Migration introduces tables and RLS. Each table gets a thin CRUD module in `backend/db/` and a Pydantic model. Per-asset-class valuators (pure math) + two HTTP fetchers (AMFI NAVs + IBJA gold) populate current values. `wealth_aggregator` is the single consumer-facing entry point that returns a `WealthSnapshot` for Phase 2/3.

**Tech Stack:** Python 3.11, FastAPI, Supabase Postgres, pytest, `httpx`, `pydantic` v2.

**Spec:** `docs/superpowers/specs/2026-05-25-multi-asset-data-model-design.md`

**Branch:** `phase1-multi-asset-data-model` (already created off `main`).

---

## Open questions resolved before planning

1. **Gold source** — IBJA daily rate scraped from `https://ibja.co/` (morning AM rate, fine gold 999). Falls back to last cached value tagged `cached`, then to a hardcoded `STATIC_FALLBACK_PRICE_PER_GRAM_INR` constant tagged `unavailable`. No API key needed.
2. **`nav_cache` history** — Single row per `scheme_code` (overwritten on refresh).
3. **Endowment surrender factor** — Piecewise schedule: years < 3 → 0; year ≥ 3 → `min(0.90, 0.30 + 0.05 × (years − 3))`. Applied to total premiums paid.

---

## File structure

**New files (30):**

```
backend/db_schema/migrations/002_multi_asset.sql
backend/db_schema/migrations/002_multi_asset_rollback.sql
backend/db_schema/seed_v2.sql
backend/db_schema/README.md
backend/db/mutual_funds_db.py
backend/db/bonds_db.py
backend/db/gold_db.py
backend/db/cash_db.py
backend/db/fds_db.py
backend/db/insurance_db.py
backend/db/liabilities_db.py
backend/db/market_yields_db.py
backend/db/nav_cache_db.py
backend/db/gold_price_cache_db.py
backend/models/wealth.py
backend/services/amfi_nav_fetcher.py
backend/services/gold_price_fetcher.py
backend/services/bond_pricer.py
backend/services/fd_valuator.py
backend/services/insurance_valuator.py
backend/services/liability_valuator.py
backend/services/wealth_aggregator.py
backend/tests/test_fd_valuator.py
backend/tests/test_liability_valuator.py
backend/tests/test_bond_pricer.py
backend/tests/test_insurance_valuator.py
backend/tests/test_amfi_fetcher.py
backend/tests/test_gold_fetcher.py
backend/tests/test_wealth_aggregator.py
backend/tests/fixtures/amfi_navall_sample.txt
backend/tests/fixtures/ibja_rate_sample.html
```

**Modified files (2):**

```
backend/routes/jobs.py     (+3 endpoints: refresh-nav, refresh-gold, refresh-yields)
CLAUDE.md                  (+ Phase 1 Architecture subsection)
```

---

Implementation order is strict: migration first, then CRUD + models, then valuators (each TDD), then fetchers (mocked TDD), then aggregator (TDD), then cron routes, then seed, then verification, then docs.

---

### Task 1: Migration SQL + rollback

**Files:**
- Create: `backend/db_schema/migrations/002_multi_asset.sql`
- Create: `backend/db_schema/migrations/002_multi_asset_rollback.sql`

- [ ] **Step 1: Create the migrations directory and migration file**

Create `backend/db_schema/migrations/002_multi_asset.sql`:

```sql
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
```

- [ ] **Step 2: Create the rollback file**

Create `backend/db_schema/migrations/002_multi_asset_rollback.sql`:

```sql
-- Rollback for 002_multi_asset.sql. Drops in reverse dependency order.
begin;
drop table if exists gold_price_cache cascade;
drop table if exists nav_cache cascade;
drop table if exists market_yields cascade;
drop table if exists liabilities cascade;
drop table if exists insurance_policies cascade;
drop table if exists fixed_deposits cascade;
drop table if exists cash_balances cascade;
drop table if exists gold_holdings cascade;
drop table if exists bonds cascade;
drop table if exists mutual_funds cascade;
commit;
```

- [ ] **Step 3: Apply migration to local/dev Supabase and verify**

Run via Supabase SQL editor (or `psql` if local). Expected: all 10 tables created. Verify with:

```sql
select table_name from information_schema.tables
where table_schema = 'public'
  and table_name in ('mutual_funds','bonds','gold_holdings','cash_balances',
                     'fixed_deposits','insurance_policies','liabilities',
                     'market_yields','nav_cache','gold_price_cache');
```

Expected: 10 rows returned.

- [ ] **Step 4: Commit**

```bash
git add backend/db_schema/migrations/
git commit -m "feat(db): migration 002 — multi-asset tables, indexes, RLS"
```

---

### Task 2: DB README

**Files:**
- Create: `backend/db_schema/README.md`

- [ ] **Step 1: Write the README**

Create `backend/db_schema/README.md`:

```markdown
# Database schema

## Apply order (one-time bootstrap)

1. `schema.sql`             — base 10 tables
2. `rls.sql`                — base RLS policies
3. `seed.sql`               — 5 demo clients with equity holdings
4. `migrations/002_multi_asset.sql`  — Phase 1 multi-asset tables + RLS
5. `seed_v2.sql`            — Phase 1 multi-asset seed for the 5 demo clients

## Rollback

Each migration ships a `*_rollback.sql` for local dev safety only. Never run in production.

## Phase notes

- **Phase 1** (this commit): adds `mutual_funds`, `bonds`, `gold_holdings`, `cash_balances`, `fixed_deposits`, `insurance_policies`, `liabilities` + support tables `market_yields`, `nav_cache`, `gold_price_cache`. Consumer entry point is `backend/services/wealth_aggregator.py`.
- **Phase 2** (future): change-tracking model — wealth snapshots, allocation targets, rationale events.
- **Phase 3** (future): UI and report-content consumption of the wealth model.
```

- [ ] **Step 2: Commit**

```bash
git add backend/db_schema/README.md
git commit -m "docs(db): migration apply-order README"
```

---

### Task 3: Pydantic models for the new tables

**Files:**
- Create: `backend/models/wealth.py`

- [ ] **Step 1: Write the models file**

Create `backend/models/wealth.py`:

```python
"""Pydantic shapes for the Phase 1 multi-asset tables.

These are import-only for now (no routes use them yet). They exist so Phase 3
can build the wealth API surface without re-typing fields.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


SourceTag = Literal["live", "cached", "unavailable"]


class MutualFund(BaseModel):
    id: UUID
    client_id: UUID
    scheme_code: str
    scheme_name: str
    scheme_type: Literal["equity", "debt", "hybrid", "liquid"]
    units: float
    avg_cost_nav: float
    invested_amount: float
    sip_active: bool = False
    sip_amount: Optional[float] = None
    sip_start_date: Optional[date] = None
    current_nav: Optional[float] = None
    current_nav_date: Optional[date] = None
    source: SourceTag = "unavailable"
    created_at: datetime


class Bond(BaseModel):
    id: UUID
    client_id: UUID
    isin: str
    bond_name: str
    bond_type: Literal["gsec", "corp", "tax_free", "perpetual"]
    face_value: float
    units: float
    coupon_rate: float
    coupon_freq: Literal["annual", "semi"]
    maturity_date: Optional[date] = None
    purchase_date: date
    purchase_price: float
    current_price: Optional[float] = None
    current_price_date: Optional[date] = None
    source: SourceTag = "unavailable"
    created_at: datetime


class GoldHolding(BaseModel):
    id: UUID
    client_id: UUID
    gold_type: Literal["physical", "sgb", "etf", "fund"]
    grams: float
    purity: Optional[Literal["24k", "22k", "18k"]] = None
    purchase_date: date
    purchase_price_per_gram: float
    current_price_per_gram: Optional[float] = None
    current_price_date: Optional[date] = None
    source: SourceTag = "unavailable"
    created_at: datetime


class CashBalance(BaseModel):
    id: UUID
    client_id: UUID
    account_type: Literal["savings", "sweep", "current"]
    bank_name: str
    balance: float
    as_of_date: date
    created_at: datetime


class FixedDeposit(BaseModel):
    id: UUID
    client_id: UUID
    bank_name: str
    fd_number_last4: Optional[str] = None
    principal: float
    interest_rate: float
    compounding: Literal["simple", "monthly", "quarterly", "annual"]
    start_date: date
    maturity_date: date
    payout_type: Literal["cumulative", "payout"]
    created_at: datetime


class InsurancePolicy(BaseModel):
    id: UUID
    client_id: UUID
    policy_type: Literal["term", "endowment", "ulip", "health", "whole_life"]
    insurer: str
    policy_number_last4: Optional[str] = None
    sum_assured: float
    premium_amount: float
    premium_frequency: Literal["monthly", "quarterly", "annual"]
    policy_start_date: date
    maturity_date: Optional[date] = None
    surrender_value: Optional[float] = None
    current_nav: Optional[float] = None
    units: Optional[float] = None
    created_at: datetime


class Liability(BaseModel):
    id: UUID
    client_id: UUID
    loan_type: Literal["home", "car", "personal", "credit_card", "loan_against_securities"]
    lender: str
    sanctioned_amount: float
    interest_rate: float
    emi_amount: float
    tenure_months: int
    start_date: date
    created_at: datetime


class MarketYield(BaseModel):
    date: date
    tenor_years: int
    yield_pct: float


class NavCacheEntry(BaseModel):
    scheme_code: str
    nav: float
    nav_date: date
    fetched_at: datetime


class GoldPriceCacheEntry(BaseModel):
    gold_type: str
    price_per_gram: float
    source: SourceTag
    fetched_at: datetime


class AssetBucket(BaseModel):
    holdings: list = Field(default_factory=list)
    total_value: float = 0.0
    source_health: dict = Field(default_factory=dict)


class InsuranceBucket(BaseModel):
    holdings: list = Field(default_factory=list)
    total_surrender: float = 0.0
    total_sum_assured: float = 0.0


class LiabilityBucket(BaseModel):
    holdings: list = Field(default_factory=list)
    total_outstanding: float = 0.0


class WealthSnapshot(BaseModel):
    equity: AssetBucket
    mfs: AssetBucket
    bonds: AssetBucket
    gold: AssetBucket
    cash: AssetBucket
    fds: AssetBucket
    insurance: InsuranceBucket
    liabilities: LiabilityBucket
    net_worth: float
    asset_allocation: dict
    has_stale_values: bool
    stale_sources: list[str]
```

- [ ] **Step 2: Verify it imports without error**

Run: `python -c "from backend.models.wealth import WealthSnapshot; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/models/wealth.py
git commit -m "feat(models): pydantic shapes for multi-asset tables"
```

---

### Task 4: CRUD modules for the 10 new tables

**Files:**
- Create: `backend/db/mutual_funds_db.py`
- Create: `backend/db/bonds_db.py`
- Create: `backend/db/gold_db.py`
- Create: `backend/db/cash_db.py`
- Create: `backend/db/fds_db.py`
- Create: `backend/db/insurance_db.py`
- Create: `backend/db/liabilities_db.py`
- Create: `backend/db/market_yields_db.py`
- Create: `backend/db/nav_cache_db.py`
- Create: `backend/db/gold_price_cache_db.py`

All modules follow the same pattern as existing `backend/db/*` files: singleton client via `db/supabase_client.get_supabase()`, raise `RuntimeError` on connection failure, return plain dicts.

- [ ] **Step 1: Create `backend/db/mutual_funds_db.py`**

```python
"""CRUD for the mutual_funds table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_for_client(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("mutual_funds").select("*").eq("client_id", client_id).execute()
    return res.data or []


def insert(row: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("mutual_funds").insert(row).execute()
    return (res.data or [{}])[0]
```

- [ ] **Step 2: Create `backend/db/bonds_db.py`**

```python
"""CRUD for the bonds table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_for_client(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("bonds").select("*").eq("client_id", client_id).execute()
    return res.data or []


def insert(row: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("bonds").insert(row).execute()
    return (res.data or [{}])[0]
```

- [ ] **Step 3: Create `backend/db/gold_db.py`**

```python
"""CRUD for the gold_holdings table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_for_client(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("gold_holdings").select("*").eq("client_id", client_id).execute()
    return res.data or []


def insert(row: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("gold_holdings").insert(row).execute()
    return (res.data or [{}])[0]
```

- [ ] **Step 4: Create `backend/db/cash_db.py`**

```python
"""CRUD for the cash_balances table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_for_client(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("cash_balances").select("*").eq("client_id", client_id).execute()
    return res.data or []


def insert(row: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("cash_balances").insert(row).execute()
    return (res.data or [{}])[0]
```

- [ ] **Step 5: Create `backend/db/fds_db.py`**

```python
"""CRUD for the fixed_deposits table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_for_client(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("fixed_deposits").select("*").eq("client_id", client_id).execute()
    return res.data or []


def insert(row: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("fixed_deposits").insert(row).execute()
    return (res.data or [{}])[0]
```

- [ ] **Step 6: Create `backend/db/insurance_db.py`**

```python
"""CRUD for the insurance_policies table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_for_client(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("insurance_policies").select("*").eq("client_id", client_id).execute()
    return res.data or []


def insert(row: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("insurance_policies").insert(row).execute()
    return (res.data or [{}])[0]
```

- [ ] **Step 7: Create `backend/db/liabilities_db.py`**

```python
"""CRUD for the liabilities table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_for_client(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("liabilities").select("*").eq("client_id", client_id).execute()
    return res.data or []


def insert(row: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("liabilities").insert(row).execute()
    return (res.data or [{}])[0]
```

- [ ] **Step 8: Create `backend/db/market_yields_db.py`**

```python
"""CRUD for the market_yields support table (G-Sec yield curve)."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_curve(curve: str = "gsec") -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = (
        sb.table("market_yields")
        .select("*")
        .eq("curve", curve)
        .order("tenor_years")
        .execute()
    )
    return res.data or []


def upsert(rows: list[dict[str, Any]]) -> None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    sb.table("market_yields").upsert(rows, on_conflict="curve,tenor_years").execute()
```

- [ ] **Step 9: Create `backend/db/nav_cache_db.py`**

```python
"""CRUD for the nav_cache support table (single row per scheme_code)."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get(scheme_code: str) -> dict[str, Any] | None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("nav_cache").select("*").eq("scheme_code", scheme_code).limit(1).execute()
    return (res.data or [None])[0]


def upsert(rows: list[dict[str, Any]]) -> None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    sb.table("nav_cache").upsert(rows, on_conflict="scheme_code").execute()
```

- [ ] **Step 10: Create `backend/db/gold_price_cache_db.py`**

```python
"""CRUD for the gold_price_cache support table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_latest(purity: str = "999") -> dict[str, Any] | None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = (
        sb.table("gold_price_cache")
        .select("*")
        .eq("purity", purity)
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def insert(row: dict[str, Any]) -> None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    sb.table("gold_price_cache").insert(row).execute()
```

- [ ] **Step 11: Verify all modules import**

Run: `cd backend && python -c "from db import mutual_funds_db, bonds_db, gold_db, cash_db, fds_db, insurance_db, liabilities_db, market_yields_db, nav_cache_db, gold_price_cache_db; print('ok')"`
Expected: `ok`

- [ ] **Step 12: Commit**

```bash
git add backend/db/mutual_funds_db.py backend/db/bonds_db.py backend/db/gold_db.py \
        backend/db/cash_db.py backend/db/fds_db.py backend/db/insurance_db.py \
        backend/db/liabilities_db.py backend/db/market_yields_db.py \
        backend/db/nav_cache_db.py backend/db/gold_price_cache_db.py
git commit -m "feat(db): CRUD modules for 10 new multi-asset tables"
```

---

### Task 5: FD valuator (TDD)

**Files:**
- Create: `backend/services/valuators/__init__.py` (empty marker)
- Create: `backend/services/valuators/fd_valuator.py`
- Test: `backend/tests/test_fd_valuator.py`

Computes current value of a fixed deposit given principal, rate, start date, and compounding mode. Pure function — no I/O.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_fd_valuator.py`:
```python
from datetime import date
from services.valuators.fd_valuator import value_fd


def test_simple_interest():
    # 100000 @ 7% simple, 1 year
    v = value_fd(
        principal=100000.0,
        rate=0.07,
        start=date(2024, 1, 1),
        compounding="simple",
        as_of=date(2025, 1, 1),
    )
    assert round(v, 2) == 107000.00


def test_quarterly_compounding_one_year():
    # 100000 @ 8% quarterly for 1 year -> 100000 * (1.02)^4
    v = value_fd(
        principal=100000.0,
        rate=0.08,
        start=date(2024, 1, 1),
        compounding="quarterly",
        as_of=date(2025, 1, 1),
    )
    assert round(v, 2) == 108243.22


def test_monthly_compounding_two_years():
    v = value_fd(
        principal=50000.0,
        rate=0.06,
        start=date(2023, 1, 1),
        compounding="monthly",
        as_of=date(2025, 1, 1),
    )
    # 50000 * (1 + 0.06/12) ** 24
    assert round(v, 2) == 56357.50


def test_as_of_before_start_returns_principal():
    v = value_fd(
        principal=100000.0,
        rate=0.07,
        start=date(2025, 6, 1),
        compounding="annual",
        as_of=date(2025, 1, 1),
    )
    assert v == 100000.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_fd_valuator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.valuators'`

- [ ] **Step 3: Create the package marker**

`backend/services/valuators/__init__.py`:
```python
"""Pure valuation functions for non-market-quoted assets."""
```

- [ ] **Step 4: Implement the valuator**

`backend/services/valuators/fd_valuator.py`:
```python
"""Fixed-deposit current-value calculator."""
from __future__ import annotations
from datetime import date


_FREQ = {"simple": None, "annual": 1, "quarterly": 4, "monthly": 12, "daily": 365}


def value_fd(
    principal: float,
    rate: float,
    start: date,
    compounding: str,
    as_of: date,
) -> float:
    """Return the current value of an FD.

    Args:
        principal: deposit amount in INR
        rate: annual rate as a decimal (0.07 == 7%)
        start: deposit start date
        compounding: one of simple, annual, quarterly, monthly, daily
        as_of: valuation date
    """
    if as_of <= start:
        return float(principal)
    years = (as_of - start).days / 365.25
    if compounding == "simple":
        return float(principal * (1 + rate * years))
    n = _FREQ.get(compounding)
    if n is None:
        raise ValueError(f"unknown compounding: {compounding}")
    return float(principal * (1 + rate / n) ** (n * years))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_fd_valuator.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/services/valuators/__init__.py \
        backend/services/valuators/fd_valuator.py \
        backend/tests/test_fd_valuator.py
git commit -m "feat(valuators): FD compound-interest calculator"
```

---

### Task 6: Liability valuator (TDD)

**Files:**
- Create: `backend/services/valuators/liability_valuator.py`
- Test: `backend/tests/test_liability_valuator.py`

Standard loan amortization. Returns the outstanding balance as of a given date given principal, rate, tenor (months), start date, and EMI. If EMI is None, derives EMI from the standard amortization formula.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_liability_valuator.py`:
```python
from datetime import date
from services.valuators.liability_valuator import outstanding_balance, emi_for


def test_emi_derivation_round_loan():
    # 10L home loan, 8% p.a., 240 months
    emi = emi_for(principal=1_000_000.0, rate=0.08, months=240)
    # closed form: 1_000_000 * 0.08/12 * (1 + 0.08/12)^240 /
    #              ((1 + 0.08/12)^240 - 1) ≈ 8364.40
    assert round(emi, 2) == 8364.40


def test_outstanding_at_origination_equals_principal():
    bal = outstanding_balance(
        principal=1_000_000.0,
        rate=0.08,
        months=240,
        start=date(2025, 1, 1),
        as_of=date(2025, 1, 1),
        emi=None,
    )
    assert round(bal, 2) == 1_000_000.00


def test_outstanding_after_one_year():
    bal = outstanding_balance(
        principal=1_000_000.0,
        rate=0.08,
        months=240,
        start=date(2024, 1, 1),
        as_of=date(2025, 1, 1),
        emi=None,
    )
    # 12 payments in -> outstanding should be ~ 979_822
    assert 975_000 < bal < 985_000


def test_outstanding_after_full_tenor_is_zero():
    bal = outstanding_balance(
        principal=1_000_000.0,
        rate=0.08,
        months=240,
        start=date(2005, 1, 1),
        as_of=date(2025, 1, 1),
        emi=None,
    )
    assert round(bal, 2) == 0.00


def test_explicit_emi_overrides_derivation():
    bal = outstanding_balance(
        principal=1_000_000.0,
        rate=0.08,
        months=240,
        start=date(2024, 1, 1),
        as_of=date(2025, 1, 1),
        emi=10_000.0,
    )
    # higher EMI -> faster paydown than the round case
    assert bal < 979_822.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_liability_valuator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the valuator**

`backend/services/valuators/liability_valuator.py`:
```python
"""Loan / liability outstanding-balance calculator."""
from __future__ import annotations
from datetime import date


def emi_for(principal: float, rate: float, months: int) -> float:
    """Closed-form EMI for a standard amortising loan."""
    if rate == 0:
        return principal / months
    r = rate / 12.0
    factor = (1 + r) ** months
    return principal * r * factor / (factor - 1)


def _months_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month)


def outstanding_balance(
    principal: float,
    rate: float,
    months: int,
    start: date,
    as_of: date,
    emi: float | None = None,
) -> float:
    """Outstanding balance after k EMIs have been paid (k = months elapsed)."""
    if as_of <= start:
        return float(principal)
    k = min(_months_between(start, as_of), months)
    if k >= months:
        return 0.0
    pay = emi if emi is not None else emi_for(principal, rate, months)
    r = rate / 12.0
    if r == 0:
        return max(0.0, principal - pay * k)
    bal = principal * (1 + r) ** k - pay * (((1 + r) ** k - 1) / r)
    return max(0.0, float(bal))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_liability_valuator.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/valuators/liability_valuator.py \
        backend/tests/test_liability_valuator.py
git commit -m "feat(valuators): loan outstanding-balance calculator"
```

---

### Task 7: Bond pricer + market_yields integration (TDD)

**Files:**
- Create: `backend/services/valuators/bond_pricer.py`
- Test: `backend/tests/test_bond_pricer.py`

Discounts coupon and principal cashflows by the relevant tenor-matched G-Sec yield (plus an optional credit spread) and returns the dirty price plus current market value. The yield curve is provided as a list of `(tenor_years, yield_pct)` points — the function interpolates linearly.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_bond_pricer.py`:
```python
from datetime import date
from services.valuators.bond_pricer import price_bond, interpolate_yield


def test_yield_interpolation_midpoint():
    curve = [(1, 6.5), (5, 7.0), (10, 7.3)]
    # midway between 1y (6.5) and 5y (7.0) -> at 3y should be 6.75
    assert round(interpolate_yield(curve, 3.0), 4) == 6.75


def test_yield_interpolation_below_min_clamps():
    curve = [(1, 6.5), (5, 7.0)]
    assert interpolate_yield(curve, 0.5) == 6.5


def test_yield_interpolation_above_max_clamps():
    curve = [(1, 6.5), (5, 7.0)]
    assert interpolate_yield(curve, 30.0) == 7.0


def test_par_bond_prices_at_face():
    # 5y bond, 7% coupon, curve flat at 7%, no spread -> price ≈ face
    curve = [(1, 7.0), (5, 7.0), (10, 7.0)]
    px = price_bond(
        face=1000.0,
        coupon_pct=7.0,
        maturity=date(2030, 1, 1),
        as_of=date(2025, 1, 1),
        curve=curve,
        spread_bps=0,
        frequency=1,
    )
    assert 995.0 <= px <= 1005.0


def test_yield_above_coupon_prices_below_face():
    curve = [(1, 8.0), (5, 8.0), (10, 8.0)]
    px = price_bond(
        face=1000.0,
        coupon_pct=7.0,
        maturity=date(2030, 1, 1),
        as_of=date(2025, 1, 1),
        curve=curve,
        spread_bps=0,
        frequency=1,
    )
    assert px < 1000.0


def test_credit_spread_lowers_price():
    curve = [(1, 7.0), (5, 7.0), (10, 7.0)]
    base = price_bond(
        face=1000.0, coupon_pct=7.0, maturity=date(2030, 1, 1),
        as_of=date(2025, 1, 1), curve=curve, spread_bps=0, frequency=1,
    )
    with_spread = price_bond(
        face=1000.0, coupon_pct=7.0, maturity=date(2030, 1, 1),
        as_of=date(2025, 1, 1), curve=curve, spread_bps=200, frequency=1,
    )
    assert with_spread < base
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_bond_pricer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the pricer**

`backend/services/valuators/bond_pricer.py`:
```python
"""PV-of-cashflows bond pricer with linear-interpolated yield curve."""
from __future__ import annotations
from datetime import date


def interpolate_yield(curve: list[tuple[float, float]], tenor_years: float) -> float:
    """Linearly interpolate the yield curve at `tenor_years`.

    `curve` is a sorted list of (tenor_years, yield_pct).
    Clamps to the nearest endpoint outside the curve's range.
    """
    if not curve:
        raise ValueError("empty yield curve")
    pts = sorted(curve)
    if tenor_years <= pts[0][0]:
        return pts[0][1]
    if tenor_years >= pts[-1][0]:
        return pts[-1][1]
    for (t0, y0), (t1, y1) in zip(pts, pts[1:]):
        if t0 <= tenor_years <= t1:
            return y0 + (y1 - y0) * (tenor_years - t0) / (t1 - t0)
    return pts[-1][1]


def price_bond(
    face: float,
    coupon_pct: float,
    maturity: date,
    as_of: date,
    curve: list[tuple[float, float]],
    spread_bps: int = 0,
    frequency: int = 1,
) -> float:
    """Discounted-cashflow price for a vanilla coupon bond.

    Returns INR price for one unit of `face`.
    """
    years_to_maturity = (maturity - as_of).days / 365.25
    if years_to_maturity <= 0:
        return float(face)
    base_y = interpolate_yield(curve, years_to_maturity) / 100.0
    discount = base_y + spread_bps / 10_000.0
    coupon = face * coupon_pct / 100.0 / frequency
    periods = max(1, int(round(years_to_maturity * frequency)))
    r = discount / frequency
    pv = 0.0
    for k in range(1, periods + 1):
        pv += coupon / (1 + r) ** k
    pv += face / (1 + r) ** periods
    return float(pv)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_bond_pricer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/valuators/bond_pricer.py \
        backend/tests/test_bond_pricer.py
git commit -m "feat(valuators): YTM bond pricer with interpolated G-Sec curve"
```

---

### Task 8: Insurance valuator (TDD)

**Files:**
- Create: `backend/services/valuators/insurance_valuator.py`
- Test: `backend/tests/test_insurance_valuator.py`

For term plans, value = 0 (no surrender value). For endowment/ULIP/money-back, value = `min(0.90, 0.30 + 0.05 × (years_since_start − 3))` × cumulative premium paid, but 0 if years < 3 (typical lock-in).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_insurance_valuator.py`:
```python
from datetime import date
from services.valuators.insurance_valuator import surrender_value


def test_term_plan_always_zero():
    v = surrender_value(
        policy_type="term",
        premium_amount=50_000.0,
        premium_frequency="annual",
        start=date(2020, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert v == 0.0


def test_endowment_under_three_years_returns_zero():
    v = surrender_value(
        policy_type="endowment",
        premium_amount=100_000.0,
        premium_frequency="annual",
        start=date(2024, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert v == 0.0


def test_endowment_three_years_factor_thirty_pct():
    # 3 full years paid, factor = 0.30 + 0.05 * (3-3) = 0.30
    # premiums paid = 100k * 4 (years 0,1,2,3) = 400k
    # value = 0.30 * 400_000 = 120_000
    v = surrender_value(
        policy_type="endowment",
        premium_amount=100_000.0,
        premium_frequency="annual",
        start=date(2022, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert round(v, 2) == 120_000.00


def test_endowment_caps_at_ninety_pct():
    # 20 years in: factor = min(0.90, 0.30 + 0.05*17) = 0.90
    # premiums = 100k * 21 = 2_100_000; value = 0.90 * 2_100_000 = 1_890_000
    v = surrender_value(
        policy_type="endowment",
        premium_amount=100_000.0,
        premium_frequency="annual",
        start=date(2005, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert round(v, 2) == 1_890_000.00


def test_monthly_frequency_counts_payments_correctly():
    # 5 years monthly @ 5000 -> 60 payments paid by anniversary
    # factor at 5y = 0.30 + 0.05*2 = 0.40
    # value = 0.40 * 60 * 5000 = 120_000
    v = surrender_value(
        policy_type="endowment",
        premium_amount=5_000.0,
        premium_frequency="monthly",
        start=date(2020, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert round(v, 2) == 120_000.00
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_insurance_valuator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the valuator**

`backend/services/valuators/insurance_valuator.py`:
```python
"""Insurance policy surrender-value calculator."""
from __future__ import annotations
from datetime import date


_FREQ_PER_YEAR = {"annual": 1, "semiannual": 2, "quarterly": 4, "monthly": 12, "single": 1}


def _premiums_paid(
    premium_amount: float,
    frequency: str,
    start: date,
    as_of: date,
) -> float:
    if as_of < start:
        return 0.0
    if frequency == "single":
        return float(premium_amount)
    n = _FREQ_PER_YEAR.get(frequency)
    if n is None:
        raise ValueError(f"unknown frequency: {frequency}")
    years = (as_of - start).days / 365.25
    payments = int(years * n) + 1  # initial premium + n per year
    return float(premium_amount * payments)


def surrender_value(
    policy_type: str,
    premium_amount: float,
    premium_frequency: str,
    start: date,
    as_of: date,
) -> float:
    """Estimated surrender value.

    Term plans return 0. Endowment/ULIP/money-back use a piecewise factor:
        years < 3   -> 0
        years >= 3  -> min(0.90, 0.30 + 0.05 * (years - 3)) * premiums_paid
    """
    if policy_type == "term":
        return 0.0
    years = (as_of - start).days / 365.25
    if years < 3:
        return 0.0
    factor = min(0.90, 0.30 + 0.05 * (years - 3))
    paid = _premiums_paid(premium_amount, premium_frequency, start, as_of)
    return float(factor * paid)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_insurance_valuator.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/valuators/insurance_valuator.py \
        backend/tests/test_insurance_valuator.py
git commit -m "feat(valuators): endowment surrender-value schedule"
```

---

### Task 9: AMFI NAV fetcher (TDD with mocked HTTP)

**Files:**
- Create: `backend/services/feeds/__init__.py` (empty marker)
- Create: `backend/services/feeds/amfi_nav.py`
- Test: `backend/tests/test_amfi_nav.py`

Parses the daily pipe-delimited NAVAll.txt file from `https://www.amfiindia.com/spages/NAVAll.txt`. Tests mock `httpx.get` and assert parsing + upsert intent. The function returns the parsed rows; the caller (Task 12 cron) handles persisting to `nav_cache`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_amfi_nav.py`:
```python
from unittest.mock import patch, MagicMock
from services.feeds.amfi_nav import parse_navall, fetch_nav_rows


_SAMPLE = """\
Open Ended Schemes(Equity)

ICICI Prudential Mutual Fund

Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
120503;INF109K01Z48;INF109K01Z55;ICICI Prudential Bluechip Fund - Direct Plan - Growth;105.4321;25-May-2026
120601;INF109K01ABC;-;ICICI Prudential Value Discovery Fund - Direct Plan - Growth;88.1234;25-May-2026

Nippon India Mutual Fund

118989;INF204K01ZZ8;-;Nippon India Small Cap Fund - Direct Plan - Growth;195.7777;25-May-2026
"""


def test_parse_navall_extracts_scheme_rows_only():
    rows = parse_navall(_SAMPLE)
    codes = [r["scheme_code"] for r in rows]
    assert codes == ["120503", "120601", "118989"]


def test_parse_navall_captures_nav_and_date():
    rows = parse_navall(_SAMPLE)
    first = rows[0]
    assert first["scheme_code"] == "120503"
    assert first["nav"] == 105.4321
    assert first["nav_date"] == "2026-05-25"


def test_parse_navall_captures_amc_name():
    rows = parse_navall(_SAMPLE)
    assert rows[0]["amc"] == "ICICI Prudential Mutual Fund"
    assert rows[2]["amc"] == "Nippon India Mutual Fund"


def test_parse_navall_skips_blank_and_header_lines():
    rows = parse_navall(_SAMPLE)
    assert all("Scheme Code" not in r["scheme_name"] for r in rows)
    assert all(r["scheme_name"].strip() for r in rows)


def test_fetch_nav_rows_uses_mocked_http():
    fake = MagicMock()
    fake.text = _SAMPLE
    fake.status_code = 200
    with patch("services.feeds.amfi_nav.httpx.get", return_value=fake) as m:
        rows = fetch_nav_rows()
    m.assert_called_once()
    assert len(rows) == 3
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_amfi_nav.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create the package marker**

`backend/services/feeds/__init__.py`:
```python
"""External market-data fetchers."""
```

- [ ] **Step 4: Implement the fetcher**

`backend/services/feeds/amfi_nav.py`:
```python
"""AMFI India daily NAV file parser and fetcher."""
from __future__ import annotations
from datetime import datetime
import httpx


AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def _parse_date(s: str) -> str:
    return datetime.strptime(s.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")


def parse_navall(text: str) -> list[dict]:
    """Parse the AMFI NAVAll.txt body into scheme rows.

    The file is pipe (`;`)-separated with AMC names appearing as bare lines
    between scheme blocks. Blank lines, schema headers, and section titles
    are skipped.
    """
    rows: list[dict] = []
    current_amc: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ";" not in line:
            if line.startswith("Open Ended") or line.startswith("Close Ended"):
                continue
            current_amc = line
            continue
        parts = line.split(";")
        if len(parts) < 6 or parts[0].strip().lower() == "scheme code":
            continue
        code = parts[0].strip()
        if not code.isdigit():
            continue
        try:
            nav = float(parts[4].strip())
        except ValueError:
            continue
        try:
            nav_date = _parse_date(parts[5])
        except ValueError:
            continue
        rows.append(
            {
                "scheme_code": code,
                "amc": current_amc or "Unknown",
                "scheme_name": parts[3].strip(),
                "nav": nav,
                "nav_date": nav_date,
            }
        )
    return rows


def fetch_nav_rows(timeout: float = 30.0) -> list[dict]:
    """Download and parse the AMFI NAVAll file."""
    resp = httpx.get(AMFI_URL, timeout=timeout)
    resp.raise_for_status()
    return parse_navall(resp.text)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_amfi_nav.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/services/feeds/__init__.py \
        backend/services/feeds/amfi_nav.py \
        backend/tests/test_amfi_nav.py
git commit -m "feat(feeds): AMFI NAVAll.txt parser and fetcher"
```

---

### Task 10: Gold price fetcher (TDD with mocked HTTP)

**Files:**
- Create: `backend/services/feeds/gold_price.py`
- Test: `backend/tests/test_gold_price.py`

Scrapes the daily rate from IBJA (`https://ibja.co/`). The HTML structure exposes "Fine Gold (999)" and "22 Karat" rate cells. The fetcher returns `{"price_per_gram": float, "purity": "999", "source": "ibja", "fetched_at": iso}`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_gold_price.py`:
```python
from unittest.mock import patch, MagicMock
from services.feeds.gold_price import parse_ibja_html, fetch_gold_price_per_gram


_SAMPLE_HTML = """
<html><body>
<table id="ratesTable">
<tr><td>Fine Gold (999)</td><td>7234.50</td></tr>
<tr><td>22 Karat (916)</td><td>6627.20</td></tr>
<tr><td>Silver (999)</td><td>89.10</td></tr>
</table>
</body></html>
"""


def test_parse_ibja_html_extracts_999_price():
    px = parse_ibja_html(_SAMPLE_HTML, purity="999")
    assert px == 7234.50


def test_parse_ibja_html_extracts_22k_price():
    px = parse_ibja_html(_SAMPLE_HTML, purity="22k")
    assert px == 6627.20


def test_parse_ibja_html_returns_none_when_purity_missing():
    assert parse_ibja_html("<html></html>", purity="999") is None


def test_fetch_gold_price_uses_mocked_http():
    fake = MagicMock()
    fake.text = _SAMPLE_HTML
    fake.status_code = 200
    with patch("services.feeds.gold_price.httpx.get", return_value=fake) as m:
        result = fetch_gold_price_per_gram(purity="999")
    m.assert_called_once()
    assert result["price_per_gram"] == 7234.50
    assert result["purity"] == "999"
    assert result["source"] == "ibja"
    assert "fetched_at" in result
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_gold_price.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the fetcher**

`backend/services/feeds/gold_price.py`:
```python
"""IBJA daily gold-rate scraper."""
from __future__ import annotations
from datetime import datetime, timezone
import re
import httpx


IBJA_URL = "https://ibja.co/"

_LABELS = {
    "999": ("Fine Gold", "999"),
    "22k": ("22 Karat", "916"),
}


def parse_ibja_html(html: str, purity: str) -> float | None:
    """Find the gold-rate cell matching the requested purity.

    The IBJA page renders rates inside a `<table>` with a row label like
    'Fine Gold (999)' followed by a numeric `<td>`. Matching is permissive
    so the parser tolerates whitespace and label variants.
    """
    label, code = _LABELS.get(purity, (None, None))
    if not label:
        return None
    pattern = re.compile(
        rf"{re.escape(label)}[^<]*\(?{code}\)?[^<]*</td>\s*<td[^>]*>\s*([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    m = pattern.search(html)
    if not m:
        return None
    return float(m.group(1))


def fetch_gold_price_per_gram(purity: str = "999", timeout: float = 30.0) -> dict:
    """Return current per-gram INR price for the requested purity."""
    resp = httpx.get(IBJA_URL, timeout=timeout)
    resp.raise_for_status()
    px = parse_ibja_html(resp.text, purity)
    if px is None:
        raise ValueError(f"could not parse gold rate for purity={purity}")
    return {
        "price_per_gram": px,
        "purity": purity,
        "source": "ibja",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_gold_price.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/feeds/gold_price.py \
        backend/tests/test_gold_price.py
git commit -m "feat(feeds): IBJA gold-rate scraper"
```

---

### Task 11: Wealth aggregator (TDD)

**Files:**
- Create: `backend/services/wealth_aggregator.py`
- Test: `backend/tests/test_wealth_aggregator.py`

Single integration point. Pulls rows for one client from all 7 client-scoped tables, calls the four valuators + the two cached feeds, and returns a `WealthSnapshot`. Cache fallback rules match the existing `market_data` pattern — `live` → `cached` → `unavailable`.

This task ships the aggregator but does NOT wire it into `context_builder.py`. The LLM/report stay equity-only in Phase 1.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_wealth_aggregator.py`:
```python
from datetime import date, datetime, timezone
from unittest.mock import patch
from services.wealth_aggregator import build_wealth_snapshot


_FAKE_MFS = [{
    "id": "mf1", "client_id": "c1", "scheme_code": "120503",
    "scheme_name": "ICICI Bluechip", "amc": "ICICI",
    "category": "equity", "sub_category": "largecap",
    "units": 1000.0, "purchase_nav": 80.0, "purchase_date": "2023-01-01",
}]
_FAKE_NAV_CACHE = {
    "scheme_code": "120503", "nav": 105.4321, "nav_date": "2026-05-25",
    "fetched_at": datetime.now(timezone.utc).isoformat(),
}
_FAKE_GOLD = [{
    "id": "g1", "client_id": "c1", "form": "physical",
    "weight_grams": 100.0, "purity": "999",
    "purchase_price_per_gram": 5500.0, "purchase_date": "2022-01-01",
}]
_FAKE_GOLD_CACHE = {
    "purity": "999", "price_per_gram": 7234.50, "source": "ibja",
    "fetched_at": datetime.now(timezone.utc).isoformat(),
}
_FAKE_FDS = [{
    "id": "fd1", "client_id": "c1", "bank": "HDFC",
    "principal": 500_000.0, "rate_pct": 7.5,
    "start_date": "2024-01-01", "maturity_date": "2027-01-01",
    "compounding": "quarterly",
}]
_FAKE_CASH = [{
    "id": "ca1", "client_id": "c1", "account_type": "savings",
    "bank": "HDFC", "balance": 250_000.0,
}]


def test_snapshot_aggregates_buckets():
    with patch("services.wealth_aggregator.mutual_funds_db.get_for_client", return_value=_FAKE_MFS), \
         patch("services.wealth_aggregator.bonds_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.gold_db.get_for_client", return_value=_FAKE_GOLD), \
         patch("services.wealth_aggregator.cash_db.get_for_client", return_value=_FAKE_CASH), \
         patch("services.wealth_aggregator.fds_db.get_for_client", return_value=_FAKE_FDS), \
         patch("services.wealth_aggregator.insurance_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.liabilities_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.nav_cache_db.get", return_value=_FAKE_NAV_CACHE), \
         patch("services.wealth_aggregator.gold_price_cache_db.get_latest", return_value=_FAKE_GOLD_CACHE), \
         patch("services.wealth_aggregator.market_yields_db.get_curve", return_value=[]):
        snap = build_wealth_snapshot("c1", as_of=date(2025, 6, 1))
    # MF: 1000 units * 105.4321 = 105_432.10
    assert round(snap.mutual_funds.current_value, 2) == 105_432.10
    # Gold: 100g * 7234.50 = 723_450
    assert round(snap.gold.current_value, 2) == 723_450.00
    # Cash: 250_000
    assert snap.cash.current_value == 250_000.0
    # FDs > principal (some accrual)
    assert snap.fixed_deposits.current_value > 500_000.0
    # net_worth = sum of assets - sum of liabilities
    assert snap.net_worth > 0


def test_snapshot_marks_stale_when_nav_cache_missing():
    with patch("services.wealth_aggregator.mutual_funds_db.get_for_client", return_value=_FAKE_MFS), \
         patch("services.wealth_aggregator.bonds_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.gold_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.cash_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.fds_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.insurance_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.liabilities_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.nav_cache_db.get", return_value=None), \
         patch("services.wealth_aggregator.gold_price_cache_db.get_latest", return_value=None), \
         patch("services.wealth_aggregator.market_yields_db.get_curve", return_value=[]):
        snap = build_wealth_snapshot("c1", as_of=date(2025, 6, 1))
    assert snap.has_stale_values is True
    assert "mutual_funds" in snap.stale_sources


def test_snapshot_asset_allocation_sums_to_one():
    with patch("services.wealth_aggregator.mutual_funds_db.get_for_client", return_value=_FAKE_MFS), \
         patch("services.wealth_aggregator.bonds_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.gold_db.get_for_client", return_value=_FAKE_GOLD), \
         patch("services.wealth_aggregator.cash_db.get_for_client", return_value=_FAKE_CASH), \
         patch("services.wealth_aggregator.fds_db.get_for_client", return_value=_FAKE_FDS), \
         patch("services.wealth_aggregator.insurance_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.liabilities_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.nav_cache_db.get", return_value=_FAKE_NAV_CACHE), \
         patch("services.wealth_aggregator.gold_price_cache_db.get_latest", return_value=_FAKE_GOLD_CACHE), \
         patch("services.wealth_aggregator.market_yields_db.get_curve", return_value=[]):
        snap = build_wealth_snapshot("c1", as_of=date(2025, 6, 1))
    total = sum(snap.asset_allocation.values())
    assert 0.999 <= total <= 1.001
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_wealth_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the aggregator**

`backend/services/wealth_aggregator.py`:
```python
"""Aggregate all non-equity wealth buckets for one client into a WealthSnapshot.

Read-only. Falls back through live -> cached -> unavailable like
`services.market_data`. Not wired into `context_builder` in Phase 1.
"""
from __future__ import annotations
from datetime import date
from db import (
    mutual_funds_db,
    bonds_db,
    gold_db,
    cash_db,
    fds_db,
    insurance_db,
    liabilities_db,
    market_yields_db,
    nav_cache_db,
    gold_price_cache_db,
)
from models.wealth import (
    AssetBucket,
    InsuranceBucket,
    LiabilityBucket,
    WealthSnapshot,
)
from services.valuators.fd_valuator import value_fd
from services.valuators.liability_valuator import outstanding_balance
from services.valuators.bond_pricer import price_bond
from services.valuators.insurance_valuator import surrender_value


def _parse_date(s: str | date) -> date:
    if isinstance(s, date):
        return s
    return date.fromisoformat(s)


def _mf_bucket(client_id: str, stale: list[str]) -> AssetBucket:
    rows = mutual_funds_db.get_for_client(client_id)
    holdings, total, invested = [], 0.0, 0.0
    for r in rows:
        cache = nav_cache_db.get(r["scheme_code"])
        if cache:
            nav = float(cache["nav"])
            src = "cached"
        else:
            nav = float(r["purchase_nav"])
            src = "unavailable"
            stale.append("mutual_funds")
        units = float(r["units"])
        cur = units * nav
        inv = units * float(r["purchase_nav"])
        total += cur
        invested += inv
        holdings.append({**r, "current_nav": nav, "current_value": cur,
                         "invested_value": inv, "source": src})
    return AssetBucket(
        asset_class="mutual_funds",
        holdings=holdings,
        current_value=total,
        invested_value=invested,
        unrealised_gain=total - invested,
    )


def _gold_bucket(client_id: str, stale: list[str]) -> AssetBucket:
    rows = gold_db.get_for_client(client_id)
    holdings, total, invested = [], 0.0, 0.0
    for r in rows:
        cache = gold_price_cache_db.get_latest(r["purity"])
        if cache:
            ppg = float(cache["price_per_gram"])
        else:
            ppg = float(r["purchase_price_per_gram"])
            stale.append("gold")
        grams = float(r["weight_grams"])
        cur = grams * ppg
        inv = grams * float(r["purchase_price_per_gram"])
        total += cur
        invested += inv
        holdings.append({**r, "current_price_per_gram": ppg,
                         "current_value": cur, "invested_value": inv})
    return AssetBucket(
        asset_class="gold",
        holdings=holdings,
        current_value=total,
        invested_value=invested,
        unrealised_gain=total - invested,
    )


def _cash_bucket(client_id: str) -> AssetBucket:
    rows = cash_db.get_for_client(client_id)
    total = sum(float(r["balance"]) for r in rows)
    return AssetBucket(
        asset_class="cash",
        holdings=rows,
        current_value=total,
        invested_value=total,
        unrealised_gain=0.0,
    )


def _fd_bucket(client_id: str, as_of: date) -> AssetBucket:
    rows = fds_db.get_for_client(client_id)
    holdings, total, invested = [], 0.0, 0.0
    for r in rows:
        cur = value_fd(
            principal=float(r["principal"]),
            rate=float(r["rate_pct"]) / 100.0,
            start=_parse_date(r["start_date"]),
            compounding=r["compounding"],
            as_of=as_of,
        )
        inv = float(r["principal"])
        total += cur
        invested += inv
        holdings.append({**r, "current_value": cur, "invested_value": inv})
    return AssetBucket(
        asset_class="fixed_deposits",
        holdings=holdings,
        current_value=total,
        invested_value=invested,
        unrealised_gain=total - invested,
    )


def _bond_bucket(client_id: str, as_of: date, stale: list[str]) -> AssetBucket:
    rows = bonds_db.get_for_client(client_id)
    curve_rows = market_yields_db.get_curve("gsec")
    curve = [(float(r["tenor_years"]), float(r["yield_pct"])) for r in curve_rows]
    holdings, total, invested = [], 0.0, 0.0
    for r in rows:
        face = float(r["face_value"])
        units = float(r.get("units", 1))
        if curve:
            px = price_bond(
                face=face,
                coupon_pct=float(r["coupon_pct"]),
                maturity=_parse_date(r["maturity_date"]),
                as_of=as_of,
                curve=curve,
                spread_bps=int(r.get("credit_spread_bps", 0)),
                frequency=int(r.get("payment_frequency", 1)),
            )
        else:
            px = float(r.get("purchase_price", face))
            stale.append("bonds")
        cur = px * units
        inv = float(r.get("purchase_price", face)) * units
        total += cur
        invested += inv
        holdings.append({**r, "current_price": px, "current_value": cur,
                         "invested_value": inv})
    return AssetBucket(
        asset_class="bonds",
        holdings=holdings,
        current_value=total,
        invested_value=invested,
        unrealised_gain=total - invested,
    )


def _insurance_bucket(client_id: str, as_of: date) -> InsuranceBucket:
    rows = insurance_db.get_for_client(client_id)
    total_cover, total_surrender = 0.0, 0.0
    for r in rows:
        total_cover += float(r.get("sum_assured", 0.0))
        sv = surrender_value(
            policy_type=r["policy_type"],
            premium_amount=float(r["premium_amount"]),
            premium_frequency=r["premium_frequency"],
            start=_parse_date(r["start_date"]),
            as_of=as_of,
        )
        r["surrender_value"] = sv
        total_surrender += sv
    return InsuranceBucket(
        policies=rows,
        total_cover=total_cover,
        total_surrender_value=total_surrender,
    )


def _liability_bucket(client_id: str, as_of: date) -> LiabilityBucket:
    rows = liabilities_db.get_for_client(client_id)
    total = 0.0
    for r in rows:
        bal = outstanding_balance(
            principal=float(r["original_amount"]),
            rate=float(r["rate_pct"]) / 100.0,
            months=int(r["tenor_months"]),
            start=_parse_date(r["start_date"]),
            as_of=as_of,
            emi=float(r["emi"]) if r.get("emi") else None,
        )
        r["outstanding_balance"] = bal
        total += bal
    return LiabilityBucket(loans=rows, total_outstanding=total)


def build_wealth_snapshot(client_id: str, as_of: date | None = None) -> WealthSnapshot:
    """Build a full multi-asset wealth snapshot for one client."""
    if as_of is None:
        as_of = date.today()
    stale: list[str] = []
    mfs = _mf_bucket(client_id, stale)
    bonds = _bond_bucket(client_id, as_of, stale)
    gold = _gold_bucket(client_id, stale)
    cash = _cash_bucket(client_id)
    fds = _fd_bucket(client_id, as_of)
    insurance = _insurance_bucket(client_id, as_of)
    liabilities = _liability_bucket(client_id, as_of)

    asset_total = (
        mfs.current_value + bonds.current_value + gold.current_value
        + cash.current_value + fds.current_value
        + insurance.total_surrender_value
    )
    net_worth = asset_total - liabilities.total_outstanding
    allocation: dict[str, float] = {}
    if asset_total > 0:
        allocation = {
            "mutual_funds": mfs.current_value / asset_total,
            "bonds": bonds.current_value / asset_total,
            "gold": gold.current_value / asset_total,
            "cash": cash.current_value / asset_total,
            "fixed_deposits": fds.current_value / asset_total,
            "insurance": insurance.total_surrender_value / asset_total,
        }
    return WealthSnapshot(
        client_id=client_id,
        as_of=as_of.isoformat(),
        mutual_funds=mfs,
        bonds=bonds,
        gold=gold,
        cash=cash,
        fixed_deposits=fds,
        insurance=insurance,
        liabilities=liabilities,
        net_worth=net_worth,
        asset_allocation=allocation,
        has_stale_values=bool(stale),
        stale_sources=sorted(set(stale)),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_wealth_aggregator.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/wealth_aggregator.py \
        backend/tests/test_wealth_aggregator.py
git commit -m "feat(services): wealth aggregator for multi-asset snapshot"
```

---

### Task 12: Cron endpoints for daily NAV + gold refresh

**Files:**
- Modify: `backend/routes/jobs.py` (add two endpoints)
- Test: `backend/tests/test_jobs_nav_gold.py`

Two new endpoints follow the existing pattern in `jobs.py` (shared `JOB_SECRET` query param, write `job_runs` row on success, `error_logger.log_error` on failure):

- `GET /jobs/refresh-nav-cache?secret=$JOB_SECRET`
- `GET /jobs/refresh-gold-price?secret=$JOB_SECRET`

- [ ] **Step 1: Inspect current jobs.py to confirm pattern**

Run: `grep -n "JOB_SECRET\|router\|@router" backend/routes/jobs.py`
Expected: confirms existing pattern uses `os.getenv("JOB_SECRET")` and `@router.get` decorators.

- [ ] **Step 2: Write the failing test**

`backend/tests/test_jobs_nav_gold.py`:
```python
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app


_SECRET = os.environ.setdefault("JOB_SECRET", "test-secret")
client = TestClient(app)


def test_refresh_nav_cache_rejects_bad_secret():
    r = client.get("/jobs/refresh-nav-cache?secret=wrong")
    assert r.status_code in (401, 403)


def test_refresh_nav_cache_happy_path():
    fake_rows = [
        {"scheme_code": "120503", "amc": "ICICI", "scheme_name": "X",
         "nav": 100.0, "nav_date": "2026-05-25"}
    ]
    with patch("routes.jobs.fetch_nav_rows", return_value=fake_rows), \
         patch("routes.jobs.nav_cache_db.upsert") as upsert, \
         patch("routes.jobs.job_runs_db.insert"):
        r = client.get(f"/jobs/refresh-nav-cache?secret={_SECRET}")
    assert r.status_code == 200
    body = r.json()
    assert body["records"] == 1
    upsert.assert_called_once()


def test_refresh_gold_price_happy_path():
    fake = {"purity": "999", "price_per_gram": 7234.5,
            "source": "ibja", "fetched_at": "2026-05-25T00:00:00+00:00"}
    with patch("routes.jobs.fetch_gold_price_per_gram", return_value=fake), \
         patch("routes.jobs.gold_price_cache_db.insert") as ins, \
         patch("routes.jobs.job_runs_db.insert"):
        r = client.get(f"/jobs/refresh-gold-price?secret={_SECRET}")
    assert r.status_code == 200
    ins.assert_called_once_with(fake)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_jobs_nav_gold.py -v`
Expected: FAIL with `404 Not Found` (endpoints don't exist yet) or `AttributeError`.

- [ ] **Step 4: Add the endpoints to `backend/routes/jobs.py`**

Add imports near existing ones:
```python
from services.feeds.amfi_nav import fetch_nav_rows
from services.feeds.gold_price import fetch_gold_price_per_gram
from db import nav_cache_db, gold_price_cache_db
```

Append two endpoints (placement: after the existing `generate-monthly` route):
```python
@router.get("/jobs/refresh-nav-cache")
def refresh_nav_cache(secret: str):
    if secret != os.getenv("JOB_SECRET"):
        raise HTTPException(status_code=403, detail="bad secret")
    started = time.time()
    try:
        rows = fetch_nav_rows()
        nav_cache_db.upsert(rows)
        duration = int((time.time() - started) * 1000)
        job_runs_db.insert({
            "job_name": "refresh-nav-cache", "status": "ok",
            "records": len(rows), "duration_ms": duration,
        })
        return {"status": "ok", "records": len(rows), "duration_ms": duration}
    except Exception as e:
        log_error("refresh-nav-cache", str(e), {})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/refresh-gold-price")
def refresh_gold_price(secret: str, purity: str = "999"):
    if secret != os.getenv("JOB_SECRET"):
        raise HTTPException(status_code=403, detail="bad secret")
    started = time.time()
    try:
        row = fetch_gold_price_per_gram(purity=purity)
        gold_price_cache_db.insert(row)
        duration = int((time.time() - started) * 1000)
        job_runs_db.insert({
            "job_name": "refresh-gold-price", "status": "ok",
            "records": 1, "duration_ms": duration,
        })
        return {"status": "ok", "row": row, "duration_ms": duration}
    except Exception as e:
        log_error("refresh-gold-price", str(e), {})
        raise HTTPException(status_code=500, detail=str(e))
```

If `time`, `os`, `HTTPException`, `log_error`, or `job_runs_db` are not already imported at the top of jobs.py, add them following the existing import conventions of that file.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_jobs_nav_gold.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routes/jobs.py backend/tests/test_jobs_nav_gold.py
git commit -m "feat(jobs): daily NAV cache + gold price refresh endpoints"
```

---

### Task 13: Seed v2 SQL — 5 demo clients with realistic mix

**Files:**
- Create: `backend/db_schema/seed_v2.sql`

Adds rows for the 5 existing demo clients (preserving their UUIDs from `seed.sql`) across all 7 client-scoped tables. Mix per client matches the spec:

- Client 1 (Aggressive): equity-heavy + 2 small-cap MFs + 50g gold, no FDs.
- Client 2 (Balanced): equity + 3 MFs across categories + 1 bond + 1 home loan + 1 term plan.
- Client 3 (Conservative): equity + 2 debt MFs + 2 FDs + 1 endowment + 100g gold + 1 car loan.
- Client 4 (HNI): equity + 5 MFs + 2 corporate bonds + 2 FDs + ULIP + 1 sovereign gold bond.
- Client 5 (Retiree): equity (small) + 3 hybrid MFs + 3 FDs + 1 senior-citizen FD + 1 annuity + low cash.

Also populates `market_yields` (one G-Sec curve) and a `gold_price_cache` seed row so the aggregator returns non-stale values out of the box.

- [ ] **Step 1: Read existing seed.sql to recover client UUIDs**

Run: `grep -E "insert into clients|'[0-9a-f-]{36}'" backend/db_schema/seed.sql | head -40`
Expected: list of 5 client UUIDs to reuse.

- [ ] **Step 2: Write `backend/db_schema/seed_v2.sql`**

Use the actual UUIDs from `seed.sql`. Template (replace `<CLIENT_N_UUID>` with the real values discovered in Step 1):

```sql
-- seed_v2.sql -- multi-asset rows for the 5 demo clients in seed.sql.
-- Run AFTER seed.sql.

-- Support: G-Sec yield curve --------------------------------------------------
insert into market_yields (curve, tenor_years, yield_pct, as_of_date) values
  ('gsec', 1, 6.85, current_date),
  ('gsec', 3, 7.05, current_date),
  ('gsec', 5, 7.15, current_date),
  ('gsec', 10, 7.25, current_date),
  ('gsec', 30, 7.40, current_date)
on conflict (curve, tenor_years) do update
  set yield_pct = excluded.yield_pct, as_of_date = excluded.as_of_date;

-- Support: gold price seed ----------------------------------------------------
insert into gold_price_cache (purity, price_per_gram, source, fetched_at)
values ('999', 7234.50, 'ibja-seed', now());

-- Client 1 (Aggressive) -------------------------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('<CLIENT_1_UUID>', '125354', 'Nippon Small Cap Direct Growth',
   'Nippon India MF', 'equity', 'smallcap', 500.0, 110.50, '2023-06-15'),
  ('<CLIENT_1_UUID>', '120601', 'ICICI Value Discovery Direct Growth',
   'ICICI Prudential MF', 'equity', 'value', 800.0, 60.20, '2022-11-01');

insert into gold_holdings
  (client_id, form, weight_grams, purity,
   purchase_price_per_gram, purchase_date)
values
  ('<CLIENT_1_UUID>', 'physical', 50.0, '999', 5800.00, '2023-08-20');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('<CLIENT_1_UUID>', 'savings', 'HDFC Bank', 350_000);

-- Client 2 (Balanced) ---------------------------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('<CLIENT_2_UUID>', '120503', 'ICICI Bluechip Direct Growth',
   'ICICI Prudential MF', 'equity', 'largecap', 1200.0, 80.10, '2022-04-10'),
  ('<CLIENT_2_UUID>', '118989', 'HDFC Mid Cap Opportunities Direct',
   'HDFC MF', 'equity', 'midcap', 600.0, 95.00, '2023-01-20'),
  ('<CLIENT_2_UUID>', '119551', 'Axis Short Term Direct Growth',
   'Axis MF', 'debt', 'short-duration', 2000.0, 28.40, '2024-02-15');

insert into bonds
  (client_id, isin, issuer, bond_type, face_value, units,
   coupon_pct, payment_frequency, purchase_price, maturity_date,
   credit_rating, credit_spread_bps, purchase_date)
values
  ('<CLIENT_2_UUID>', 'IN0020220068', 'Govt of India', 'gsec',
   1000.0, 50, 7.10, 2, 990.00, '2032-04-08', 'SOV', 0, '2023-05-12');

insert into liabilities
  (client_id, loan_type, lender, original_amount, rate_pct,
   tenor_months, emi, start_date)
values
  ('<CLIENT_2_UUID>', 'home', 'HDFC Bank', 5_000_000.0, 8.5, 240,
   43_391.16, '2022-07-01');

insert into insurance_policies
  (client_id, policy_type, insurer, sum_assured, premium_amount,
   premium_frequency, start_date, maturity_date)
values
  ('<CLIENT_2_UUID>', 'term', 'HDFC Life', 10_000_000.0, 18_000.0,
   'annual', '2021-09-01', '2046-09-01');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('<CLIENT_2_UUID>', 'savings', 'Kotak', 220_000),
  ('<CLIENT_2_UUID>', 'sweep', 'Kotak', 180_000);

-- Client 3 (Conservative) -----------------------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('<CLIENT_3_UUID>', '119551', 'Axis Short Term Direct Growth',
   'Axis MF', 'debt', 'short-duration', 5000.0, 27.10, '2022-08-01'),
  ('<CLIENT_3_UUID>', '120466', 'SBI Magnum Gilt Direct Growth',
   'SBI MF', 'debt', 'gilt', 3000.0, 49.50, '2023-03-01');

insert into fixed_deposits
  (client_id, bank, principal, rate_pct, start_date, maturity_date,
   compounding)
values
  ('<CLIENT_3_UUID>', 'SBI', 800_000.0, 7.10, '2024-01-15',
   '2027-01-15', 'quarterly'),
  ('<CLIENT_3_UUID>', 'ICICI', 500_000.0, 7.25, '2023-11-01',
   '2025-11-01', 'quarterly');

insert into insurance_policies
  (client_id, policy_type, insurer, sum_assured, premium_amount,
   premium_frequency, start_date, maturity_date)
values
  ('<CLIENT_3_UUID>', 'endowment', 'LIC', 1_500_000.0, 75_000.0,
   'annual', '2018-04-15', '2038-04-15');

insert into gold_holdings
  (client_id, form, weight_grams, purity,
   purchase_price_per_gram, purchase_date)
values
  ('<CLIENT_3_UUID>', 'physical', 100.0, '999', 5200.00, '2021-02-20');

insert into liabilities
  (client_id, loan_type, lender, original_amount, rate_pct,
   tenor_months, emi, start_date)
values
  ('<CLIENT_3_UUID>', 'car', 'ICICI Bank', 800_000.0, 9.5, 60,
   16_795.0, '2023-06-01');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('<CLIENT_3_UUID>', 'savings', 'SBI', 450_000);

-- Client 4 (HNI) --------------------------------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('<CLIENT_4_UUID>', '120503', 'ICICI Bluechip Direct Growth',
   'ICICI Prudential MF', 'equity', 'largecap', 3000.0, 75.00, '2020-09-12'),
  ('<CLIENT_4_UUID>', '120466', 'SBI Magnum Gilt Direct Growth',
   'SBI MF', 'debt', 'gilt', 8000.0, 47.20, '2022-06-01'),
  ('<CLIENT_4_UUID>', '118989', 'HDFC Mid Cap Opportunities Direct',
   'HDFC MF', 'equity', 'midcap', 1500.0, 92.30, '2021-11-15'),
  ('<CLIENT_4_UUID>', '125354', 'Nippon Small Cap Direct Growth',
   'Nippon India MF', 'equity', 'smallcap', 600.0, 105.40, '2022-03-20'),
  ('<CLIENT_4_UUID>', '119551', 'Axis Short Term Direct Growth',
   'Axis MF', 'debt', 'short-duration', 4000.0, 28.10, '2023-09-01');

insert into bonds
  (client_id, isin, issuer, bond_type, face_value, units, coupon_pct,
   payment_frequency, purchase_price, maturity_date, credit_rating,
   credit_spread_bps, purchase_date)
values
  ('<CLIENT_4_UUID>', 'INE001A07TQ4', 'HDFC Ltd', 'corporate',
   1000.0, 200, 8.20, 1, 1005.0, '2029-12-15', 'AAA', 50, '2022-12-10'),
  ('<CLIENT_4_UUID>', 'INE020B08DM5', 'REC Ltd', 'corporate',
   1000.0, 150, 7.85, 2, 998.0, '2031-05-20', 'AAA', 60, '2023-04-22');

insert into fixed_deposits
  (client_id, bank, principal, rate_pct, start_date, maturity_date,
   compounding)
values
  ('<CLIENT_4_UUID>', 'HDFC', 1_500_000.0, 7.50, '2024-03-01',
   '2027-03-01', 'quarterly'),
  ('<CLIENT_4_UUID>', 'Kotak', 1_000_000.0, 7.40, '2023-12-15',
   '2026-12-15', 'monthly');

insert into insurance_policies
  (client_id, policy_type, insurer, sum_assured, premium_amount,
   premium_frequency, start_date, maturity_date)
values
  ('<CLIENT_4_UUID>', 'ulip', 'ICICI Pru', 5_000_000.0, 200_000.0,
   'annual', '2019-08-10', '2034-08-10');

insert into gold_holdings
  (client_id, form, weight_grams, purity,
   purchase_price_per_gram, purchase_date)
values
  ('<CLIENT_4_UUID>', 'sgb', 200.0, '999', 5450.00, '2022-05-30');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('<CLIENT_4_UUID>', 'savings', 'HDFC Bank', 850_000),
  ('<CLIENT_4_UUID>', 'sweep', 'HDFC Bank', 1_200_000);

-- Client 5 (Retiree) ----------------------------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('<CLIENT_5_UUID>', '120601', 'ICICI Value Discovery Direct Growth',
   'ICICI Prudential MF', 'equity', 'value', 400.0, 58.10, '2021-04-12'),
  ('<CLIENT_5_UUID>', '120466', 'SBI Magnum Gilt Direct Growth',
   'SBI MF', 'debt', 'gilt', 4000.0, 46.80, '2022-01-15'),
  ('<CLIENT_5_UUID>', '119551', 'Axis Short Term Direct Growth',
   'Axis MF', 'debt', 'short-duration', 3000.0, 27.40, '2023-02-20');

insert into fixed_deposits
  (client_id, bank, principal, rate_pct, start_date, maturity_date,
   compounding)
values
  ('<CLIENT_5_UUID>', 'SBI', 1_200_000.0, 7.75, '2024-06-01',
   '2027-06-01', 'quarterly'),
  ('<CLIENT_5_UUID>', 'SBI', 800_000.0, 7.50, '2023-09-10',
   '2026-09-10', 'quarterly'),
  ('<CLIENT_5_UUID>', 'PNB', 600_000.0, 8.00, '2024-02-15',
   '2029-02-15', 'quarterly');

insert into insurance_policies
  (client_id, policy_type, insurer, sum_assured, premium_amount,
   premium_frequency, start_date, maturity_date)
values
  ('<CLIENT_5_UUID>', 'annuity', 'LIC', 2_000_000.0, 10_000.0,
   'monthly', '2019-01-15', '2039-01-15');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('<CLIENT_5_UUID>', 'savings', 'SBI', 150_000);
```

- [ ] **Step 3: Verify seed_v2.sql by running it against a local Supabase**

Run via SQL editor or `psql`:
```
\i backend/db_schema/seed_v2.sql
```
Then verify rows:
```sql
select 'mutual_funds' as t, count(*) from mutual_funds
union all select 'bonds', count(*) from bonds
union all select 'gold_holdings', count(*) from gold_holdings
union all select 'cash_balances', count(*) from cash_balances
union all select 'fixed_deposits', count(*) from fixed_deposits
union all select 'insurance_policies', count(*) from insurance_policies
union all select 'liabilities', count(*) from liabilities;
```
Expected: counts ≥ 1 for every table.

- [ ] **Step 4: Commit**

```bash
git add backend/db_schema/seed_v2.sql
git commit -m "feat(db): seed_v2 with multi-asset rows for 5 demo clients"
```

---

### Task 14: End-to-end smoke test for the aggregator

**Files:**
- Create: `backend/tests/test_wealth_aggregator_smoke.py`

This test wires the aggregator against real Supabase. It is `pytest.mark.skipif`-guarded so CI without `SUPABASE_URL` skips it cleanly.

- [ ] **Step 1: Write the smoke test**

`backend/tests/test_wealth_aggregator_smoke.py`:
```python
import os
import pytest
from datetime import date
from services.wealth_aggregator import build_wealth_snapshot
from db.supabase_client import get_supabase


_SKIP = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL"),
    reason="needs live Supabase (set SUPABASE_URL + SUPABASE_KEY)",
)


@_SKIP
def test_smoke_build_snapshot_for_first_seed_client():
    sb = get_supabase()
    res = sb.table("clients").select("id").limit(1).execute()
    assert res.data, "no clients in DB — apply seed.sql + seed_v2.sql first"
    client_id = res.data[0]["id"]
    snap = build_wealth_snapshot(client_id, as_of=date.today())
    assert snap.client_id == client_id
    assert snap.net_worth is not None
    # At least one asset bucket should be populated for seeded clients.
    populated = [
        snap.mutual_funds.current_value, snap.bonds.current_value,
        snap.gold.current_value, snap.cash.current_value,
        snap.fixed_deposits.current_value,
    ]
    assert any(v > 0 for v in populated)
```

- [ ] **Step 2: Run the smoke test**

Run: `cd backend && SUPABASE_URL=$SUPABASE_URL SUPABASE_KEY=$SUPABASE_KEY pytest tests/test_wealth_aggregator_smoke.py -v`
Expected: 1 passed (if env is set) or 1 skipped (if not set).

- [ ] **Step 3: Run the full test suite**

Run: `cd backend && pytest -v`
Expected: all tests pass; new tests for valuators, feeds, aggregator, and job endpoints are green.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_wealth_aggregator_smoke.py
git commit -m "test(smoke): end-to-end wealth aggregator against live Supabase"
```

---

### Task 15: Documentation updates

**Files:**
- Modify: `CLAUDE.md` (add a "Multi-Asset Data Model (Phase 1)" subsection)
- Modify: `backend/db_schema/README.md` (update apply order)

- [ ] **Step 1: Append a Phase 1 subsection to CLAUDE.md**

Add the following block under the existing `## Architecture` section, after the "Failure handling conventions" subsection:

```markdown
### Multi-Asset Data Model (Phase 1)

Phase 1 ships the data + valuation layer for non-equity assets without touching
the LLM context. Reports remain equity-only until Phase 3.

- 10 new tables in `backend/db_schema/migration_002_multi_asset.sql`:
  `mutual_funds`, `bonds`, `gold_holdings`, `cash_balances`, `fixed_deposits`,
  `insurance_policies`, `liabilities` (client-scoped) +
  `market_yields`, `nav_cache`, `gold_price_cache` (support).
- CRUD lives in `backend/db/{table}_db.py` — same singleton + `RuntimeError`
  convention as existing modules.
- Pure valuators in `backend/services/valuators/`:
  `fd_valuator`, `bond_pricer`, `insurance_valuator`, `liability_valuator`.
- Feeds in `backend/services/feeds/`: `amfi_nav` (NAVAll.txt parser),
  `gold_price` (IBJA scraper). Refreshed by two new cron endpoints
  `/jobs/refresh-nav-cache` and `/jobs/refresh-gold-price` (shared `JOB_SECRET`).
- Integration point: `services.wealth_aggregator.build_wealth_snapshot(client_id, as_of)`
  returns a `WealthSnapshot` (pydantic model in `models/wealth.py`). It is
  **not** called from `context_builder.py` in Phase 1 — wire-in is Phase 3.
- Seed: apply `seed.sql` first, then `seed_v2.sql` for multi-asset rows on the
  5 demo clients.
```

- [ ] **Step 2: Update `backend/db_schema/README.md` apply order**

Read the current README first to see existing structure, then update the apply-order section to:
```
1. schema.sql              -- base 10 tables
2. migration_002_multi_asset.sql  -- 10 new multi-asset tables (Phase 1)
3. rls.sql                 -- existing row-level security for base tables
4. seed.sql                -- 5 demo HNI clients (equity + portfolios)
5. seed_v2.sql             -- multi-asset rows for the same 5 clients
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md backend/db_schema/README.md
git commit -m "docs: document Phase 1 multi-asset data model"
```

---

## Self-Review Checklist

After completing all 15 tasks, verify:

1. **Spec coverage** — every section of `docs/superpowers/specs/2026-05-25-multi-asset-data-model-design.md` maps to one or more tasks above (schema → Task 1; CRUD → Task 4; valuators → Tasks 5-8; feeds → Tasks 9-10; aggregator → Task 11; cron → Task 12; seed → Task 13; docs → Task 15).
2. **Tests pass clean** — `cd backend && pytest` is green; smoke test is skipped or green.
3. **No placeholder rows** — `seed_v2.sql` uses real UUIDs (Step 1 of Task 13 confirms them).
4. **No wiring leak** — `services/context_builder.py` is untouched: `grep -n "wealth_aggregator\|mutual_funds\|fixed_deposits" backend/services/context_builder.py` returns nothing.
5. **No frontend leak** — no files under `frontend/` were modified.
6. **Branch hygiene** — all commits live on `phase1-multi-asset-data-model`; `git log --oneline main..HEAD` shows 14–15 focused commits.

