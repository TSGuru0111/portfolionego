# Phase 2 — Change-Tracking Plan (Part 2: Tasks 6–11)

> Continuation of `2026-05-27-phase2-change-tracking.md`. Same execution rules apply.

---

## Task 6: allocation_rollup pure service

**Files:**
- Create: `backend/services/allocation_rollup.py`
- Create: `backend/tests/test_allocation_rollup.py`

Maps Phase-1 instrument buckets to 5 economic classes. Pure function; no DB. Hybrid MFs map to equity (conservative default — spec §5).

- [ ] **Step 1: Inspect the Phase-1 WealthSnapshot shape**

Run: `head -100 backend/models/wealth.py`
Expected: shows `WealthSnapshot` with `mutual_funds`, `bonds`, `gold`, `cash`, `fixed_deposits`, `insurance` buckets, each having `holdings` lists with `current_value` (and `category` on MFs). Adjust the test below if field names differ from what is shown here.

- [ ] **Step 2: Write the failing test**

Write `backend/tests/test_allocation_rollup.py`:

```python
"""Tests for backend.services.allocation_rollup.roll_up_to_classes."""
from __future__ import annotations

from decimal import Decimal

from backend.services.allocation_rollup import roll_up_to_classes


class _Holding:
    def __init__(self, current_value, category=None):
        self.current_value = Decimal(str(current_value))
        self.category = category


class _Bucket:
    def __init__(self, holdings):
        self.holdings = holdings


class _Snap:
    """Stub: rollup reads `.<bucket>.holdings` and each holding's `.current_value` / `.category`."""
    def __init__(self, **buckets):
        self.mutual_funds = _Bucket(buckets.get("mutual_funds", []))
        self.bonds = _Bucket(buckets.get("bonds", []))
        self.gold = _Bucket(buckets.get("gold", []))
        self.cash = _Bucket(buckets.get("cash", []))
        self.fixed_deposits = _Bucket(buckets.get("fixed_deposits", []))
        self.insurance = _Bucket(buckets.get("insurance", []))


def test_pure_equity_mf_rolls_to_equity():
    snap = _Snap(mutual_funds=[_Holding(100, "equity")])
    out = roll_up_to_classes(snap)
    assert out == {"equity": Decimal("1"), "debt": Decimal("0"),
                   "gold": Decimal("0"), "cash": Decimal("0"),
                   "alternatives": Decimal("0")}


def test_debt_mf_and_bond_both_go_to_debt():
    snap = _Snap(
        mutual_funds=[_Holding(50, "debt")],
        bonds=[_Holding(50)],
    )
    out = roll_up_to_classes(snap)
    assert out["debt"] == Decimal("1")
    assert out["equity"] == Decimal("0")


def test_hybrid_mf_maps_to_equity():
    snap = _Snap(mutual_funds=[_Holding(100, "hybrid")])
    assert roll_up_to_classes(snap)["equity"] == Decimal("1")


def test_liquid_mf_maps_to_debt():
    snap = _Snap(mutual_funds=[_Holding(100, "liquid")])
    assert roll_up_to_classes(snap)["debt"] == Decimal("1")


def test_fd_and_insurance_map_to_debt():
    snap = _Snap(
        fixed_deposits=[_Holding(60)],
        insurance=[_Holding(40)],
    )
    assert roll_up_to_classes(snap)["debt"] == Decimal("1")


def test_full_mix_sums_to_one():
    snap = _Snap(
        mutual_funds=[_Holding(45, "equity")],
        bonds=[_Holding(35)],
        gold=[_Holding(8)],
        cash=[_Holding(10)],
        fixed_deposits=[_Holding(2)],
    )
    out = roll_up_to_classes(snap)
    assert sum(out.values()) == Decimal("1")
    assert out["alternatives"] == Decimal("0")


def test_empty_snapshot_returns_zeros():
    out = roll_up_to_classes(_Snap())
    assert out == {"equity": Decimal("0"), "debt": Decimal("0"),
                   "gold": Decimal("0"), "cash": Decimal("0"),
                   "alternatives": Decimal("0")}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_allocation_rollup.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Implement the service**

Write `backend/services/allocation_rollup.py`:

```python
"""Pure rollup: Phase-1 instrument buckets -> 5 economic classes.

Hybrid MFs map to equity (conservative default). See spec section 5.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

_CLASSES = ("equity", "debt", "gold", "cash", "alternatives")

_MF_CATEGORY_MAP = {
    "equity": "equity",
    "debt": "debt",
    "liquid": "debt",
    "hybrid": "equity",  # conservative default
}


def _value(h: Any) -> Decimal:
    v = getattr(h, "current_value", None)
    if v is None:
        return Decimal("0")
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _holdings(bucket: Any) -> list[Any]:
    if bucket is None:
        return []
    return list(getattr(bucket, "holdings", []) or [])


def roll_up_to_classes(snapshot: Any) -> dict[str, Decimal]:
    """Return percentages (0..1) per economic class, summing to 1.0 unless empty."""
    totals = {c: Decimal("0") for c in _CLASSES}

    for mf in _holdings(getattr(snapshot, "mutual_funds", None)):
        cls = _MF_CATEGORY_MAP.get(getattr(mf, "category", None), "equity")
        totals[cls] += _value(mf)

    for b in _holdings(getattr(snapshot, "bonds", None)):
        totals["debt"] += _value(b)
    for g in _holdings(getattr(snapshot, "gold", None)):
        totals["gold"] += _value(g)
    for c in _holdings(getattr(snapshot, "cash", None)):
        totals["cash"] += _value(c)
    for fd in _holdings(getattr(snapshot, "fixed_deposits", None)):
        totals["debt"] += _value(fd)
    for ins in _holdings(getattr(snapshot, "insurance", None)):
        totals["debt"] += _value(ins)

    gross = sum(totals.values())
    if gross == 0:
        return totals
    return {c: (totals[c] / gross) for c in _CLASSES}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_allocation_rollup.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/services/allocation_rollup.py backend/tests/test_allocation_rollup.py
git commit -m "feat(services): add allocation_rollup pure rollup"
```

---

## Task 7: wealth_snapshots_db CRUD

**Files:**
- Create: `backend/db/wealth_snapshots_db.py`
- Create: `backend/tests/test_wealth_snapshots_db.py`

- [ ] **Step 1: Write the failing test**

Write `backend/tests/test_wealth_snapshots_db.py`:

```python
"""Tests for backend.db.wealth_snapshots_db (mocked Supabase)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.db import wealth_snapshots_db


