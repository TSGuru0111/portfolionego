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
