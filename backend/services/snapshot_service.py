"""Snapshot orchestrator: aggregate -> rollup -> persist."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from db.wealth_snapshots_db import insert_snapshot
from services.allocation_rollup import roll_up_to_classes
from services.wealth_aggregator import build_wealth_snapshot

_VALID_TRIGGERS = {"report", "rationale", "monthly"}


def _decimal_to_str(d: dict[str, Decimal]) -> dict[str, str]:
    return {k: str(v) for k, v in d.items()}


def persist_snapshot(
    sb,
    *,
    client_id,
    trigger: str,
    report_id=None,
    rationale_event_id=None,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """Build a wealth snapshot, persist it, return row dict with id."""
    if trigger not in _VALID_TRIGGERS:
        raise ValueError(f"Invalid trigger: {trigger}")

    snap = build_wealth_snapshot(str(client_id), as_of_date)
    rollup = roll_up_to_classes(snap)

    total_assets = Decimal("0")
    for b in ("mutual_funds", "bonds", "gold", "cash", "fixed_deposits", "insurance"):
        bucket = getattr(snap, b, None)
        if bucket is not None:
            val = getattr(bucket, "current_value", None)
            if val is None:
                val = getattr(bucket, "total_current_value", None)
            if val is None:
                val = 0
            try:
                total_assets += Decimal(str(val))
            except Exception:
                pass

    liabilities_bucket = getattr(snap, "liabilities", None)
    total_liabs = Decimal("0")
    if liabilities_bucket is not None:
        total_liabs = Decimal(str(getattr(liabilities_bucket, "total_outstanding", 0)))

    now = datetime.now(timezone.utc)
    row: dict[str, Any] = {
        "client_id": str(client_id),
        "as_of": now.isoformat(),
        "trigger": trigger,
        "rationale_event_id": str(rationale_event_id) if rationale_event_id else None,
        "report_id": str(report_id) if report_id else None,
        "net_worth": str(getattr(snap, "net_worth", Decimal("0"))),
        "total_assets": str(total_assets),
        "total_liabilities": str(total_liabs),
        "total_unrealised_gain": str(getattr(snap, "total_unrealised_gain", Decimal("0"))),
        "allocation_pct": _decimal_to_str(rollup),
        "snapshot_json": snap.model_dump(mode="json") if hasattr(snap, "model_dump") else {},
        "has_stale_values": bool(getattr(snap, "has_stale_values", False)),
        "stale_sources": list(getattr(snap, "stale_sources", []) or []),
    }
    snap_id = insert_snapshot(sb, row)
    return {"id": snap_id, **row}
