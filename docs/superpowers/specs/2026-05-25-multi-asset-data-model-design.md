# Phase 1 — Multi-Asset Data Model + Synthetic Seed

**Date:** 2026-05-25
**Status:** Approved design — ready for implementation planning
**Branch:** `phase1-multi-asset-data-model`
**Phase:** 1 of 3 (this spec covers ONLY data foundation; Phase 2 = change-tracking, Phase 3 = UI + report content. Each gets its own brainstorm/spec/plan.)

## Goal

Extend PortfolioNarrator's data model from equity-only to a holistic Indian-HNI wealth picture: mutual funds, bonds, gold, cash, fixed deposits, insurance, and liabilities. Each non-formula-valued class gets real-feed valuation. Ship this as a pure substrate — no UI changes, no prompt changes, no report content changes in this phase. Phases 2 and 3 consume what we build here.

## Scope

### In scope

- 7 new client-scoped tables: `mutual_funds`, `bonds`, `gold_holdings`, `cash_balances`, `fixed_deposits`, `insurance_policies`, `liabilities`
- 3 support tables: `market_yields`, `nav_cache`, `gold_price_cache`
- Per-table CRUD modules in `backend/db/`
- Valuation services per asset class (mix of live feeds and pure-math formulas)
- AMFI NAV fetcher + gold price fetcher + cron job endpoints
- Bond YTM fair-value pricer
- A `wealth_aggregator` service that assembles a complete `WealthSnapshot` per client
- Synthetic seed data for the 5 existing clients across all new asset classes
- Tests for valuators, fetchers, and aggregator
- Migration + rollback SQL

### Explicitly out of scope (Phase 2 / Phase 3 work)

- `prompt_builder.py`, the 7 letter sections, the few-shot anchors — all unchanged
- `context_builder.py` — no new fields packed into LLM context this phase
- Any frontend change (`ClientDetail.jsx`, `ReportPage.jsx`, components stay as-is)
- Change-tracking ("what changed this month and why") — Phase 2
- Multi-asset visibility in the RM client-detail UI — Phase 3
- Real estate, PMS/AIF, crypto, derivatives — not in any phase yet
- Goal tracking, cash-flow dashboard, tax-loss harvesting analytics
- Auth/authorization changes
- Multi-RM data sharing

## Architecture

### Layer placement (matches existing CLAUDE.md conventions)

- **`backend/db_schema/migrations/002_multi_asset.sql`** + **`002_multi_asset_rollback.sql`** — source of truth for the new tables. `schema.sql` stays untouched.
- **`backend/db_schema/seed_v2.sql`** — populates the 5 existing clients with realistic mixes.
- **`backend/db_schema/README.md`** (new) — documents the apply order: `schema.sql` → `rls.sql` → `seed.sql` → `migrations/002_multi_asset.sql` → `seed_v2.sql`.
- **`backend/db/`** — one CRUD module per table (`mutual_funds_db.py`, `bonds_db.py`, `gold_db.py`, `cash_db.py`, `fds_db.py`, `insurance_db.py`, `liabilities_db.py`, `market_yields_db.py`, `nav_cache_db.py`, `gold_price_cache_db.py`). Each exposes `get_for_client(client_id)` and minimal CRUD. Same `RuntimeError on connection failure` convention as existing `db/` modules; all access via `db/supabase_client.get_supabase()` singleton.
- **`backend/services/`** — new valuation + aggregation services (see "Service layer" below).
- **`backend/models/`** — Pydantic shapes for each table. API surface is **not** built in this phase; models exist so Phase 3 can import them cleanly.
- **`backend/routes/jobs.py`** — gets two new cron endpoints (`/jobs/refresh-nav`, `/jobs/refresh-gold`), guarded by `JOB_SECRET` like the existing job endpoints.

### Schema

All client-scoped tables share `id uuid PK`, `client_id uuid FK → clients(id) ON DELETE CASCADE`, `created_at timestamptz default now()`, and an index on `(client_id)`. Dates use ISO `YYYY-MM-DD`.

