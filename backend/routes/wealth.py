"""Wealth tracking routes: snapshots, allocation targets, drift.

GET  /clients/{id}/snapshots/latest       — latest snapshot
GET  /clients/{id}/snapshots              — range of snapshots (?from=&to=)
GET  /clients/{id}/allocation-target      — current active target
GET  /clients/{id}/allocation-target/history
PUT  /clients/{id}/allocation-target      — change target (creates event + snapshot)
GET  /clients/{id}/drift                  — actual vs target per class
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator

from db.allocation_targets_db import (
    change_allocation_target,
    get_active_target,
    get_target_history,
)
from db.rationale_events_db import insert_rationale_event
from db.supabase_client import get_supabase
from db.wealth_snapshots_db import get_latest_snapshot, get_snapshots_range
from services.drift_service import compute_drift
from services.snapshot_service import persist_snapshot

logger = logging.getLogger(__name__)
router = APIRouter()

_CLASSES = ("equity", "debt", "gold", "cash", "alternatives")


def _current_rm_id(request: Request = None) -> UUID:
    """Extract RM UUID from Authorization header (demo: returns a fixed UUID when missing)."""
    _DEMO_RM = UUID("00000000-0000-0000-0000-000000000001")
    if request is None:
        return _DEMO_RM
    auth = request.headers.get("Authorization", "")
    # In production this would decode the JWT; demo returns fixed UUID
    return _DEMO_RM


class AllocationTargetBody(BaseModel):
    risk_profile: Literal["Conservative", "Moderate", "Aggressive"]
    target_pct: dict[str, Decimal]
    band_pct: dict[str, Decimal]
    rationale_text: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def _validate(self):
        for d, name in ((self.target_pct, "target_pct"), (self.band_pct, "band_pct")):
            if set(d.keys()) != set(_CLASSES):
                raise ValueError(f"{name} must have exactly these keys: {set(_CLASSES)}")
        total = sum(self.target_pct.values())
        if total != Decimal("100"):
            raise ValueError(f"target_pct must sum to 100, got {total}")
        return self


@router.get("/clients/{client_id}/snapshots/latest")
def get_latest(client_id: UUID, request: Request) -> dict[str, Any]:
    rm_id = _current_rm_id(request)
    sb = get_supabase()
    row = get_latest_snapshot(sb, str(client_id))
    if row is None:
        raise HTTPException(status_code=404, detail="no snapshot found")
    return row


@router.get("/clients/{client_id}/snapshots")
def get_range(
    client_id: UUID,
    request: Request,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
) -> list[dict[str, Any]]:
    rm_id = _current_rm_id(request)
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to must be >= from")
    sb = get_supabase()
    return get_snapshots_range(sb, str(client_id), from_date, to_date)


@router.get("/clients/{client_id}/allocation-target/history")
def get_history(client_id: UUID, request: Request) -> list[dict[str, Any]]:
    rm_id = _current_rm_id(request)
    sb = get_supabase()
    return get_target_history(sb, str(client_id))


@router.get("/clients/{client_id}/allocation-target")
def get_target(client_id: UUID, request: Request) -> dict[str, Any]:
    rm_id = _current_rm_id(request)
    sb = get_supabase()
    row = get_active_target(sb, str(client_id))
    if row is None:
        raise HTTPException(status_code=404, detail="no active allocation target")
    return row


@router.put("/clients/{client_id}/allocation-target")
def put_target(
    client_id: UUID,
    body: AllocationTargetBody,
    request: Request,
) -> dict[str, Any]:
    """Spec §6.3 — atomic target change.

    Order: insert event → change target via RPC → persist snapshot.
    Snapshot failures are logged but do NOT abort the target change.
    """
    rm_id = _current_rm_id(request)
    sb = get_supabase()

    event_row = insert_rationale_event(
        sb,
        client_id=str(client_id),
        event_type="target_change",
        event_date=date.today(),
        title=f"Target → {body.risk_profile}",
        body=body.rationale_text,
        author_rm_id=str(rm_id),
    )
    event_id = UUID(event_row["id"])

    target_row = change_allocation_target(
        sb,
        client_id=str(client_id),
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
            client_id=str(client_id),
            trigger="rationale",
            rationale_event_id=str(event_id),
        )
        snapshot_id = UUID(snap_row["id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "snapshot after target change failed for client %s: %s",
            client_id, exc,
        )

    return {
        "event_id": str(event_id),
        "target_id": str(target_id),
        "snapshot_id": str(snapshot_id) if snapshot_id else None,
    }


@router.get("/clients/{client_id}/drift")
def get_drift(client_id: UUID, request: Request) -> list[dict[str, Any]]:
    rm_id = _current_rm_id(request)
    sb = get_supabase()
    target = get_active_target(sb, str(client_id))
    if target is None:
        raise HTTPException(status_code=404, detail="no active allocation target")
    snap = get_latest_snapshot(sb, str(client_id))
    if snap is None:
        raise HTTPException(status_code=404, detail="no snapshot")
    result = compute_drift(
        sb,
        str(client_id),
        target_pct={cls: str(target.get(f"{cls}_pct", 0)) for cls in _CLASSES},
        band_pct={cls: str(target.get(f"{cls}_band_pct", 5)) for cls in _CLASSES},
        actual_pct=snap.get("allocation_pct", {}),
    )
    return result or []