def _chain(returned_data):
    res = MagicMock()
    res.data = returned_data
    c = MagicMock()
    for m in ("insert", "select", "eq", "lte", "gte", "order", "limit", "single"):
        getattr(c, m).return_value = c
    c.execute.return_value = res
    return c


@pytest.mark.asyncio
async def test_insert_returns_id():
    c = _chain([{"id": "11111111-1111-1111-1111-111111111111"}])
    with patch.object(wealth_snapshots_db, "get_supabase") as gs:
        sb = MagicMock()
        sb.table.return_value = c
        gs.return_value = sb
        out = await wealth_snapshots_db.insert({
            "client_id": "22222222-2222-2222-2222-222222222222",
            "as_of": "2026-05-01T00:00:00+00:00",
            "trigger": "monthly",
            "net_worth": "1000000", "total_assets": "1200000",
            "total_liabilities": "200000", "total_unrealised_gain": "0",
            "allocation_pct": {"equity": 1, "debt": 0, "gold": 0,
                               "cash": 0, "alternatives": 0},
            "snapshot_json": {},
            "has_stale_values": False, "stale_sources": [],
        })
    assert out == "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_empty():
    c = _chain([])
    with patch.object(wealth_snapshots_db, "get_supabase") as gs:
        sb = MagicMock()
        sb.table.return_value = c
        gs.return_value = sb
        out = await wealth_snapshots_db.get_latest("22222222-2222-2222-2222-222222222222")
    assert out is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_wealth_snapshots_db.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the CRUD module**

Write `backend/db/wealth_snapshots_db.py`:

```python
"""CRUD for wealth_snapshots."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.supabase_client import get_supabase

_TABLE = "wealth_snapshots"


async def insert(row: dict[str, Any]) -> str:
    sb = get_supabase()
    res = sb.table(_TABLE).insert(row).select("id").single().execute()
    return res.data["id"]


async def get_latest(client_id: str) -> dict[str, Any] | None:
    sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", client_id)
        .order("as_of", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def get_at_or_before(client_id: str, as_of: datetime) -> dict[str, Any] | None:
    sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", client_id)
        .lte("as_of", as_of.isoformat())
        .order("as_of", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def list_in_range(
    client_id: str, from_ts: datetime, to_ts: datetime
) -> list[dict[str, Any]]:
    sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", client_id)
        .gte("as_of", from_ts.isoformat())
        .lte("as_of", to_ts.isoformat())
        .order("as_of", desc=False)
        .execute()
    )
    return res.data or []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_wealth_snapshots_db.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/db/wealth_snapshots_db.py backend/tests/test_wealth_snapshots_db.py
git commit -m "feat(db): add wealth_snapshots_db CRUD"
```