**`mutual_funds`** — `scheme_code (AMFI), scheme_name, scheme_type (equity|debt|hybrid|liquid), units, avg_cost_nav, invested_amount, sip_active (bool), sip_amount, sip_start_date, current_nav, current_nav_date, source (live|cached|unavailable)`. Index: `(scheme_code)`.

**`bonds`** — `isin, bond_name, bond_type (gsec|corp|tax_free|perpetual), face_value, units, coupon_rate, coupon_freq (annual|semi), maturity_date, purchase_date, purchase_price, current_price, current_price_date, source`. Index: `(isin)`.

**`gold_holdings`** — `gold_type (physical|sgb|etf|fund), grams, purity (24k|22k|18k), purchase_date, purchase_price_per_gram, current_price_per_gram, current_price_date, source`.

**`cash_balances`** — `account_type (savings|sweep|current), bank_name, balance, as_of_date`.

**`fixed_deposits`** — `bank_name, fd_number_last4, principal, interest_rate, compounding (simple|monthly|quarterly|annual), start_date, maturity_date, payout_type (cumulative|payout)`. Current value computed in the valuator, not stored.

**`insurance_policies`** — `policy_type (term|endowment|ulip|health|whole_life), insurer, policy_number_last4, sum_assured, premium_amount, premium_frequency (monthly|quarterly|annual), policy_start_date, maturity_date, surrender_value (nullable), current_nav (ULIP only, nullable), units (ULIP only, nullable)`.

**`liabilities`** — `loan_type (home|car|personal|credit_card|loan_against_securities), lender, sanctioned_amount, interest_rate, emi_amount, tenure_months, start_date`. Current outstanding computed in the valuator, not stored.

**`market_yields`** (support, not client-scoped) — `date, tenor_years, yield_pct`. PK = `(date, tenor_years)`. ~5 rows refreshed daily (1Y, 3Y, 5Y, 10Y, 30Y G-Sec).

**`nav_cache`** (support, mirrors existing `price_cache`) — `scheme_code PK, nav, nav_date, fetched_at`.

**`gold_price_cache`** (support) — `gold_type PK, price_per_gram, source, fetched_at`.

### RLS

Mirrors the existing `rls.sql` pattern. All 7 asset/liability tables filter rows by `client_id` belonging to the authenticated RM (via the `clients.rm_id` chain). `market_yields`, `nav_cache`, `gold_price_cache` are read-public / write-service-role.

## Service layer

### Valuation services (`backend/services/`)

**`amfi_nav_fetcher.py`** — Daily fetch of `https://www.amfiindia.com/spages/NAVAll.txt` (pipe-delimited format). Upserts into `nav_cache`. Exposes `get_nav(scheme_code) -> (nav, nav_date, source)` where `source ∈ {"live", "cached", "unavailable"}`. Same shape as `services/market_data.get_price()` for equity, so consumer code is uniform.

**`gold_price_fetcher.py`** — Daily fetch from a free source (IBJA scrape OR a free metals API; concrete source chosen during planning). Upserts into `gold_price_cache`. Exposes `get_gold_price(gold_type) -> (price_per_gram, source)`.

**`bond_pricer.py`** — Pure-math YTM fair-value pricer. For a bond + matching `market_yields` tenor, computes clean price via PV-of-cashflows discount math. For listed bonds with a populated `current_price`, returns that directly (treats it as last traded). Exposes `value_bond(bond_row) -> (current_value, source)`.

**`fd_valuator.py`** — Pure-math accrued interest per `compounding` rule. Exposes `value_fd(fd_row, as_of=date.today()) -> current_value`. Property: monotonically increasing in time until `maturity_date`.

**`insurance_valuator.py`** — Per `policy_type`:
- `term`, `health` → current value = 0 (no surrender, sum assured is contingent)
- `endowment`, `whole_life` → linear surrender-value approximation from premiums paid × `surrender_factor(years_completed)` (factor table baked into the valuator; standard IRDAI-style curve)
- `ulip` → `units × current_nav` (NAV stored on row, RM-maintained for now; could later wire to a ULIP NAV feed)

