# Phase 2 — Change-Tracking Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist wealth snapshots, versioned allocation targets, and rationale events so the Cohere narrator can describe how a client's wealth, allocation, and decisions evolved between letters.

**Architecture:** Three new tables (`wealth_snapshots`, `allocation_targets`, `rationale_events`) plus a `transactions.rationale_event_id` column. A `snapshot_service` orchestrator persists snapshots for three triggers (report / rationale / monthly cron). A pure `allocation_rollup` maps Phase-1 instrument buckets to 5 economic classes. A `drift_service` computes actual vs target with per-class bands. `context_builder` reads the three new tables to feed a new `change_tracking` block into the Cohere prompt.

**Tech Stack:** FastAPI, Supabase (Postgres + RLS), Pydantic v2, pytest + pytest-asyncio + httpx, React 18 with existing `components/ui/` primitives. Spec: `docs/superpowers/specs/2026-05-27-phase2-change-tracking-design.md`.

**File Map:**

```
backend/
  db_schema/migrations/003_change_tracking.sql      NEW
  db_schema/seed_v3.sql                             NEW
  db/sql/rpc_change_allocation_target.sql           NEW
  models/{rationale_event,allocation_target,wealth_snapshot}.py    NEW
  db/{rationale_events_db,allocation_targets_db,wealth_snapshots_db}.py  NEW
  services/{allocation_rollup,snapshot_service,drift_service}.py   NEW
  services/{context_builder,prompt_builder}.py      MODIFY
  routes/wealth.py                                  NEW
  routes/{clients,jobs}.py                          MODIFY
  tests/conftest.py + 9 test files                  NEW
  requirements-dev.txt, .env.test.example           NEW
frontend/src/
  components/client/{AllocationTargetCard,AllocationTargetModal,RationaleEventsPanel,RationaleEventModal}.jsx  NEW
  api/wealth.js                                     NEW
  pages/ClientDetail.jsx                            MODIFY
```

**Task order (bite-sized TDD):** test foundation → migration → 3 models → 3 DB CRUD → pure rollup → snapshot service → drift service → routes → cron → seed → narrator → frontend.

This plan is split into two files. Tasks 1–5 are below. Tasks 6–15 are in `2026-05-27-phase2-change-tracking-part2.md`.

---

## Task 1: Backend pytest setup

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/.env.test.example`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Add dev dependencies file**

Write `backend/requirements-dev.txt`:

```
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
python-dotenv==1.0.1
```

- [ ] **Step 2: Add test env template**

Write `backend/.env.test.example`:

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=replace-with-local-supabase-service-role
JOB_SECRET=test-job-secret
COHERE_API_KEY=test-not-used
```

- [ ] **Step 3: Create empty tests package init**

Write `backend/tests/__init__.py` as an empty file (single newline).

- [ ] **Step 4: Write conftest with fixtures**

Write `backend/tests/conftest.py`:

```python
"""Shared pytest fixtures for the Phase 2 backend test suite."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
if (_ROOT / ".env.test").exists():
    load_dotenv(_ROOT / ".env.test", override=True)
elif (_ROOT / ".env").exists():
    load_dotenv(_ROOT / ".env", override=False)


@pytest.fixture
def fake_client_id() -> str:
    """Stable demo client UUID — Rajesh Mehta from seed_v2.sql."""
    return "d62e9583-9d56-4e45-8665-e0634b3db42a"


@pytest.fixture
def random_client_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def fake_rm_id() -> str:
    return "00000000-0000-0000-0000-000000000001"
```

- [ ] **Step 5: Verify pytest discovers tests**

Run: `cd backend && python -m pytest --collect-only -q 2>&1 | tail -5`
Expected: `0 tests collected` or `no tests ran`, no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements-dev.txt backend/.env.test.example backend/tests/__init__.py backend/tests/conftest.py
git commit -m "test(backend): add pytest setup with conftest and env template"
```

---

## Task 2: Migration 003 — change-tracking tables

**Files:**
- Create: `backend/db_schema/migrations/003_change_tracking.sql`

- [ ] **Step 1: Write migration SQL**

Write `backend/db_schema/migrations/003_change_tracking.sql`:

```sql
-- Phase 2: change-tracking model
-- Adds wealth_snapshots, allocation_targets, rationale_events + RLS;
-- extends transactions with rationale_event_id.

