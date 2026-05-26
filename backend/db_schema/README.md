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