Exposes `value_policy(policy_row) -> (current_value, sum_assured, source)`.

**`liability_valuator.py`** — Pure-math amortization. Computes outstanding balance from `principal, interest_rate, emi_amount, tenure_months, start_date` and today's date. Exposes `value_liability(loan_row) -> outstanding_balance`. Property: monotonically decreasing until `end_date`.

### Aggregation

**`wealth_aggregator.py`** — Glue service, single integration point for Phase 2 and Phase 3. Given `client_id`:
1. Calls every `db/*_db.get_for_client(client_id)`
2. Enriches each row through its valuator
3. Returns a `WealthSnapshot`:

```python
{
  "equity":      {"holdings": [...], "total_value": float, "source_health": {...}},
  "mfs":         {"holdings": [...], "total_value": float, "source_health": {...}},
  "bonds":       {"holdings": [...], "total_value": float, "source_health": {...}},
  "gold":        {"holdings": [...], "total_value": float, "source_health": {...}},
  "cash":        {"holdings": [...], "total_value": float},
  "fds":         {"holdings": [...], "total_value": float},
  "insurance":   {"holdings": [...], "total_surrender": float, "total_sum_assured": float},
  "liabilities": {"holdings": [...], "total_outstanding": float},
  "net_worth":   float,                         # total_assets - total_liabilities
  "asset_allocation": {                         # pct of total assets (not net worth)
      "equity_pct": float, "mf_pct": float, "bond_pct": float,
      "gold_pct": float, "cash_pct": float, "fd_pct": float, "insurance_pct": float
  },
  "has_stale_values": bool,
  "stale_sources": [str]                        # e.g., ["amfi_nav", "gold"]
}
```

Phase 1 ships `wealth_aggregator` but does **not** wire it into `context_builder`. The LLM context and the report stay equity-only until Phase 3.

### Cron jobs (`backend/routes/jobs.py`)

- `GET /jobs/refresh-nav?secret=<JOB_SECRET>` → `amfi_nav_fetcher.refresh_all()`
- `GET /jobs/refresh-gold?secret=<JOB_SECRET>` → `gold_price_fetcher.refresh()`
- `GET /jobs/refresh-yields?secret=<JOB_SECRET>` (weekly, optional) → bulk-update `market_yields`; in v1 the rows can also be edited manually since G-Sec yields move slowly.

All three follow the existing pattern: write to `job_runs` on completion (status, records, duration_ms), and log to `error_logs` on failure via `services/error_logger.log_error` — which never raises.

### Failure handling

Every valuator returns a stale/unavailable marker rather than raising. `wealth_aggregator` aggregates these into `has_stale_values` and `stale_sources`. Consumers (Phase 2/3) render the appropriate warning. This mirrors the existing equity `has_stale_prices` / `stale_tickers` convention so Phase 3 prompt changes can use one uniform language.

## Migration & seed

### Migration

- `002_multi_asset.sql` creates all 10 tables (7 client-scoped + 3 support), indexes, and RLS policies in one transaction.
- `002_multi_asset_rollback.sql` drops them in reverse dependency order. Both files are committed to git; the rollback exists for local dev safety, not for production rollback.
- The `backend/db_schema/README.md` documents the apply order.

### Seed

`seed_v2.sql` populates the 5 existing demo clients per the agreed mix:

| Client | AUM | Risk | Seed mix |
|---|---|---|---|
| Sunita | ₹0.75 Cr | Conservative | Heavy FDs + debt MFs + tax-free bonds + 1 endowment policy + 1 small personal loan |
| Rajesh | ₹2.5 Cr | Moderate | Existing equity + mixed MFs + small gold (SGB) + cash + home loan |
| Priya | ₹1.2 Cr | Aggressive | Existing equity + equity MFs + small gold ETF + LAS (loan against securities) |
| Arjun | ₹5 Cr | Moderate-long | Diversified across all classes + home loan + car loan |
| Vikram | ₹8 Cr | Aggressive-long | Existing equity + ULIP + perpetual bonds + gold + LAS |