-- rationale_events first (other tables FK to it). Back-FKs added after the
-- other tables exist (snapshot_id, linked_target_id).
create table rationale_events (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  event_date timestamptz not null,
  event_type text not null check (event_type in (
    'target_change','rebalance','cash_deployment','tax_harvest',
    'liquidity_event','external_change','market_commentary','onboarding'
  )),
  title text not null check (char_length(title) <= 200),
  rationale_text text not null,
  snapshot_id uuid null,
  linked_target_id uuid null,
  created_by_rm_id uuid not null references rms(id),
  created_at timestamptz not null default now()
);
create index rationale_events_client_date_idx
  on rationale_events(client_id, event_date desc);
create index rationale_events_client_type_idx
  on rationale_events(client_id, event_type, event_date desc);

create table wealth_snapshots (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  as_of timestamptz not null,
  trigger text not null check (trigger in ('report','rationale','monthly')),
  rationale_event_id uuid null references rationale_events(id),
  report_id uuid null references reports(id),

  net_worth numeric(18,2) not null,
  total_assets numeric(18,2) not null,
  total_liabilities numeric(18,2) not null,
  total_unrealised_gain numeric(18,2) not null,
  allocation_pct jsonb not null,

  snapshot_json jsonb not null,

  has_stale_values boolean not null default false,
  stale_sources text[] not null default '{}',

  created_at timestamptz not null default now()
);
create index wealth_snapshots_client_asof_idx
  on wealth_snapshots(client_id, as_of desc);
create index wealth_snapshots_client_trigger_idx
  on wealth_snapshots(client_id, trigger, as_of desc);

