"""Drift computation: actual vs target with per-class tolerance bands."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from db.allocation_targets_db import get_active_target
from db.wealth_snapshots_db import get_latest_snapshot

_CLASSES = ("equity", "debt", "gold", "cash", "alternatives")
_HUNDRED = Decimal("100")


def _d(x: Any) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def compute_drift(
    sb,
    client_id,
    *,
    target_pct: dict | None = None,
    band_pct: dict | None = None,
    actual_pct: dict | None = None,
) -> list[dict[str, Any]] | None:
    """Return per-class drift list, or None when no active target.

    Can be called with explicit dicts (for routes that already fetched the data)
    or with just client_id + sb to fetch from DB.

    Returns a list of {class, target_pct, actual_pct, delta_pct, band_pct, status}.
    """
    if target_pct is None or actual_pct is None or band_pct is None:
        target_row = get_active_target(sb, str(client_id))
        if target_row is None:
            return None
        snap = get_latest_snapshot(sb, str(client_id))
        if snap is None:
            return None
        _target_pct = {
            cls: _d(target_row.get(f"{cls}_pct", 0)) for cls in _CLASSES
        }
        _band_pct = {
            cls: _d(target_row.get(f"{cls}_band_pct", 5)) for cls in _CLASSES
        }
        _actual_pct = {
            cls: _d(snap.get("allocation_pct", {}).get(cls, 0)) * _HUNDRED
            for cls in _CLASSES
        }
    else:
        _target_pct = {cls: _d(target_pct.get(cls, 0)) for cls in _CLASSES}
        _band_pct = {cls: _d(band_pct.get(cls, 5)) for cls in _CLASSES}
        _actual_pct = {
            cls: _d(actual_pct.get(cls, 0)) * _HUNDRED for cls in _CLASSES
        }

    result = []
    for cls in _CLASSES:
        t = _target_pct[cls]
        b = _band_pct[cls]
        a = _actual_pct[cls]
        delta = a - t
        in_band = abs(delta) <= b
        if in_band:
            status = "ok"
        elif delta > 0:
            status = "over"
        else:
            status = "under"
        result.append({
            "class": cls,
            "target_pct": str(t),
            "actual_pct": str(a),
            "delta_pct": str(delta),
            "band_pct": str(b),
            "status": status,
        })
    return result