---

## Task 8: rationale_events_db CRUD

**Files:**
- Create: `backend/db/rationale_events_db.py`
- Create: `backend/tests/test_rationale_events_db.py`

- [ ] **Step 1: Write the failing test**

Write `backend/tests/test_rationale_events_db.py`:

```python
"""Tests for backend.db.rationale_events_db."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.db import rationale_events_db


def _chain(returned_data):
    res = MagicMock()
    res.data = returned_data
    c = MagicMock()
    for m in ("insert", "select", "update", "eq", "in_", "gte", "lte",
              "order", "limit", "single"):
        getattr(c, m).return_value = c
    c.execute.return_value = res
    return c


@pytest.mark.asyncio
async def test_insert_returns_id():
    c = _chain([{"id": "11111111-1111-1111-1111-111111111111"}])
    with patch.object(rationale_events_db, "get_supabase") as gs:
        sb = MagicMock()
        sb.table.return_value = c
        gs.return_value = sb
        out = await rationale_events_db.insert({
            "client_id": "22222222-2222-2222-2222-222222222222",
            "event_date": "2026-05-01T00:00:00+00:00",
            "event_type": "rebalance",
            "title": "Rebalance",
            "rationale_text": "why",
            "created_by_rm_id": "33333333-3333-3333-3333-333333333333",
        })
    assert out == "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_update_snapshot_id_calls_update():
    c = _chain([])
    with patch.object(rationale_events_db, "get_supabase") as gs:
        sb = MagicMock()
        sb.table.return_value = c
        gs.return_value = sb
        await rationale_events_db.update_snapshot_id("ev-id", "snap-id")
    c.update.assert_called_with({"snapshot_id": "snap-id"})


@pytest.mark.asyncio
async def test_list_in_range_filters_types():
    c = _chain([{"id": "e1"}, {"id": "e2"}])
    with patch.object(rationale_events_db, "get_supabase") as gs:
        sb = MagicMock()
        sb.table.return_value = c
        gs.return_value = sb
        out = await rationale_events_db.list_in_range(
            "22222222-2222-2222-2222-222222222222",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 12, 31, tzinfo=timezone.utc),
            types=["rebalance", "tax_harvest"],
        )
    assert len(out) == 2
    c.in_.assert_called_with("event_type", ["rebalance", "tax_harvest"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_rationale_events_db.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the CRUD module**

Write `backend/db/rationale_events_db.py`:

```python
"""CRUD for rationale_events."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.supabase_client import get_supabase

_TABLE = "rationale_events"


async def insert(row: dict[str, Any]) -> str:
    sb = get_supabase()
    res = sb.table(_TABLE).insert(row).select("id").single().execute()
    return res.data["id"]


async def get(event_id: str) -> dict[str, Any] | None:
    sb = get_supabase()
    res = sb.table(_TABLE).select("*").eq("id", event_id).limit(1).execute()
    return res.data[0] if res.data else None


async def update_snapshot_id(event_id: str, snapshot_id: str) -> None:
    sb = get_supabase()
    sb.table(_TABLE).update({"snapshot_id": snapshot_id}).eq("id", event_id).execute()


async def update_linked_target_id(event_id: str, target_id: str) -> None:
    sb = get_supabase()
    sb.table(_TABLE).update({"linked_target_id": target_id}).eq("id", event_id).execute()


async def list_in_range(
    client_id: str,
    from_ts: datetime,
    to_ts: datetime,
    types: list[str] | None = None,
) -> list[dict[str, Any]]:
    sb = get_supabase()
    q = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", client_id)
        .gte("event_date", from_ts.isoformat())
        .lte("event_date", to_ts.isoformat())
    )
    if types:
        q = q.in_("event_type", types)
    res = q.order("event_date", desc=False).execute()
    return res.data or []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_rationale_events_db.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/db/rationale_events_db.py backend/tests/test_rationale_events_db.py
git commit -m "feat(db): add rationale_events_db CRUD"
```

---

## Task 9: allocation_targets_db + atomic change RPC

**Files:**
- Create: `backend/db/sql/rpc_change_allocation_target.sql`
- Create: `backend/db/allocation_targets_db.py`
- Create: `backend/tests/test_allocation_targets_db.py`

The `change()` operation must be atomic. We use a Postgres function (RPC) to guarantee a single transaction stamps the prior `effective_to` and inserts the new active row.

- [ ] **Step 1: Write the RPC SQL**

Write `backend/db/sql/rpc_change_allocation_target.sql`:

```sql
-- Atomic allocation-target change.
-- Stamps prior active row's effective_to to now() and inserts a new active row
-- in one transaction. Returns the new row's id.

create or replace function change_allocation_target(
  p_client_id uuid,
  p_rationale_event_id uuid,
  p_rm_id uuid,
  p_equity_pct numeric,
  p_debt_pct numeric,
  p_gold_pct numeric,
  p_cash_pct numeric,
  p_alternatives_pct numeric,
  p_equity_band_pct numeric,
  p_debt_band_pct numeric,
  p_gold_band_pct numeric,
  p_cash_band_pct numeric,
  p_alternatives_band_pct numeric
) returns uuid
language plpgsql
security definer
as $$
declare
  new_id uuid;
  now_ts timestamptz := now();
begin
  update allocation_targets
    set effective_to = now_ts
    where client_id = p_client_id and effective_to is null;

  insert into allocation_targets (
    client_id, effective_from, effective_to,
    equity_pct, debt_pct, gold_pct, cash_pct, alternatives_pct,
    equity_band_pct, debt_band_pct, gold_band_pct, cash_band_pct, alternatives_band_pct,
    rationale_event_id, created_by_rm_id
  ) values (
    p_client_id, now_ts, null,
    p_equity_pct, p_debt_pct, p_gold_pct, p_cash_pct, p_alternatives_pct,
    p_equity_band_pct, p_debt_band_pct, p_gold_band_pct, p_cash_band_pct, p_alternatives_band_pct,
    p_rationale_event_id, p_rm_id
  )
  returning id into new_id;

  return new_id;
end;
$$;
```

- [ ] **Step 2: Write the failing test**

Write `backend/tests/test_allocation_targets_db.py`:

```python
"""Tests for backend.db.allocation_targets_db."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from backend.db import allocation_targets_db