Plus a snapshot of `market_yields` (5 tenor rows for the seed date), and small `nav_cache` / `gold_price_cache` snapshots so the demo works offline before the first cron run.

**Realism constraints (encoded in seed values, not in code):**
- Net worth (assets − liabilities) for each client stays within the same order of magnitude as today's `aum_cr`, so Phase 3 prompt changes don't suddenly produce a wildly different headline number.
- ISINs, AMFI scheme codes, FD account numbers, policy numbers are synthetic but format-valid (no real customer data anywhere).
- 4–8 positions per non-equity class per client; existing equity holdings are not modified.

## Testing

- **`backend/tests/test_fd_valuator.py`** — pure-function tests; property-based: value monotonic in time, value at start = principal, value at maturity matches expected formula per `compounding` rule.
- **`backend/tests/test_liability_valuator.py`** — pure-function; property-based: outstanding monotonically decreasing, outstanding at `start_date` = principal, outstanding at `end_date` ≤ 0.
- **`backend/tests/test_bond_pricer.py`** — par bond (coupon = market yield) prices at face value; zero-coupon prices correctly vs. analytic formula; sensitivity to yield change has correct sign.
- **`backend/tests/test_insurance_valuator.py`** — each `policy_type` branch tested; term returns 0; ULIP `units × nav` correct; endowment surrender curve sensible.
- **`backend/tests/test_amfi_fetcher.py`** + **`test_gold_fetcher.py`** — mocked HTTP responses using a recorded fixture of the AMFI NAVAll format and the chosen gold source format. **No live network calls in CI.**
- **`backend/tests/test_wealth_aggregator.py`** — uses a seeded test client; asserts structure of `WealthSnapshot`, correct totals, and that `has_stale_values` flips correctly when a source is forced stale.
- All existing tests in `backend/tests/test_utils.py` must still pass — Phase 1 must not regress `context_builder`, `report_generator`, or the streaming pipeline.

## Definition of done

1. All 10 tables exist in Supabase with RLS, indexes, and rollback file committed.
2. `seed_v2.sql` populates all 5 clients with realistic mixes; net worth ≈ existing `aum_cr` order of magnitude per client.
3. AMFI + gold cron endpoints return 200 and refresh `nav_cache` / `gold_price_cache`.
4. `wealth_aggregator.get_snapshot(client_id)` returns a complete `WealthSnapshot` for every seeded client with no exceptions, correct totals, correct stale flags when sources are forced offline.
5. All valuator + aggregator + fetcher tests pass; all existing tests still pass.
6. `infra/deploy.sh` runs cleanly on EC2 against the new schema (existing deploy flow unchanged).
7. Documentation: `backend/db_schema/README.md` explains the migration order; `CLAUDE.md` gets a short subsection under Architecture pointing at `wealth_aggregator` as the consumer-facing entry point for Phase 2/3.

## Open questions deferred to implementation planning

- Exact gold price source (IBJA scrape vs. a free metals-price API) — evaluate both during plan-writing.
- Whether `nav_cache` should retain history (multi-day rows per `scheme_code`) or stay single-row-per-scheme. Phase 1 ships single-row; Phase 2 may add history if change-tracking needs it.
- Endowment surrender-factor curve — concrete numbers chosen in the plan; a standard IRDAI-style schedule is sufficient.

## Phasing recap

This spec is **Phase 1 of 3**. Phases 2 (change-tracking) and 3 (UI + report content) are separate brainstorms / specs / plans:

- **Phase 2** — portfolio snapshots over time, allocation targets, "what changed this month and why" model. Consumes `wealth_aggregator` to detect drift and to record point-in-time wealth snapshots.
- **Phase 3** — `ClientDetail.jsx` and `ReportPage.jsx` updates so the RM sees the full wealth picture; additions to the 7-section prompt so the letter discusses non-equity asset classes and change rationale.

Each phase starts only after the previous one is real.
