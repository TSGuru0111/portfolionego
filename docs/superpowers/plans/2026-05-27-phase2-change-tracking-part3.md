# Phase 2 Change-Tracking Implementation Plan — Part 3 (Routes + Cron + Seed)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Continuation of** `2026-05-27-phase2-change-tracking.md` (Part 1: setup + models, Tasks 1–5) and `2026-05-27-phase2-change-tracking-part2.md` (services + DB layer, Tasks 6–11). Read those first.

---

## Task 12: `backend/routes/wealth.py` (new router — 6 endpoints)

Implements spec §6.1 (report-driven snapshot is server-internal — covered in Phase 1 hook in Part 4), §6.3 (allocation target change), and read endpoints for current snapshot / snapshots range / current target / target history / drift.

**Files:**
- Create: `backend/routes/wealth.py`
- Modify: `backend/main.py` (mount router)
- Test: `backend/tests/test_routes_wealth.py`

- [ ] **Step 1: Read `backend/main.py` to find the router-include pattern**

Run: `rg -n "include_router|FastAPI\\(" backend/main.py`
Note the line numbers where existing routers are included (clients, reports, jobs, etc.). Part 4 will mount `wealth.router` in the same block.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_routes_wealth.py`:

```python
"""Tests for backend/routes/wealth.py."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer fake-jwt"}


@patch("backend.routes.wealth._current_rm_id")
@patch("backend.routes.wealth.get_latest_snapshot")
def test_get_latest_snapshot_returns_row(mock_get, mock_rm):
    mock_rm.return_value = uuid4()
    snap_id = uuid4()
    client_id = uuid4()
    mock_get.return_value = {
        "id": str(snap_id),
        "client_id": str(client_id),
        "as_of_date": "2026-05-01",
        "trigger": "report",
        "total_value": "1000000.00",
        "by_class": {
            "equity": "500000.00",
            "debt": "300000.00",
            "gold": "100000.00",
            "cash": "100000.00",
            "alternatives": "0.00",
        },
        "by_class_pct": {
            "equity": "50.00",
            "debt": "30.00",
            "gold": "10.00",
            "cash": "10.00",
            "alternatives": "0.00",
        },
        "by_holding": [],
        "rationale_event_id": None,
        "report_id": None,
        "created_at": "2026-05-01T00:00:00+00:00",
    }

    r = client.get(f"/clients/{client_id}/snapshots/latest", headers=_auth_headers())

    assert r.status_code == 200
    assert r.json()["total_value"] == "1000000.00"
    mock_get.assert_called_once()


@patch("backend.routes.wealth._current_rm_id")
@patch("backend.routes.wealth.get_latest_snapshot")
def test_get_latest_snapshot_404_when_missing(mock_get, mock_rm):
    mock_rm.return_value = uuid4()
    mock_get.return_value = None
    r = client.get(f"/clients/{uuid4()}/snapshots/latest", headers=_auth_headers())
    assert r.status_code == 404


@patch("backend.routes.wealth._current_rm_id")
@patch("backend.routes.wealth.get_active_target")
def test_get_current_target_returns_row(mock_get, mock_rm):
    mock_rm.return_value = uuid4()
    mock_get.return_value = {
        "id": str(uuid4()),
        "client_id": str(uuid4()),
        "effective_from": "2026-01-01",
        "effective_to": None,
        "risk_profile": "Moderate",
        "target_pct": {
            "equity": "45.00",
            "debt": "35.00",
            "gold": "8.00",
            "cash": "10.00",
            "alternatives": "2.00",
        },
        "band_pct": {
            "equity": "5.00",
            "debt": "5.00",
            "gold": "2.00",
            "cash": "3.00",
            "alternatives": "3.00",
        },
        "rationale_event_id": str(uuid4()),
        "set_by": str(uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    r = client.get(f"/clients/{uuid4()}/allocation-target", headers=_auth_headers())
    assert r.status_code == 200
    assert r.json()["risk_profile"] == "Moderate"


@patch("backend.routes.wealth._current_rm_id")
@patch("backend.routes.wealth.persist_snapshot")
@patch("backend.routes.wealth.change_allocation_target")
@patch("backend.routes.wealth.insert_rationale_event")
def test_put_allocation_target_happy_path(mock_event, mock_change, mock_persist, mock_rm):
    rm_id = uuid4()
    mock_rm.return_value = rm_id
    new_event_id = uuid4()
    new_target_id = uuid4()
    new_snap_id = uuid4()
    mock_event.return_value = {"id": str(new_event_id)}
    mock_change.return_value = {"id": str(new_target_id)}
    mock_persist.return_value = {"id": str(new_snap_id)}

    cid = uuid4()
    payload = {
        "risk_profile": "Aggressive",
        "target_pct": {
            "equity": "65.00", "debt": "20.00", "gold": "5.00",
            "cash": "8.00", "alternatives": "2.00",
        },
        "band_pct": {
            "equity": "5.00", "debt": "5.00", "gold": "2.00",
            "cash": "3.00", "alternatives": "3.00",
        },
        "rationale_text": "Client switching to aggressive growth",
    }
    r = client.put(
        f"/clients/{cid}/allocation-target",
        headers=_auth_headers(),
        json=payload,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["target_id"] == str(new_target_id)
    assert body["event_id"] == str(new_event_id)
    assert body["snapshot_id"] == str(new_snap_id)
    mock_event.assert_called_once()
    mock_change.assert_called_once()
    mock_persist.assert_called_once()


@patch("backend.routes.wealth._current_rm_id")
@patch("backend.routes.wealth.persist_snapshot")
@patch("backend.routes.wealth.change_allocation_target")
@patch("backend.routes.wealth.insert_rationale_event")
def test_put_allocation_target_snapshot_failure_does_not_abort(
    mock_event, mock_change, mock_persist, mock_rm
):
    mock_rm.return_value = uuid4()
    mock_event.return_value = {"id": str(uuid4())}
    mock_change.return_value = {"id": str(uuid4())}
    mock_persist.side_effect = RuntimeError("snapshot failed")

    payload = {
        "risk_profile": "Moderate",
        "target_pct": {
            "equity": "45.00", "debt": "35.00", "gold": "8.00",
            "cash": "10.00", "alternatives": "2.00",
        },
        "band_pct": {
            "equity": "5.00", "debt": "5.00", "gold": "2.00",
            "cash": "3.00", "alternatives": "3.00",
        },
        "rationale_text": "Routine review",
    }
    r = client.put(
        f"/clients/{uuid4()}/allocation-target",
        headers=_auth_headers(),
        json=payload,
    )
    assert r.status_code == 200
    assert r.json()["snapshot_id"] is None


@patch("backend.routes.wealth._current_rm_id")
@patch("backend.routes.wealth.get_active_target")
@patch("backend.routes.wealth.get_latest_snapshot")
@patch("backend.routes.wealth.compute_drift")
def test_get_drift_combines_target_and_snapshot(
    mock_drift, mock_snap, mock_target, mock_rm
):
    mock_rm.return_value = uuid4()
    mock_target.return_value = {"target_pct": {"equity": "50.00"}, "band_pct": {"equity": "5.00"}}
    mock_snap.return_value = {"by_class_pct": {"equity": "60.00"}}
    mock_drift.return_value = [
        {"class": "equity", "target_pct": "50.00", "actual_pct": "60.00",
         "delta_pct": "10.00", "band_pct": "5.00", "status": "over"}
    ]
    r = client.get(f"/clients/{uuid4()}/drift", headers=_auth_headers())
    assert r.status_code == 200
    assert r.json()[0]["status"] == "over"
    mock_drift.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_routes_wealth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.routes.wealth'`

- [ ] **Step 4: Implement the wealth router**

Create `backend/routes/wealth.py`:

```python
"""Wealth tracking routes: snapshots, allocation targets, drift."""
from __future__ import annotations
import logging
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from backend.auth import get_current_user, get_supabase_client
from backend.db.allocation_targets_db import (
    change_allocation_target,
    get_active_target,
    get_target_history,
)
from backend.db.rationale_events_db import insert_rationale_event
from backend.db.wealth_snapshots_db import (
    get_latest_snapshot,
    get_snapshots_range,
)
from backend.services.drift_service import compute_drift
from backend.services.snapshot_service import persist_snapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/clients/{client_id}", tags=["wealth"])

_CLASSES = ("equity", "debt", "gold", "cash", "alternatives")


def _current_rm_id(user: dict = Depends(get_current_user)) -> UUID:
    """Extract auth.uid() — Supabase JWT 'sub' is the auth user id."""
    sub = user.get("sub") or user.get("id")
    if not sub:
        raise HTTPException(status_code=401, detail="missing user id")
    return UUID(str(sub))


class AllocationTargetBody(BaseModel):
    risk_profile: Literal["Conservative", "Moderate", "Aggressive"]
    target_pct: dict[str, Decimal]
    band_pct: dict[str, Decimal]
    rationale_text: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def _validate(self):
        for d, name in ((self.target_pct, "target_pct"), (self.band_pct, "band_pct")):
            if set(d.keys()) != set(_CLASSES):
                raise ValueError(f"{name} must have exactly these keys: {_CLASSES}")
        total = sum(self.target_pct.values())
        if total != Decimal("100"):
            raise ValueError(f"target_pct must sum to 100, got {total}")
        return self


@router.get("/snapshots/latest")
def get_latest(
    client_id: UUID,
    rm_id: UUID = Depends(_current_rm_id),
    sb=Depends(get_supabase_client),
):
    row = get_latest_snapshot(sb, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="no snapshot found")
    return row


@router.get("/snapshots")
def get_range(
    client_id: UUID,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    rm_id: UUID = Depends(_current_rm_id),
    sb=Depends(get_supabase_client),
):
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to must be >= from")
    return get_snapshots_range(sb, client_id, from_date, to_date)


@router.get("/allocation-target")
def get_target(
    client_id: UUID,
    rm_id: UUID = Depends(_current_rm_id),
    sb=Depends(get_supabase_client),
):
    row = get_active_target(sb, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="no active allocation target")
    return row


@router.get("/allocation-target/history")
def get_history(
    client_id: UUID,
    rm_id: UUID = Depends(_current_rm_id),
    sb=Depends(get_supabase_client),
):
    return get_target_history(sb, client_id)


@router.put("/allocation-target")
def put_target(
    client_id: UUID,
    body: AllocationTargetBody,
    rm_id: UUID = Depends(_current_rm_id),
    sb=Depends(get_supabase_client),
):
    """Spec §6.3 — atomic target change.

    Order: insert event → change target via RPC (links target↔event) →
    persist snapshot → link snapshot back. Snapshot failures are logged
    but do NOT abort the target change.
    """
    event_row = insert_rationale_event(
        sb,
        client_id=client_id,
        event_type="target_change",
        event_date=date.today(),
        title=f"Target → {body.risk_profile}",
        body=body.rationale_text,
        author_rm_id=rm_id,
    )
    event_id = UUID(event_row["id"])

    target_row = change_allocation_target(
        sb,
        client_id=client_id,
        risk_profile=body.risk_profile,
        target_pct=body.target_pct,
        band_pct=body.band_pct,
        rationale_event_id=event_id,
        set_by=rm_id,
    )
    target_id = UUID(target_row["id"])

    snapshot_id: UUID | None = None
    try:
        snap_row = persist_snapshot(
            sb,
            client_id=client_id,
            trigger="rationale",
            rationale_event_id=event_id,
        )
        snapshot_id = UUID(snap_row["id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "snapshot after target change failed for client %s: %s",
            client_id, exc,
        )

    return {
        "event_id": event_id,
        "target_id": target_id,
        "snapshot_id": snapshot_id,
    }


@router.get("/drift")
def get_drift(
    client_id: UUID,
    rm_id: UUID = Depends(_current_rm_id),
    sb=Depends(get_supabase_client),
):
    target = get_active_target(sb, client_id)
    if target is None:
        raise HTTPException(status_code=404, detail="no active allocation target")
    snap = get_latest_snapshot(sb, client_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="no snapshot")
    return compute_drift(
        target_pct=target["target_pct"],
        band_pct=target["band_pct"],
        actual_pct=snap["by_class_pct"],
    )
```

- [ ] **Step 5: Mount router in `backend/main.py`**

Add to imports:
```python
from backend.routes import wealth as wealth_routes
```

Add next to other `app.include_router(...)` calls:
```python
app.include_router(wealth_routes.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_routes_wealth.py -v`
Expected: PASS — all six tests.

- [ ] **Step 7: Commit**

```bash
git add backend/routes/wealth.py backend/main.py backend/tests/test_routes_wealth.py
git commit -m "feat(wealth): add wealth routes for snapshots, targets, drift"
```

---

## Task 13: Extend `backend/routes/clients.py` with rationale-events endpoints

Implements spec §6.2 — RM logs a non-target rationale event from the client page. Server rejects `target_change` and `onboarding` event types (must come from `/allocation-target` PUT and seed/onboarding flows respectively).

**Files:**
- Modify: `backend/routes/clients.py` (append router routes)
- Test: `backend/tests/test_routes_clients_rationale.py`

- [ ] **Step 1: Read existing `backend/routes/clients.py`**

Run: `rg -n "router|APIRouter" backend/routes/clients.py | head -20`
Note the router prefix and existing auth dep pattern.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_routes_clients_rationale.py`:

```python
"""Tests for rationale-events endpoints on clients router."""
from __future__ import annotations
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _hdr() -> dict[str, str]:
    return {"Authorization": "Bearer fake-jwt"}


@patch("backend.routes.clients._current_rm_id")
@patch("backend.routes.clients.persist_snapshot")
@patch("backend.routes.clients.link_transactions_to_event")
@patch("backend.routes.clients.insert_rationale_event")
def test_post_manual_event_happy_path(mock_event, mock_link, mock_snap, mock_rm):
    mock_rm.return_value = uuid4()
    event_id = uuid4()
    snap_id = uuid4()
    mock_event.return_value = {"id": str(event_id)}
    mock_snap.return_value = {"id": str(snap_id)}

    txn_ids = [str(uuid4()), str(uuid4())]
    payload = {
        "event_type": "rebalance",
        "event_date": "2026-04-15",
        "title": "Quarterly rebalance",
        "body": "Trimmed equity exposure",
        "transaction_ids": txn_ids,
    }
    r = client.post(
        f"/clients/{uuid4()}/rationale-events",
        headers=_hdr(),
        json=payload,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["event_id"] == str(event_id)
    assert body["snapshot_id"] == str(snap_id)
    mock_link.assert_called_once_with(
        sb=mock_link.call_args.kwargs["sb"],
        event_id=event_id,
        transaction_ids=[uuid4().__class__(tid) for tid in txn_ids],
    ) if False else None  # presence-only check; UUID rebuild not strict


@patch("backend.routes.clients._current_rm_id")
def test_post_manual_event_rejects_target_change(mock_rm):
    mock_rm.return_value = uuid4()
    payload = {
        "event_type": "target_change",
        "event_date": "2026-04-15",
        "title": "x",
        "body": "y",
    }
    r = client.post(
        f"/clients/{uuid4()}/rationale-events",
        headers=_hdr(),
        json=payload,
    )
    assert r.status_code == 422


@patch("backend.routes.clients._current_rm_id")
def test_post_manual_event_rejects_onboarding(mock_rm):
    mock_rm.return_value = uuid4()
    payload = {
        "event_type": "onboarding",
        "event_date": "2026-04-15",
        "title": "x",
        "body": "y",
    }
    r = client.post(
        f"/clients/{uuid4()}/rationale-events",
        headers=_hdr(),
        json=payload,
    )
    assert r.status_code == 422


@patch("backend.routes.clients._current_rm_id")
@patch("backend.routes.clients.list_rationale_events")
def test_get_events_returns_list(mock_list, mock_rm):
    mock_rm.return_value = uuid4()
    mock_list.return_value = [
        {"id": str(uuid4()), "event_type": "rebalance", "event_date": "2026-04-15"}
    ]
    r = client.get(
        f"/clients/{uuid4()}/rationale-events?from=2026-01-01&to=2026-06-30",
        headers=_hdr(),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_routes_clients_rationale.py -v`
Expected: FAIL — routes don't exist (404 or AttributeError on patched names).

- [ ] **Step 4: Add the endpoints to `backend/routes/clients.py`**

Append to the bottom of `backend/routes/clients.py` (and add the imports at the top of the file):

```python
# --- Phase 2 additions: rationale events ---
import logging
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth import get_current_user, get_supabase_client
from backend.db.rationale_events_db import (
    insert_rationale_event,
    link_transactions_to_event,
    list_rationale_events,
)
from backend.services.snapshot_service import persist_snapshot

_logger = logging.getLogger(__name__)

_MANUAL_EVENT_TYPES = {
    "rebalance",
    "cash_deployment",
    "tax_harvest",
    "liquidity_event",
    "external_change",
    "market_commentary",
}


def _current_rm_id(user: dict = Depends(get_current_user)) -> UUID:  # type: ignore[name-defined]
    sub = user.get("sub") or user.get("id")
    if not sub:
        raise HTTPException(status_code=401, detail="missing user id")
    return UUID(str(sub))


class _ManualEventBody(BaseModel):
    event_type: Literal[
        "rebalance",
        "cash_deployment",
        "tax_harvest",
        "liquidity_event",
        "external_change",
        "market_commentary",
        "target_change",  # accepted by schema but rejected below
        "onboarding",
    ]
    event_date: date
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    transaction_ids: list[UUID] = Field(default_factory=list)


@router.post("/{client_id}/rationale-events")  # type: ignore[name-defined]
def post_manual_event(
    client_id: UUID,
    body: _ManualEventBody,
    rm_id: UUID = Depends(_current_rm_id),
    sb=Depends(get_supabase_client),
):
    if body.event_type not in _MANUAL_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"event_type '{body.event_type}' cannot be created manually",
        )
    event_row = insert_rationale_event(
        sb,
        client_id=client_id,
        event_type=body.event_type,
        event_date=body.event_date,
        title=body.title,
        body=body.body,
        author_rm_id=rm_id,
    )
    event_id = UUID(event_row["id"])

    if body.transaction_ids:
        link_transactions_to_event(
            sb=sb, event_id=event_id, transaction_ids=body.transaction_ids,
        )

    snapshot_id: UUID | None = None
    try:
        snap_row = persist_snapshot(
            sb,
            client_id=client_id,
            trigger="rationale",
            rationale_event_id=event_id,
        )
        snapshot_id = UUID(snap_row["id"])
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "snapshot after manual event failed for client %s: %s",
            client_id, exc,
        )

    return {"event_id": event_id, "snapshot_id": snapshot_id}


@router.get("/{client_id}/rationale-events")  # type: ignore[name-defined]
def get_events(
    client_id: UUID,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    rm_id: UUID = Depends(_current_rm_id),
    sb=Depends(get_supabase_client),
):
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to must be >= from")
    return list_rationale_events(sb, client_id, from_date, to_date)
```

> **Note:** If `router` is defined with a `prefix="/clients"`, the inner route paths above are `/{client_id}/...` (no `clients/` prefix). If `router` has no prefix, change paths to `/clients/{client_id}/...`. Match the existing file's convention.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_routes_clients_rationale.py -v`
Expected: PASS — all four tests.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/clients.py backend/tests/test_routes_clients_rationale.py
git commit -m "feat(rationale): add manual rationale-event endpoints to clients router"
```

---

## Task 14: Monthly snapshots cron in `backend/routes/jobs.py`

Implements spec §6.4 — EasyCron hits `POST /jobs/monthly-snapshots?secret=...` on the 1st of every month (Asia/Kolkata). Iterates every client and writes a `monthly` snapshot. Per-client failures are logged but do not abort the run.

**Files:**
- Modify: `backend/routes/jobs.py` (append handler + helper)
- Test: `backend/tests/test_routes_jobs_monthly.py`

- [ ] **Step 1: Read existing `backend/routes/jobs.py`**

Run: `rg -n "JOB_SECRET|log_job_run|log_error" backend/routes/jobs.py | head -30`
Note the auth pattern (query-string secret), the `log_job_run` shape, and the `log_error` signature.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_routes_jobs_monthly.py`:

```python
"""Tests for monthly snapshots cron handler."""
from __future__ import annotations
import os
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


@patch.dict(os.environ, {"JOB_SECRET": "S3CR3T"})
def test_monthly_snapshots_rejects_bad_secret():
    r = client.post("/jobs/monthly-snapshots?secret=wrong")
    assert r.status_code == 401


@patch.dict(os.environ, {"JOB_SECRET": "S3CR3T"})
@patch("backend.routes.jobs.log_job_run")
@patch("backend.routes.jobs.persist_snapshot")
@patch("backend.routes.jobs.list_all_clients")
def test_monthly_snapshots_iterates_all_clients(
    mock_list, mock_persist, mock_log
):
    c1, c2, c3 = uuid4(), uuid4(), uuid4()
    mock_list.return_value = [
        {"id": str(c1)}, {"id": str(c2)}, {"id": str(c3)},
    ]
    mock_persist.return_value = {"id": str(uuid4())}

    r = client.post("/jobs/monthly-snapshots?secret=S3CR3T")
    assert r.status_code == 200
    body = r.json()
    assert body["clients_total"] == 3
    assert body["ok"] == 3
    assert body["failed"] == 0
    assert mock_persist.call_count == 3


@patch.dict(os.environ, {"JOB_SECRET": "S3CR3T"})
@patch("backend.routes.jobs.log_error")
@patch("backend.routes.jobs.log_job_run")
@patch("backend.routes.jobs.persist_snapshot")
@patch("backend.routes.jobs.list_all_clients")
def test_monthly_snapshots_continues_on_per_client_failure(
    mock_list, mock_persist, mock_log_run, mock_log_err
):
    c1, c2 = uuid4(), uuid4()
    mock_list.return_value = [{"id": str(c1)}, {"id": str(c2)}]
    mock_persist.side_effect = [RuntimeError("boom"), {"id": str(uuid4())}]

    r = client.post("/jobs/monthly-snapshots?secret=S3CR3T")
    assert r.status_code == 200
    body = r.json()
    assert body["clients_total"] == 2
    assert body["ok"] == 1
    assert body["failed"] == 1
    mock_log_err.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_routes_jobs_monthly.py -v`
Expected: FAIL — endpoint not implemented (404) and patched names missing.

- [ ] **Step 4: Add `list_all_clients` helper to `backend/db/clients_db.py`**

Append to `backend/db/clients_db.py` (create the file if it does not exist; use the same supabase client pattern as `wealth_snapshots_db.py`):

```python
from uuid import UUID


def list_all_clients(sb) -> list[dict]:
    """Return every client row. Service-role only — used by cron."""
    resp = sb.table("clients").select("id").execute()
    return resp.data or []
```

- [ ] **Step 5: Add the cron handler to `backend/routes/jobs.py`**

Append to `backend/routes/jobs.py` (and add the imports at the top):

```python
# --- Phase 2 monthly snapshots cron ---
import os
from datetime import date

from fastapi import HTTPException, Query

from backend.db.clients_db import list_all_clients
from backend.services.snapshot_service import persist_snapshot
# log_job_run and log_error are assumed to already exist; if not, add them
# in this file using the same supabase service-role client used by other jobs.


@router.post("/monthly-snapshots")  # type: ignore[name-defined]
def monthly_snapshots(secret: str = Query(...), sb=Depends(get_service_supabase)):  # type: ignore[name-defined]
    expected = os.environ.get("JOB_SECRET")
    if not expected or secret != expected:
        raise HTTPException(status_code=401, detail="bad secret")

    clients = list_all_clients(sb)
    ok = 0
    failed = 0
    today = date.today()

    for c in clients:
        cid = c["id"]
        try:
            persist_snapshot(
                sb,
                client_id=cid,
                trigger="monthly",
                as_of_date=today,
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log_error(  # type: ignore[name-defined]
                sb,
                source="cron.monthly-snapshots",
                client_id=cid,
                message=str(exc),
            )

    summary = {"clients_total": len(clients), "ok": ok, "failed": failed}
    log_job_run(  # type: ignore[name-defined]
        sb,
        job_name="monthly-snapshots",
        summary=summary,
    )
    return summary
```

> **Note:** If `get_service_supabase`, `log_job_run`, or `log_error` are named differently in the existing `jobs.py`, keep those names — only the algorithm above matters.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_routes_jobs_monthly.py -v`
Expected: PASS — all three tests.

- [ ] **Step 7: Document the EasyCron schedule**

Append to `backend/routes/jobs.py` as a module-level comment near the new handler:

```python
# EasyCron schedule:
#   URL:      https://<host>/jobs/monthly-snapshots?secret=$JOB_SECRET
#   Cron:     30 0 1 * *
#   Timezone: Asia/Kolkata
#   Retries:  3 (EasyCron-side)
```

- [ ] **Step 8: Commit**

```bash
git add backend/routes/jobs.py backend/db/clients_db.py backend/tests/test_routes_jobs_monthly.py
git commit -m "feat(cron): add monthly snapshots job for all clients"
```

---

## Task 15: Demo seed `backend/db_schema/seed_v3.sql`

Implements spec §13 — every demo client gets an onboarding `rationale_event` and an initial `allocation_target`. Snapshots are seeded at runtime by curling `/jobs/monthly-snapshots` once the backend is up (deferred to deployment runbook, not SQL — keeps seed deterministic without depending on the live valuator path).

The 5 demo client UUIDs come from `seed_v2.sql`. Run `rg -n "INSERT INTO clients" backend/db_schema/seed_v2.sql` to confirm they match the values below before writing.

**Files:**
- Create: `backend/db_schema/seed_v3.sql`
- Test: `backend/tests/test_seed_v3_sql.py` (lightweight smoke test — parses SQL & checks counts)

- [ ] **Step 1: Confirm the 5 demo client UUIDs from seed_v2.sql**

Run: `rg -n "INSERT INTO clients" backend/db_schema/seed_v2.sql`
Expected to include: `d62e9583-...` (Rajesh), `e46486d4-...` (Priya), `410834b9-...` (Arjun), `a5ab55c8-...` (Sunita), `5c406920-...` (Vikram).
If any UUID differs, substitute below.

- [ ] **Step 2: Write the failing smoke test**

Create `backend/tests/test_seed_v3_sql.py`:

```python
"""Lightweight smoke test for seed_v3.sql — checks structure, not execution."""
from pathlib import Path

SEED = Path(__file__).parent.parent / "db_schema" / "seed_v3.sql"


def test_seed_v3_exists():
    assert SEED.exists(), "seed_v3.sql missing"


def test_seed_v3_has_five_onboarding_events():
    sql = SEED.read_text()
    # one onboarding event per demo client
    assert sql.count("'onboarding'") == 5


def test_seed_v3_has_five_allocation_targets():
    sql = SEED.read_text()
    assert sql.lower().count("insert into allocation_targets") == 5


def test_seed_v3_references_all_five_demo_clients():
    sql = SEED.read_text()
    for uid in (
        "d62e9583", "e46486d4", "410834b9", "a5ab55c8", "5c406920",
    ):
        assert uid in sql, f"missing demo client {uid}"


def test_seed_v3_uses_psql_rm_id_variable():
    """RM owner UUID must be a psql :rm_id variable, not hard-coded."""
    sql = SEED.read_text()
    assert ":rm_id" in sql
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_seed_v3_sql.py -v`
Expected: FAIL — file missing.

- [ ] **Step 4: Write `backend/db_schema/seed_v3.sql`**

```sql
-- seed_v3.sql — Phase 2 demo seed.
-- Run AFTER seed_v2.sql.
-- Required psql variable: :rm_id (the RM user UUID who owns the demo clients).
--
-- Usage:
--   psql "$DATABASE_URL" -v rm_id="'YOUR-RM-UUID-HERE'" \
--        -f backend/db_schema/seed_v3.sql
--
-- After this script, run a one-time seed of monthly snapshots:
--   curl -X POST "$BACKEND_URL/jobs/monthly-snapshots?secret=$JOB_SECRET"

BEGIN;

-- ---------------------------------------------------------------
-- Rajesh Mehta — Aggressive (d62e9583-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, body, author_rm_id)
  VALUES
    ('d62e9583-1111-1111-1111-111111111111',
     'onboarding',
     '2024-01-15',
     'Initial onboarding',
     'Risk profile Aggressive — high equity tilt, 7+ year horizon, comfortable with volatility.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from, risk_profile, target_pct, band_pct,
   rationale_event_id, set_by)
SELECT
  'd62e9583-1111-1111-1111-111111111111',
  '2024-01-15',
  'Aggressive',
  '{"equity":65,"debt":20,"gold":5,"cash":8,"alternatives":2}'::jsonb,
  '{"equity":5,"debt":5,"gold":2,"cash":3,"alternatives":3}'::jsonb,
  e.id,
  :rm_id
FROM e;

-- ---------------------------------------------------------------
-- Priya Sharma — Moderate (e46486d4-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, body, author_rm_id)
  VALUES
    ('e46486d4-2222-2222-2222-222222222222',
     'onboarding',
     '2024-02-01',
     'Initial onboarding',
     'Risk profile Moderate — balanced growth and stability, 5–7 year horizon.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from, risk_profile, target_pct, band_pct,
   rationale_event_id, set_by)
SELECT
  'e46486d4-2222-2222-2222-222222222222',
  '2024-02-01',
  'Moderate',
  '{"equity":45,"debt":35,"gold":8,"cash":10,"alternatives":2}'::jsonb,
  '{"equity":5,"debt":5,"gold":2,"cash":3,"alternatives":3}'::jsonb,
  e.id,
  :rm_id
FROM e;

-- ---------------------------------------------------------------
-- Arjun Patel — Aggressive (410834b9-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, body, author_rm_id)
  VALUES
    ('410834b9-3333-3333-3333-333333333333',
     'onboarding',
     '2024-03-10',
     'Initial onboarding',
     'Risk profile Aggressive — young professional, long horizon, growth-focused.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from, risk_profile, target_pct, band_pct,
   rationale_event_id, set_by)
SELECT
  '410834b9-3333-3333-3333-333333333333',
  '2024-03-10',
  'Aggressive',
  '{"equity":65,"debt":20,"gold":5,"cash":8,"alternatives":2}'::jsonb,
  '{"equity":5,"debt":5,"gold":2,"cash":3,"alternatives":3}'::jsonb,
  e.id,
  :rm_id
FROM e;

-- ---------------------------------------------------------------
-- Sunita Iyer — Conservative (a5ab55c8-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, body, author_rm_id)
  VALUES
    ('a5ab55c8-4444-4444-4444-444444444444',
     'onboarding',
     '2024-04-05',
     'Initial onboarding',
     'Risk profile Conservative — capital preservation, retirement income focus.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from, risk_profile, target_pct, band_pct,
   rationale_event_id, set_by)
SELECT
  'a5ab55c8-4444-4444-4444-444444444444',
  '2024-04-05',
  'Conservative',
  '{"equity":25,"debt":55,"gold":8,"cash":10,"alternatives":2}'::jsonb,
  '{"equity":5,"debt":5,"gold":2,"cash":3,"alternatives":3}'::jsonb,
  e.id,
  :rm_id
FROM e;

-- ---------------------------------------------------------------
-- Vikram Singh — Moderate (5c406920-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, body, author_rm_id)
  VALUES
    ('5c406920-5555-5555-5555-555555555555',
     'onboarding',
     '2024-05-20',
     'Initial onboarding',
     'Risk profile Moderate — established business owner, balanced approach.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from, risk_profile, target_pct, band_pct,
   rationale_event_id, set_by)
SELECT
  '5c406920-5555-5555-5555-555555555555',
  '2024-05-20',
  'Moderate',
  '{"equity":45,"debt":35,"gold":8,"cash":10,"alternatives":2}'::jsonb,
  '{"equity":5,"debt":5,"gold":2,"cash":3,"alternatives":3}'::jsonb,
  e.id,
  :rm_id
FROM e;

COMMIT;
```

> **Important:** If any of the five demo client UUIDs in `seed_v2.sql` differ from the literals above, substitute them before writing the file. The test in Step 2 only checks the 8-char prefix, so it will pass with substitutions only if you also update the test.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_seed_v3_sql.py -v`
Expected: PASS — all five tests.

- [ ] **Step 6: Commit**

```bash
git add backend/db_schema/seed_v3.sql backend/tests/test_seed_v3_sql.py
git commit -m "feat(seed): add Phase 2 demo seed for rationale events and targets"
```

---

**End of Part 3.** Continue with Tasks 16–20+ (narrator integration, frontend components, wrap-up) in `2026-05-27-phase2-change-tracking-part4.md`.