def _chain(returned_data):
    res = MagicMock()
    res.data = returned_data
    c = MagicMock()
    for m in ("select", "eq", "is_", "order", "limit"):
        getattr(c, m).return_value = c
    c.execute.return_value = res
    return c


@pytest.mark.asyncio
async def test_get_current_returns_active_row():
    c = _chain([{"id": "t1", "client_id": "c1", "effective_to": None}])
    with patch.object(allocation_targets_db, "get_supabase") as gs:
        sb = MagicMock()
        sb.table.return_value = c
        gs.return_value = sb
        out = await allocation_targets_db.get_current("c1")
    assert out["id"] == "t1"
    c.is_.assert_called_with("effective_to", "null")


@pytest.mark.asyncio
async def test_change_calls_rpc_and_returns_id():
    res = MagicMock()
    res.data = "new-target-id"
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = res
    with patch.object(allocation_targets_db, "get_supabase", return_value=sb):
        out = await allocation_targets_db.change(
            client_id="c1",
            rationale_event_id="e1",
            rm_id="rm1",
            pcts={"equity": Decimal("45"), "debt": Decimal("35"),
                  "gold": Decimal("8"), "cash": Decimal("10"),
                  "alternatives": Decimal("2")},
            bands={"equity": Decimal("5"), "debt": Decimal("5"),
                   "gold": Decimal("2"), "cash": Decimal("3"),
                   "alternatives": Decimal("3")},
        )
    sb.rpc.assert_called_once()
    args = sb.rpc.call_args[0]
    assert args[0] == "change_allocation_target"
    assert args[1]["p_client_id"] == "c1"
    assert args[1]["p_equity_pct"] == "45"
    assert out == "new-target-id"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_allocation_targets_db.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Implement the CRUD module**

Write `backend/db/allocation_targets_db.py`:

```python
"""CRUD for allocation_targets, with an atomic `change` via RPC."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.db.supabase_client import get_supabase

_TABLE = "allocation_targets"


async def get_current(client_id: str) -> dict[str, Any] | None:
    sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", client_id)
        .is_("effective_to", "null")
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def list_history(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", client_id)
        .order("effective_from", desc=True)
        .execute()
    )
    return res.data or []


async def change(
    *,
    client_id: str,
    rationale_event_id: str,
    rm_id: str,
    pcts: dict[str, Decimal],
    bands: dict[str, Decimal],
) -> str:
    """Atomically stamp the prior active row and insert a new active row.

    Returns the new target id.
    """
    sb = get_supabase()
    payload = {
        "p_client_id": client_id,
        "p_rationale_event_id": rationale_event_id,
        "p_rm_id": rm_id,
        "p_equity_pct": str(pcts["equity"]),
        "p_debt_pct": str(pcts["debt"]),
        "p_gold_pct": str(pcts["gold"]),
        "p_cash_pct": str(pcts["cash"]),
        "p_alternatives_pct": str(pcts["alternatives"]),
        "p_equity_band_pct": str(bands["equity"]),
        "p_debt_band_pct": str(bands["debt"]),
        "p_gold_band_pct": str(bands["gold"]),
        "p_cash_band_pct": str(bands["cash"]),
        "p_alternatives_band_pct": str(bands["alternatives"]),
    }
    res = sb.rpc("change_allocation_target", payload).execute()
    return res.data
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_allocation_targets_db.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/db/sql/rpc_change_allocation_target.sql backend/db/allocation_targets_db.py backend/tests/test_allocation_targets_db.py
git commit -m "feat(db): add allocation_targets_db with atomic change RPC"
```

---

## Task 10: snapshot_service.persist_snapshot

**Files:**
- Create: `backend/services/snapshot_service.py`
- Create: `backend/tests/test_snapshot_service.py`

Orchestrates: `wealth_aggregator.build_wealth_snapshot` → `roll_up_to_classes` → `wealth_snapshots_db.insert`. Used by all three triggers.

- [ ] **Step 1: Write the failing test**

Write `backend/tests/test_snapshot_service.py`:

```python
"""Tests for backend.services.snapshot_service.persist_snapshot."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services import snapshot_service


@pytest.fixture
def fake_snapshot():
    s = MagicMock()
    s.net_worth = Decimal("1000000")
    s.has_stale_values = False
    s.stale_sources = []
    s.total_unrealised_gain = Decimal("50000")
    s.mutual_funds = MagicMock(total_current_value=Decimal("600000"), holdings=[])
    s.bonds = MagicMock(total_current_value=Decimal("200000"), holdings=[])
    s.gold = MagicMock(total_current_value=Decimal("80000"), holdings=[])
    s.cash = MagicMock(total_current_value=Decimal("120000"), holdings=[])
    s.fixed_deposits = MagicMock(total_current_value=Decimal("0"), holdings=[])
    s.insurance = MagicMock(total_current_value=Decimal("0"), holdings=[])
    s.liabilities = MagicMock(total_outstanding=Decimal("0"), holdings=[])
    s.model_dump.return_value = {"net_worth": "1000000"}
    return s


@pytest.mark.asyncio
async def test_persist_snapshot_report_trigger(fake_snapshot):
    with patch.object(snapshot_service, "build_wealth_snapshot",
                      return_value=fake_snapshot), \
         patch.object(snapshot_service, "roll_up_to_classes",
                      return_value={"equity": Decimal("0.6"), "debt": Decimal("0.2"),
                                    "gold": Decimal("0.08"), "cash": Decimal("0.12"),
                                    "alternatives": Decimal("0")}), \
         patch.object(snapshot_service.wealth_snapshots_db, "insert",
                      new=AsyncMock(return_value="snap-id")) as ins:
        out = await snapshot_service.persist_snapshot(
            client_id="c1", trigger="report", report_id="r1",
        )
    assert out == "snap-id"
    row = ins.call_args[0][0]
    assert row["trigger"] == "report"
    assert row["report_id"] == "r1"
    assert row["rationale_event_id"] is None
    assert row["client_id"] == "c1"
    assert row["allocation_pct"]["equity"] == "0.6"


@pytest.mark.asyncio
async def test_persist_snapshot_rationale_trigger(fake_snapshot):
    with patch.object(snapshot_service, "build_wealth_snapshot",
                      return_value=fake_snapshot), \
         patch.object(snapshot_service, "roll_up_to_classes",
                      return_value={"equity": Decimal("0.6"), "debt": Decimal("0.2"),
                                    "gold": Decimal("0.08"), "cash": Decimal("0.12"),
                                    "alternatives": Decimal("0")}), \
         patch.object(snapshot_service.wealth_snapshots_db, "insert",
                      new=AsyncMock(return_value="snap-id")) as ins:
        await snapshot_service.persist_snapshot(
            client_id="c1", trigger="rationale", rationale_event_id="e1",
        )
    row = ins.call_args[0][0]
    assert row["trigger"] == "rationale"
    assert row["rationale_event_id"] == "e1"
    assert row["report_id"] is None


@pytest.mark.asyncio
async def test_persist_snapshot_rejects_bad_trigger():
    with pytest.raises(ValueError, match="trigger"):
        await snapshot_service.persist_snapshot(client_id="c1", trigger="foo")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_snapshot_service.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the service**

Write `backend/services/snapshot_service.py`:

```python
"""Snapshot orchestrator: aggregate -> rollup -> persist."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from backend.db import wealth_snapshots_db
from backend.services.allocation_rollup import roll_up_to_classes
from backend.services.wealth_aggregator import build_wealth_snapshot

_VALID_TRIGGERS = {"report", "rationale", "monthly"}


def _decimal_to_str(d: dict[str, Decimal]) -> dict[str, str]:
    return {k: str(v) for k, v in d.items()}


async def persist_snapshot(
    *,
    client_id: str,
    trigger: str,
    report_id: str | None = None,
    rationale_event_id: str | None = None,
    as_of: date | None = None,
) -> str:
    """Build a wealth snapshot, persist it, return its id."""
    if trigger not in _VALID_TRIGGERS:
        raise ValueError(f"Invalid trigger: {trigger}")

    snap = build_wealth_snapshot(client_id, as_of)
    rollup = roll_up_to_classes(snap)

    total_assets = Decimal("0")
    for b in ("mutual_funds", "bonds", "gold", "cash", "fixed_deposits", "insurance"):
        bucket = getattr(snap, b, None)
        total_assets += getattr(bucket, "total_current_value", Decimal("0"))

    total_liabs = getattr(
        getattr(snap, "liabilities", None), "total_outstanding", Decimal("0")
    )

    now = datetime.now(timezone.utc)
    row: dict[str, Any] = {
        "client_id": client_id,
        "as_of": now.isoformat(),
        "trigger": trigger,
        "rationale_event_id": rationale_event_id,
        "report_id": report_id,
        "net_worth": str(getattr(snap, "net_worth", Decimal("0"))),
        "total_assets": str(total_assets),
        "total_liabilities": str(total_liabs),
        "total_unrealised_gain": str(getattr(snap, "total_unrealised_gain", Decimal("0"))),
        "allocation_pct": _decimal_to_str(rollup),
        "snapshot_json": snap.model_dump(mode="json"),
        "has_stale_values": bool(getattr(snap, "has_stale_values", False)),
        "stale_sources": list(getattr(snap, "stale_sources", []) or []),
    }
    return await wealth_snapshots_db.insert(row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_snapshot_service.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/snapshot_service.py backend/tests/test_snapshot_service.py
git commit -m "feat(services): add snapshot_service.persist_snapshot"
```

---

## Task 11: drift_service.compute_drift

**Files:**
- Create: `backend/services/drift_service.py`
- Create: `backend/tests/test_drift_service.py`

Returns per-class actual / target / band / in_band / breach_direction. Tolerates missing target (returns `None`).

- [ ] **Step 1: Write the failing test**

Write `backend/tests/test_drift_service.py`:

```python
"""Tests for backend.services.drift_service.compute_drift."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.services import drift_service


def _target(**overrides):
    base = {
        "equity_pct": "45", "debt_pct": "35", "gold_pct": "8",
        "cash_pct": "10", "alternatives_pct": "2",
        "equity_band_pct": "5", "debt_band_pct": "5",
        "gold_band_pct": "2", "cash_band_pct": "3", "alternatives_band_pct": "3",
    }
    base.update(overrides)
    return base


def _snap(allocation):
    return {"allocation_pct": allocation}


@pytest.mark.asyncio
async def test_returns_none_when_no_target():
    with patch.object(drift_service.allocation_targets_db, "get_current",
                      new=AsyncMock(return_value=None)):
        assert await drift_service.compute_drift("c1") is None


