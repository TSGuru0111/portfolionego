"""Pure analytics functions for KPI tiles.

Every function returns None when its inputs are insufficient so the frontend
can render an em-dash instead of a misleading 0. Never coerce None to 0 here.
"""
from __future__ import annotations

from typing import Any


def _mv(holding: dict[str, Any]) -> float:
    qty = holding.get("qty") or 0
    price = holding.get("current_price") or 0
    try:
        return float(qty) * float(price)
    except (TypeError, ValueError):
        return 0.0


def compute_concentration(holdings: list[dict[str, Any]]) -> float | None:
    """Return top-3 holdings as a percent of total market value."""
    if not holdings:
        return None
    mvs = [_mv(h) for h in holdings]
    total = sum(mvs)
    if total <= 0:
        return None
    top3 = sum(sorted(mvs, reverse=True)[:3])
    return top3 / total * 100.0