create table allocation_targets (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  effective_from timestamptz not null,
  effective_to timestamptz null,

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
create unique index allocation_targets_one_active_per_client
  on allocation_targets(client_id) where effective_to is null;
create index allocation_targets_client_history_idx
  on allocation_targets(client_id, effective_from desc);

-- Back-FKs from rationale_events
alter table rationale_events
  add constraint rationale_events_snapshot_fk
    foreign key (snapshot_id) references wealth_snapshots(id);
alter table rationale_events
  add constraint rationale_events_linked_target_fk
    foreign key (linked_target_id) references allocation_targets(id);

alter table transactions
  add column rationale_event_id uuid null references rationale_events(id);

-- RLS
alter table rationale_events enable row level security;
create policy "RM owns rationale_events via client"
  on rationale_events for all
  using (exists (
    select 1 from clients c
    where c.id = rationale_events.client_id and c.rm_id = auth.uid()
  ));

alter table wealth_snapshots enable row level security;
create policy "RM owns wealth_snapshots via client"
  on wealth_snapshots for all
  using (exists (
    select 1 from clients c
    where c.id = wealth_snapshots.client_id and c.rm_id = auth.uid()
  ));

alter table allocation_targets enable row level security;
create policy "RM owns allocation_targets via client"
  on allocation_targets for all
  using (exists (
    select 1 from clients c
    where c.id = allocation_targets.client_id and c.rm_id = auth.uid()
  ));
```

- [ ] **Step 2: Sanity-check the SQL parses**

Run: `python -c "s=open('backend/db_schema/migrations/003_change_tracking.sql').read(); assert s.count('create table')==3 and s.count('enable row level security')==3; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/db_schema/migrations/003_change_tracking.sql
git commit -m "feat(db): add 003_change_tracking migration"
```

---

## Task 3: RationaleEvent Pydantic model

**Files:**
- Create: `backend/models/rationale_event.py`
- Create: `backend/tests/test_models_rationale_event.py`

- [ ] **Step 1: Write the failing test**

Write `backend/tests/test_models_rationale_event.py`:

```python
"""Tests for backend.models.rationale_event."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.models.rationale_event import (
    EVENT_TYPES,
    RationaleEvent,
    RationaleEventWrite,
)


def test_event_types_has_eight_values():
    assert set(EVENT_TYPES) == {
        "target_change", "rebalance", "cash_deployment", "tax_harvest",
        "liquidity_event", "external_change", "market_commentary", "onboarding",
    }


def test_write_rejects_oversized_title():
    with pytest.raises(ValidationError):
        RationaleEventWrite(
            event_date=datetime.now(timezone.utc),
            event_type="rebalance",
            title="x" * 201,
            rationale_text="why",
        )


def test_write_accepts_minimal_body():
    body = RationaleEventWrite(
        event_date=datetime.now(timezone.utc),
        event_type="rebalance",
        title="Rebalanced equity",
        rationale_text="Trimmed equity by 4% after rally.",
    )
    assert body.link_transaction_ids == []


def test_full_row_round_trip():
    row = RationaleEvent.model_validate({
        "id": "11111111-1111-1111-1111-111111111111",
        "client_id": "22222222-2222-2222-2222-222222222222",
        "event_date": "2026-05-01T10:00:00+00:00",
        "event_type": "tax_harvest",
        "title": "Tax-loss harvest",
        "rationale_text": "Booked losses in XYZ.",
        "snapshot_id": None,
        "linked_target_id": None,
        "created_by_rm_id": "33333333-3333-3333-3333-333333333333",
        "created_at": "2026-05-01T10:05:00+00:00",
    })
    assert row.event_type == "tax_harvest"
    assert row.snapshot_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models_rationale_event.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.models.rationale_event'`.

- [ ] **Step 3: Implement the model**

Write `backend/models/rationale_event.py`:

```python
"""Pydantic models for rationale_events rows."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

EventType = Literal[
    "target_change", "rebalance", "cash_deployment", "tax_harvest",
    "liquidity_event", "external_change", "market_commentary", "onboarding",
]

EVENT_TYPES: tuple[str, ...] = (
    "target_change", "rebalance", "cash_deployment", "tax_harvest",
    "liquidity_event", "external_change", "market_commentary", "onboarding",
)


class RationaleEventWrite(BaseModel):
    """Request body for POST /clients/{id}/rationale-events."""

    event_date: datetime
    event_type: EventType
    title: str = Field(min_length=1, max_length=200)
    rationale_text: str = Field(min_length=1)
    link_transaction_ids: list[UUID] = Field(default_factory=list)


class RationaleEvent(BaseModel):
    """Row as stored in the rationale_events table."""

    id: UUID
    client_id: UUID
    event_date: datetime
    event_type: EventType
    title: str
    rationale_text: str
    snapshot_id: UUID | None = None
    linked_target_id: UUID | None = None
    created_by_rm_id: UUID
    created_at: datetime
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models_rationale_event.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/models/rationale_event.py backend/tests/test_models_rationale_event.py
git commit -m "feat(models): add RationaleEvent + RationaleEventWrite"
```

---

## Task 4: AllocationTarget Pydantic model

**Files:**
- Create: `backend/models/allocation_target.py`
- Create: `backend/tests/test_models_allocation_target.py`

- [ ] **Step 1: Write the failing test**

Write `backend/tests/test_models_allocation_target.py`:

```python
"""Tests for backend.models.allocation_target."""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.models.allocation_target import AllocationTarget, AllocationTargetWrite


def _body(**overrides):
    base = {
        "equity_pct": Decimal("45"),
        "debt_pct": Decimal("35"),
        "gold_pct": Decimal("8"),
        "cash_pct": Decimal("10"),
        "alternatives_pct": Decimal("2"),
        "equity_band_pct": Decimal("5"),
        "debt_band_pct": Decimal("5"),
        "gold_band_pct": Decimal("2"),
        "cash_band_pct": Decimal("3"),
        "alternatives_band_pct": Decimal("3"),
        "rationale": {
            "event_date": "2026-05-01T00:00:00+00:00",
            "title": "Quarterly rebalance",
            "rationale_text": "Shifted to neutral after rally.",
        },
    }
    base.update(overrides)
    return base


def test_write_accepts_summing_to_100():
    body = AllocationTargetWrite.model_validate(_body())
    assert body.equity_pct == Decimal("45")
    assert body.rationale.title == "Quarterly rebalance"


def test_write_rejects_sum_not_100():
    with pytest.raises(ValidationError):
        AllocationTargetWrite.model_validate(_body(equity_pct=Decimal("50")))


def test_write_rejects_negative_pct():
    bad = _body(equity_pct=Decimal("-1"), debt_pct=Decimal("81"))
    with pytest.raises(ValidationError):
        AllocationTargetWrite.model_validate(bad)


def test_target_row_validates():
    row = AllocationTarget.model_validate({
        "id": "11111111-1111-1111-1111-111111111111",
        "client_id": "22222222-2222-2222-2222-222222222222",
        "effective_from": "2026-01-01T00:00:00+00:00",
        "effective_to": None,
        "equity_pct": "45", "debt_pct": "35", "gold_pct": "8",
        "cash_pct": "10", "alternatives_pct": "2",
        "equity_band_pct": "5", "debt_band_pct": "5", "gold_band_pct": "2",
        "cash_band_pct": "3", "alternatives_band_pct": "3",
        "rationale_event_id": "33333333-3333-3333-3333-333333333333",
        "created_by_rm_id": "44444444-4444-4444-4444-444444444444",
        "created_at": "2026-01-01T00:00:01+00:00",
    })
    assert row.effective_to is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models_allocation_target.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the model**

Write `backend/models/allocation_target.py`:

```python
"""Pydantic models for allocation_targets rows."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

_HUNDRED = Decimal("100")
_TWO_PLACES = Decimal("0.01")


class _RationaleSubBody(BaseModel):
    event_date: datetime
    title: str = Field(min_length=1, max_length=200)
    rationale_text: str = Field(min_length=1)


class AllocationTargetWrite(BaseModel):
    equity_pct: Decimal = Field(ge=0, le=100)
    debt_pct: Decimal = Field(ge=0, le=100)
    gold_pct: Decimal = Field(ge=0, le=100)
    cash_pct: Decimal = Field(ge=0, le=100)
    alternatives_pct: Decimal = Field(ge=0, le=100)

    equity_band_pct: Decimal = Field(default=Decimal("5"), ge=0, le=100)
    debt_band_pct: Decimal = Field(default=Decimal("5"), ge=0, le=100)
    gold_band_pct: Decimal = Field(default=Decimal("2"), ge=0, le=100)
    cash_band_pct: Decimal = Field(default=Decimal("3"), ge=0, le=100)
    alternatives_band_pct: Decimal = Field(default=Decimal("3"), ge=0, le=100)

    rationale: _RationaleSubBody

    @model_validator(mode="after")
    def _pcts_sum_to_100(self) -> "AllocationTargetWrite":
        total = (
            self.equity_pct + self.debt_pct + self.gold_pct
            + self.cash_pct + self.alternatives_pct
        )
        if total.quantize(_TWO_PLACES) != _HUNDRED:
            raise ValueError(f"Allocation pcts must sum to 100, got {total}")
        return self


class AllocationTarget(BaseModel):
    id: UUID
    client_id: UUID
    effective_from: datetime
    effective_to: datetime | None = None

    equity_pct: Decimal
    debt_pct: Decimal
    gold_pct: Decimal
    cash_pct: Decimal
    alternatives_pct: Decimal

    equity_band_pct: Decimal
    debt_band_pct: Decimal
    gold_band_pct: Decimal
    cash_band_pct: Decimal
    alternatives_band_pct: Decimal

    rationale_event_id: UUID
    created_by_rm_id: UUID
    created_at: datetime
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models_allocation_target.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/models/allocation_target.py backend/tests/test_models_allocation_target.py
git commit -m "feat(models): add AllocationTarget + AllocationTargetWrite"
```

---

## Task 5: WealthSnapshotRow Pydantic model

**Files:**
- Create: `backend/models/wealth_snapshot.py`
- Create: `backend/tests/test_models_wealth_snapshot.py`

- [ ] **Step 1: Write the failing test**

Write `backend/tests/test_models_wealth_snapshot.py`:

```python
"""Tests for backend.models.wealth_snapshot."""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.models.wealth_snapshot import WealthSnapshotRow


def _row(**overrides):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "client_id": "22222222-2222-2222-2222-222222222222",
        "as_of": "2026-05-01T00:00:00+00:00",
        "trigger": "monthly",
        "rationale_event_id": None,
        "report_id": None,
        "net_worth": "1000000.00",
        "total_assets": "1200000.00",
        "total_liabilities": "200000.00",
        "total_unrealised_gain": "50000.00",
        "allocation_pct": {
            "equity": 0.45, "debt": 0.35, "gold": 0.08,
            "cash": 0.10, "alternatives": 0.02,
        },
        "snapshot_json": {"net_worth": "1000000.00"},
        "has_stale_values": False,
        "stale_sources": [],
        "created_at": "2026-05-01T00:00:01+00:00",
    }
    base.update(overrides)
    return base


def test_row_parses_minimum():
    row = WealthSnapshotRow.model_validate(_row())
    assert row.trigger == "monthly"
    assert row.allocation_pct["equity"] == Decimal("0.45")


def test_row_rejects_bad_trigger():
    with pytest.raises(ValidationError):
        WealthSnapshotRow.model_validate(_row(trigger="adhoc"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models_wealth_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the model**

Write `backend/models/wealth_snapshot.py`:

```python
"""Pydantic models for wealth_snapshots rows."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Trigger = Literal["report", "rationale", "monthly"]


class WealthSnapshotRow(BaseModel):
    id: UUID
    client_id: UUID
    as_of: datetime
    trigger: Trigger
    rationale_event_id: UUID | None = None
    report_id: UUID | None = None

    net_worth: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    total_unrealised_gain: Decimal
    allocation_pct: dict[str, Decimal]

    snapshot_json: dict

    has_stale_values: bool = False
    stale_sources: list[str] = Field(default_factory=list)

    created_at: datetime
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models_wealth_snapshot.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/models/wealth_snapshot.py backend/tests/test_models_wealth_snapshot.py
git commit -m "feat(models): add WealthSnapshotRow"
```

---

**Continue with Tasks 6–15 in:** `docs/superpowers/plans/2026-05-27-phase2-change-tracking-part2.md`