@pytest.mark.asyncio
async def test_in_band_when_close_to_target():
    actual = {"equity": "0.46", "debt": "0.34", "gold": "0.08",
              "cash": "0.10", "alternatives": "0.02"}
    with patch.object(drift_service.allocation_targets_db, "get_current",
                      new=AsyncMock(return_value=_target())), \
         patch.object(drift_service.wealth_snapshots_db, "get_latest",
                      new=AsyncMock(return_value=_snap(actual))):
        out = await drift_service.compute_drift("c1")
    assert out["equity"]["in_band"] is True
    assert out["equity"]["breach_direction"] is None


@pytest.mark.asyncio
async def test_over_breach_flagged():
    actual = {"equity": "0.55", "debt": "0.25", "gold": "0.08",
              "cash": "0.10", "alternatives": "0.02"}
    with patch.object(drift_service.allocation_targets_db, "get_current",
                      new=AsyncMock(return_value=_target())), \
         patch.object(drift_service.wealth_snapshots_db, "get_latest",
                      new=AsyncMock(return_value=_snap(actual))):
        out = await drift_service.compute_drift("c1")
    assert out["equity"]["in_band"] is False
    assert out["equity"]["breach_direction"] == "over"
    assert out["debt"]["breach_direction"] == "under"


@pytest.mark.asyncio
async def test_target_zero_and_actual_zero_is_in_band():
    actual = {"equity": "0.45", "debt": "0.35", "gold": "0.08",
              "cash": "0.12", "alternatives": "0"}
    with patch.object(drift_service.allocation_targets_db, "get_current",
                      new=AsyncMock(return_value=_target(alternatives_pct="0",
                                                        cash_pct="12"))), \
         patch.object(drift_service.wealth_snapshots_db, "get_latest",
                      new=AsyncMock(return_value=_snap(actual))):
        out = await drift_service.compute_drift("c1")
    assert out["alternatives"]["in_band"] is True


@pytest.mark.asyncio
async def test_exactly_at_band_edge_is_in_band():
    # target 45, band 5 → 40..50 inclusive; actual 50 is in band
    actual = {"equity": "0.50", "debt": "0.30", "gold": "0.08",
              "cash": "0.10", "alternatives": "0.02"}
    with patch.object(drift_service.allocation_targets_db, "get_current",
                      new=AsyncMock(return_value=_target())), \
         patch.object(drift_service.wealth_snapshots_db, "get_latest",
                      new=AsyncMock(return_value=_snap(actual))):
        out = await drift_service.compute_drift("c1")
    assert out["equity"]["in_band"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_drift_service.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the service**

Write `backend/services/drift_service.py`:

```python
"""Drift computation: actual vs target with per-class tolerance bands."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.db import allocation_targets_db, wealth_snapshots_db

_CLASSES = ("equity", "debt", "gold", "cash", "alternatives")
_HUNDRED = Decimal("100")


def _d(x: Any) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


async def compute_drift(client_id: str) -> dict[str, dict[str, Any]] | None:
    """Return {class: {actual_pct, target_pct, band_pct, in_band, breach_direction}}.

    Snapshot `allocation_pct` is fractional (0..1) and is rescaled to percent here.
    Returns None when no active target exists for the client.
    """
    target = await allocation_targets_db.get_current(client_id)
    if target is None:
        return None

    snap = await wealth_snapshots_db.get_latest(client_id)
    actual_frac = (snap or {}).get("allocation_pct", {})

    out: dict[str, dict[str, Any]] = {}
    for cls in _CLASSES:
        target_pct = _d(target[f"{cls}_pct"])
        band_pct = _d(target[f"{cls}_band_pct"])
        actual_pct = _d(actual_frac.get(cls, "0")) * _HUNDRED

        diff = actual_pct - target_pct
        in_band = abs(diff) <= band_pct
        direction: str | None
        if in_band:
            direction = None
        else:
            direction = "over" if diff > 0 else "under"

        out[cls] = {
            "actual_pct": actual_pct,
            "target_pct": target_pct,
            "band_pct": band_pct,
            "in_band": in_band,
            "breach_direction": direction,
        }
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_drift_service.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/drift_service.py backend/tests/test_drift_service.py
git commit -m "feat(services): add drift_service.compute_drift"
```

---

**Continue with Tasks 12–15 in:** `docs/superpowers/plans/2026-05-27-phase2-change-tracking-part3.md`
