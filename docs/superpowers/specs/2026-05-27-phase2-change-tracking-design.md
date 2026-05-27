# Phase 2 — Change-Tracking Model Design

**Status:** Draft for review
**Date:** 2026-05-27
**Depends on:** Phase 1 (`2026-05-25-multi-asset-data-model-design.md`, merged PR #2)

## 1. Purpose & Lead Use Case

Phase 1 shipped the multi-asset data model, valuators, feeds, and an on-demand `wealth_aggregator.build_wealth_snapshot()` — but nothing persists, no allocation targets exist, and the only "why" field anywhere is the free-text `transactions.rationale` column on equity trades.

Phase 2 adds the **change-tracking model** so the report narrator can describe how a client's wealth, allocation, and decisions evolved between letters.

**Lead use case (A):** Report narrative fuel. The Cohere letter can now say things like *"since your last letter, your gold allocation moved from 8% to 12% as we deployed redemption proceeds; we raised your gold target from 5% to 8% in April because inflation prints stayed sticky."*

**Side effects that come along for free:**
- **(B) Compliance / audit trail** — every allocation target change carries a logged rationale; every snapshot is a photograph of what we believed wealth was at that moment.
- **(C) RM workflow / drift detection** — actual vs target with per-class tolerance bands is computable on demand.

**Explicitly out of scope (deferred):**
- Client-facing history / charts on `ClientDetail`.
- Proactive RM drift-alert UI or notifications.
- Multi-event-type narrator templates beyond a single "what changed" paragraph.
- Broker-feed-driven event detection.
- Daily snapshot cadence.
- Backfill of historical snapshots prior to Phase 2 launch.

## 2. Design Decisions (Locked Through Brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| Q1 | Lead use case | A (narrator); B, C follow for free |
| Q2 | Snapshot persistence cadence | Report-gen + rationale-event + monthly backstop |
| Q3 | Snapshot granularity | Aggregates + full `WealthSnapshot` JSONB blob, photograph semantics |
| Q4 | Allocation target granularity | Five economic classes (equity, debt, gold, cash, alternatives), per-class bands |
| Q5 | Target change handling | Versioned history, `rationale_event_id NOT NULL` on every target row |
| Q6 | Rationale event structure | Structured `event_type` enum (8 values), `title` + `rationale_text` |

## 3. Component Overview

```
┌────────────────────┐
│ RM action / cron   │
│ - generate report  │
│ - log rationale    │
│ - monthly tick     │
└─────────┬──────────┘
          │
          ▼
┌──────────────────────────────────────────────────────┐
│ services/snapshot_service.py                         │
│   persist_snapshot(client_id, trigger, event_id?)    │
│     1. call wealth_aggregator.build_wealth_snapshot  │
│     2. roll up buckets → 5 economic classes          │
│     3. insert wealth_snapshots row                   │
│     4. return snapshot_id                            │
└─────────┬────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────┐
│ wealth_snapshots │ allocation_targets │ rationale_events│
└─────────┬────────┴──────────┬─────────┴────────┬─────┘
          │                   │                  │
          └─────────┬─────────┴──────────────────┘
                    ▼
         ┌─────────────────────────────────┐
         │ services/context_builder.py     │
         │   reads: prior + current snap   │
         │          active target          │
         │          rationale_events in    │
         │          [prior.as_of, now]     │
         │          drift                  │
         │   → passes to prompt_builder    │
         └─────────────────────────────────┘
```

## 4. Schema — Migration `003_change_tracking.sql`

The three new tables have cross-references between `wealth_snapshots` and `rationale_events`. Both FKs are nullable to allow a two-step insert pattern (see §6 for the resolution flow).

### 4.1 `wealth_snapshots`

```sql
create table wealth_snapshots (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  as_of timestamptz not null,
  trigger text not null check (trigger in ('report','rationale','monthly')),
  rationale_event_id uuid null references rationale_events(id),
  report_id uuid null references reports(id),

  -- Hot aggregate columns
  net_worth numeric(18,2) not null,
  total_assets numeric(18,2) not null,
  total_liabilities numeric(18,2) not null,
  total_unrealised_gain numeric(18,2) not null,
  allocation_pct jsonb not null,  -- {"equity":0.42,"debt":0.30,"gold":0.08,"cash":0.15,"alternatives":0.05}

  -- Full fidelity photograph (serialized Phase-1 WealthSnapshot)
  snapshot_json jsonb not null,

  has_stale_values boolean not null default false,
  stale_sources text[] not null default '{}',

  created_at timestamptz not null default now()
);
create index wealth_snapshots_client_asof_idx on wealth_snapshots(client_id, as_of desc);
create index wealth_snapshots_client_trigger_idx on wealth_snapshots(client_id, trigger, as_of desc);
```

**Photograph semantics:** values are frozen at write time. If a valuator bug is fixed later, prior snapshots stay as they were — which is what audit and narrative both require.

### 4.2 `allocation_targets`

```sql
create table allocation_targets (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  effective_from timestamptz not null,
  effective_to timestamptz null,  -- null = currently active

  equity_pct numeric(5,2) not null check (equity_pct between 0 and 100),
  debt_pct numeric(5,2) not null check (debt_pct between 0 and 100),
  gold_pct numeric(5,2) not null check (gold_pct between 0 and 100),
  cash_pct numeric(5,2) not null check (cash_pct between 0 and 100),
  alternatives_pct numeric(5,2) not null check (alternatives_pct between 0 and 100),
  check (round((equity_pct + debt_pct + gold_pct + cash_pct + alternatives_pct)::numeric, 2) = 100),

  equity_band_pct numeric(5,2) not null default 5,
  debt_band_pct numeric(5,2) not null default 5,
  gold_band_pct numeric(5,2) not null default 2,
  cash_band_pct numeric(5,2) not null default 3,
  alternatives_band_pct numeric(5,2) not null default 3,

  rationale_event_id uuid not null references rationale_events(id),
  created_by_rm_id uuid not null references rms(id),
  created_at timestamptz not null default now()
);

-- Exactly one active target per client
create unique index allocation_targets_one_active_per_client
  on allocation_targets(client_id) where effective_to is null;

create index allocation_targets_client_history_idx
  on allocation_targets(client_id, effective_from desc);
```

The partial unique index enforces *exactly one active row per client*. Target changes are immutable inserts; the prior row's `effective_to` is stamped in the same transaction (see §6).

### 4.3 `rationale_events`

```sql
create table rationale_events (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  event_date timestamptz not null,           -- when the decision occurred
  event_type text not null check (event_type in (
    'target_change','rebalance','cash_deployment','tax_harvest',
    'liquidity_event','external_change','market_commentary','onboarding'
  )),
  title text not null check (char_length(title) <= 200),
  rationale_text text not null,
  snapshot_id uuid null references wealth_snapshots(id),
  linked_target_id uuid null references allocation_targets(id),
  created_by_rm_id uuid not null references rms(id),
  created_at timestamptz not null default now()
);
create index rationale_events_client_date_idx on rationale_events(client_id, event_date desc);
create index rationale_events_client_type_idx on rationale_events(client_id, event_type, event_date desc);
```

### 4.4 Tweak to existing `transactions` table

```sql
alter table transactions
  add column rationale_event_id uuid null references rationale_events(id);
-- transactions.rationale (text) stays for legacy seed data; new writes populate
-- rationale_event_id and leave rationale null.
```

### 4.5 Row-Level Security

All three new tables get RM-scoped policies modeled directly on Phase 1's `002_multi_asset.sql`: a row is visible iff its `client_id` resolves through `clients.rm_id` to `auth.uid()`. Concretely:

```sql
alter table wealth_snapshots enable row level security;
create policy "RM owns wealth_snapshots via client"
  on wealth_snapshots for all
  using (exists (
    select 1 from clients c
    where c.id = wealth_snapshots.client_id and c.rm_id = auth.uid()
  ));
-- Identical pattern for allocation_targets and rationale_events.
```

## 5. Allocation Rollup — Instrument Bucket → Economic Class

Phase 1 buckets are by instrument type; targets are by economic class. The mapping lives in a pure function `services/allocation_rollup.py::roll_up_to_classes(snapshot: WealthSnapshot) -> dict[str, Decimal]`:

| Phase-1 bucket | Mapped economic class |
|----------------|----------------------|
| `mutual_funds.category == 'equity'` | `equity` |
| `mutual_funds.category in ('debt','liquid')` | `debt` |
| `mutual_funds.category == 'hybrid'` | `equity` (conservative default; documented limitation — proper split requires equity/debt ratio metadata which Phase 1 does not capture) |
| `bonds` (all types) | `debt` |
| `gold_holdings` | `gold` |
| `cash_balances` | `cash` |
| `fixed_deposits` | `debt` |
| `insurance_policies` (surrender value) | `debt` |
| (no Phase-1 source) | `alternatives` (reserved; always 0 until alt-asset support lands) |

Rollup is computed against `current_value` for each holding. `total_liabilities` is *not* netted into class percentages — class % uses gross assets so it sums to 100. `net_worth` remains stored on the snapshot for narrative use.

**Hybrid MF limitation:** the spec acknowledges that mapping all hybrid funds to equity overstates equity exposure for debt-leaning hybrids. Phase 3 may add a per-fund equity ratio override. For Phase 2, the conservative default is documented and surfaced as a banner in the Allocation Target card (*"Hybrid MFs are counted as equity in this view."*).

## 6. Write Paths — Two-Step Cross-FK Resolution

The bidirectional FK between `wealth_snapshots` and `rationale_events` is resolved in code, not in DB. Both FKs are nullable.

### 6.1 Trigger: `report`

```
POST /reports/generate-stream (existing route, modified)
  → report_generator.generate_report(client_id):
      report_id = create_report_row(...)
      snapshot_id = snapshot_service.persist_snapshot(
        client_id, trigger='report', report_id=report_id
      )
      context = context_builder.build_context(client_id, report_id, snapshot_id)
      ...
```
No rationale event is created. `wealth_snapshots.rationale_event_id` is NULL.

### 6.2 Trigger: `rationale` (non-target event)

```
POST /clients/{id}/rationale-events
  body: {event_date, event_type, title, rationale_text, link_transaction_ids?}
  →
    1. INSERT rationale_events (snapshot_id=NULL, linked_target_id=NULL) → event_id
    2. snapshot_id = snapshot_service.persist_snapshot(
         client_id, trigger='rationale', rationale_event_id=event_id
       )
       (snapshot row has rationale_event_id=event_id set on insert)
    3. UPDATE rationale_events SET snapshot_id=snapshot_id WHERE id=event_id
    4. If link_transaction_ids non-empty:
       UPDATE transactions SET rationale_event_id=event_id
         WHERE id = ANY(link_transaction_ids) AND client_id=client_id
```
Steps 1–3 run in a single transaction. Step 4 is a separate transaction (failure to link transactions does not invalidate the event).

### 6.3 Trigger: `rationale` (target change)

```
PUT /clients/{id}/allocation-target
  body: {
    target: {equity_pct, debt_pct, gold_pct, cash_pct, alternatives_pct,
             equity_band_pct, debt_band_pct, gold_band_pct, cash_band_pct, alternatives_band_pct},
    rationale: {event_date, title, rationale_text}  -- event_type server-derived
  }
  → all in one DB transaction:
    0. exists_prior = SELECT 1 FROM allocation_targets
         WHERE client_id=client_id AND effective_to IS NULL
       resolved_event_type = 'target_change' if exists_prior else 'onboarding'
    1. INSERT rationale_events (event_type=resolved_event_type, snapshot_id=NULL,
         linked_target_id=NULL) → event_id
    2. UPDATE allocation_targets SET effective_to=now()
         WHERE client_id=client_id AND effective_to IS NULL
    3. INSERT allocation_targets (effective_from=now(), effective_to=NULL,
         rationale_event_id=event_id, ...target fields...) → target_id
    4. UPDATE rationale_events SET linked_target_id=target_id WHERE id=event_id
  → after commit, outside the transaction:
    5. snapshot_id = snapshot_service.persist_snapshot(
         client_id, trigger='rationale', rationale_event_id=event_id
       )
    6. UPDATE rationale_events SET snapshot_id=snapshot_id WHERE id=event_id
```

Snapshot persistence is *outside* the target-change transaction so a valuator failure does not roll back the legitimate target change. If steps 5–6 fail, the event row stays with `snapshot_id=NULL` and an entry is written to `error_logs`; the narrator tolerates missing snapshots.

### 6.4 Trigger: `monthly`

```
POST /jobs/monthly-snapshots  (EasyCron, JOB_SECRET header)
  for each client in clients:
    try:
      snapshot_service.persist_snapshot(client_id, trigger='monthly')
    except Exception as e:
      log to error_logs
  insert job_runs row with counts
```
Runs at 00:30 on the 1st of each month IST. No rationale event is created.

## 7. Models, DB Modules, Services

### 7.1 New Pydantic models (`backend/models/`)

- `wealth_snapshot.py`
  - `WealthSnapshotRow` — DB row shape (all columns).
  - `WealthSnapshotRead` — includes hydrated Phase-1 `WealthSnapshot` parsed from `snapshot_json`.
- `allocation_target.py`
  - `AllocationTarget` — 5 pcts, 5 bands, FK refs, validity range.
  - `AllocationTargetWrite` — request body for `PUT` (no FK refs, server fills them).
- `rationale_event.py`
  - `RationaleEvent` — full row.
  - `RationaleEventWrite` — request body.
  - `EventType` — `Literal['target_change','rebalance','cash_deployment','tax_harvest','liquidity_event','external_change','market_commentary','onboarding']`.

### 7.2 New CRUD modules (`backend/db/`)

- `wealth_snapshots_db.py`
  - `insert(row) -> id`
  - `get_latest(client_id) -> WealthSnapshotRow | None`
  - `get_at_or_before(client_id, as_of) -> WealthSnapshotRow | None`
  - `list_in_range(client_id, from_ts, to_ts) -> list[WealthSnapshotRow]`
- `allocation_targets_db.py`
  - `get_current(client_id) -> AllocationTarget | None`
  - `list_history(client_id) -> list[AllocationTarget]`
  - `change(client_id, new_target_data, rationale_event_id, rm_id) -> id` (atomic: stamps prior row's `effective_to`, inserts new row, both in one transaction)
- `rationale_events_db.py`
  - `insert(row) -> id`
  - `update_snapshot_id(event_id, snapshot_id) -> None`
  - `update_linked_target_id(event_id, target_id) -> None`
  - `get(event_id) -> RationaleEvent | None`
  - `list_in_range(client_id, from_ts, to_ts, types: list[EventType] | None = None) -> list[RationaleEvent]`

### 7.3 New service modules (`backend/services/`)

- `allocation_rollup.py` — pure function `roll_up_to_classes(snapshot: WealthSnapshot) -> dict[str, Decimal]`. Returns the 5 class percentages summing to 1.0. Documented hybrid-MF limitation.
- `snapshot_service.py` — `persist_snapshot(client_id, trigger, *, report_id=None, rationale_event_id=None, as_of=None) -> snapshot_id`. Single orchestrator used by all three triggers.
- `drift_service.py` — `compute_drift(client_id) -> dict[str, DriftEntry]`. For each of the 5 classes, returns `{actual_pct, target_pct, band_pct, in_band: bool, breach_direction: 'over'|'under'|None}`. Tolerates missing active target (returns `None`).

## 8. API Surface

All routes RM-scoped, RLS-enforced, mounted under existing `backend/routes/`. New file `backend/routes/wealth.py` for snapshots/targets/drift; rationale events extend `backend/routes/clients.py`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/clients/{id}/wealth-snapshots/latest` | Most recent snapshot |
| GET | `/clients/{id}/wealth-snapshots?from=&to=` | Snapshots in range |
| GET | `/clients/{id}/allocation-target` | Current active target |
| GET | `/clients/{id}/allocation-target/history` | Versioned list |
| PUT | `/clients/{id}/allocation-target` | Change target + create event (atomic, see §6.3) |
| POST | `/clients/{id}/rationale-events` | Log non-target event |
| GET | `/clients/{id}/rationale-events?from=&to=&types=` | List events |
| GET | `/clients/{id}/drift` | Per-class actual vs target with band flags |
| POST | `/jobs/monthly-snapshots` | Cron (JOB_SECRET header) |

## 9. Narrator Integration (`context_builder.py`)

The minimum wiring that makes Phase 2 worth shipping. `build_context(client_id, report_id, snapshot_id)` gains:

```python
context["change_tracking"] = {
  "current_snapshot": <hydrated WealthSnapshot from snapshot_id>,
  "prior_snapshot": <get_at_or_before(client_id, prior_report.created_at) or None>,
  "active_target": <get_current(client_id) or None>,
  "drift": <compute_drift(client_id) or {}>,
  "rationale_events_in_period": <list_in_range(
      client_id,
      from_ts = prior_snapshot.as_of if prior_snapshot else current_snapshot.as_of - 90 days,
      to_ts = current_snapshot.as_of
    ), oldest first>,
}
```

`prompt_builder.py` adds one new few-shot block:

> Use the `change_tracking` block to write a *"What changed since the last letter"* paragraph in the Performance section.
> - Compare `current_snapshot.allocation_pct` to `prior_snapshot.allocation_pct` and call out classes that moved more than 1 percentage point.
> - If `rationale_events_in_period` is non-empty, weave each event's `title` and `rationale_text` into the narrative in chronological order.
> - If any `drift.<class>.in_band == False`, flag it in the Next Steps section as *"<Class> is currently <over|under> target by <X>% (target <T>%, band ±<B>%); consider <rebalance direction>."*
> - If `has_stale_values == True`, soften with *"based on latest available NAVs"* or equivalent.
> - If `prior_snapshot` is None or `active_target` is None, omit those sections gracefully.

This is the only prompt change in Phase 2. The letter template structure is unchanged.

## 10. Frontend Minimums

Both additions live on `frontend/src/pages/ClientDetail.jsx`. No new top-level pages. No new chart libraries. Existing `components/ui/` primitives only.

### 10.1 Allocation Target card (new component `components/client/AllocationTargetCard.jsx`)

- Shows current target (5 horizontal bars with target % + ±band annotation).
- "Edit Target" button → modal `AllocationTargetModal.jsx`:
  - 5 percent inputs (must sum to 100, live validation).
  - 5 band inputs (defaults 5/5/2/3/3).
  - Rationale form (mandatory): `title` (max 200 char), `rationale_text` (textarea).
  - `event_type` is hidden, server-forced to `target_change`.
  - Submit → `PUT /clients/{id}/allocation-target`.
- Empty state (no active target): shows *"No allocation target set. Edit to create one."* — first submission creates the initial target row and an `onboarding` event (not `target_change`) when no prior target exists.

### 10.2 Rationale Events log (new component `components/client/RationaleEventsPanel.jsx`)

- Collapsible panel listing recent events: type chip (color by `event_type`), date, title, expand-to-read rationale_text.
- "Log Event" button → modal `RationaleEventModal.jsx`:
  - `event_type` selector (excludes `target_change` and `onboarding` — those are created automatically).
  - `event_date` (defaults to today).
  - `title`, `rationale_text`.
  - Optional transaction linker: multi-select from this client's transactions that don't yet have a `rationale_event_id`.
  - Submit → `POST /clients/{id}/rationale-events`.

### 10.3 What is *not* in Phase 2 UI

- Drift visualization (the `GET /drift` endpoint exists, but no UI consumes it yet — narrator does).
- Snapshot history charts.
- Target history viewer (history is queryable via API; no UI in Phase 2).

## 11. Seed Data — `seed_v3.sql`

For each of the 5 demo clients seeded in Phase 1:

1. Insert one `rationale_events` row with `event_type='onboarding'`, `event_date=clients.client_since`, `title="Initial allocation target set"`, generic `rationale_text`.
2. Insert one `allocation_targets` row, `effective_from=clients.client_since`, `effective_to=NULL`, linked to the onboarding event. Target values vary per client based on risk_profile:
   - Conservative: 25/55/8/10/2
   - Moderate: 45/35/8/10/2
   - Aggressive: 65/20/5/8/2
3. Insert one `wealth_snapshots` row with `trigger='monthly'`, `as_of=now()`, computed from current Phase-1 data, linked to neither report nor event.

No historical snapshots are backfilled. Phase 2 ships forward-only history.

## 12. Testing

The repo currently has no test framework. Phase 2 introduces `pytest` for the backend as a one-time setup. Frontend testing stays deferred.

### 12.1 Backend test setup
- `backend/requirements-dev.txt`: `pytest`, `pytest-asyncio`, `httpx`.
- `backend/tests/` directory with `conftest.py` providing a Supabase test-schema client.
- Tests run against a separate Supabase project (or `supabase start` local stack) — credentials in `.env.test`.

### 12.2 Required tests

- `tests/test_allocation_rollup.py` — deterministic mapping; one case per instrument-bucket type; hybrid-MF mapping; empty snapshot; net_worth not affecting class percentages.
- `tests/test_drift_service.py` — in-band, over, under, exactly at band edge, missing target, missing class, class with target=0.
- `tests/test_allocation_targets_db.py` — `change()` atomicity (prior row stamped, new row inserted, both visible after commit); partial unique index actually rejects a second active row; rollback on inner failure.
- `tests/test_snapshot_service.py` — persist_snapshot writes correct aggregates and JSONB; trigger field set correctly per call site.
- `tests/test_routes_wealth.py` — integration test against test schema: full `PUT /allocation-target` flow asserts event row, prior target stamped, new target row, snapshot row, all linked correctly.

No coverage threshold gate in Phase 2; just the tests above plus any added during implementation.

## 13. Error Handling & Stale Data

- All three trigger paths log to `error_logs` on failure and never crash the caller. Report-gen proceeds with empty `change_tracking` if snapshot insert fails.
- `has_stale_values` / `stale_sources` are carried through unchanged from Phase-1 `WealthSnapshot`; the narrator prompt block softens language when stale.
- `drift_service.compute_drift` tolerates rollup gaps: if `alternatives_pct` target is 0 and actual is 0, `in_band=True`; if target > 0 but no alternatives data, `breach_direction='under'`.
- The cross-FK two-step pattern means a snapshot can briefly exist with `rationale_event_id=NULL` waiting to be linked, or an event with `snapshot_id=NULL` if snapshot persistence fails. Both states are valid; queries tolerate them.

## 14. Migration & Rollout Order

1. Apply `003_change_tracking.sql` (creates 3 tables + indexes + RLS + `transactions.rationale_event_id` column).
2. Deploy backend with new models, DB modules, services, routes (feature-flag-free — endpoints are additive).
3. Deploy frontend with the two new `ClientDetail` components (no existing component changes).
4. Apply `seed_v3.sql` against demo data.
5. Add EasyCron job for `/jobs/monthly-snapshots`.
6. Update `context_builder.py` and `prompt_builder.py` to emit `change_tracking` block — first report generation after this step starts narrating change.

Rollback for any step is a backward SQL migration drop + revert deploy; no destructive operations on Phase-1 data.

## 15. Open Questions for Implementation

- **Hybrid MF split:** keep the "all hybrid → equity" rule, or read each MF's category-meta if seed data carries it? Default to the conservative rule; revisit in Phase 3.
- **Monthly cron timing:** 00:30 IST on the 1st is the proposal; final time is an Ops decision at implementation time.
- **Test Supabase project:** decide between local `supabase start` and a dedicated cloud test project at the start of implementation.

These are flagged as decisions to make during plan/implementation, not blockers on this design.
