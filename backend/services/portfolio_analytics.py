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


def compute_absolute_gain(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Return {value, partial, missing_tickers}.

    value is None when ALL holdings are missing current_price OR holdings is empty.
    partial is True when at least one holding was skipped.
    """
    if not holdings:
        return {"value": None, "partial": False, "missing_tickers": []}

    gain = 0.0
    missing: list[str] = []
    counted = 0
    for h in holdings:
        cp = h.get("current_price")
        if cp is None:
            missing.append(h.get("ticker", "?"))
            continue
        try:
            qty = float(h.get("qty") or 0)
            bp = float(h.get("buy_price") or 0)
            cp_f = float(cp)
        except (TypeError, ValueError):
            missing.append(h.get("ticker", "?"))
            continue
        gain += qty * (cp_f - bp)
        counted += 1

    return {
        "value": gain if counted > 0 else None,
        "partial": bool(missing),
        "missing_tickers": missing,
    }


from services.risk_profile import target_for

DEBT_SECTORS: set[str] = {
    "Debt", "Fixed Income", "Bonds", "Government Securities", "Corporate Bonds",
}
CASH_SECTORS: set[str] = {"Cash", "Liquid", "Money Market"}


def _bucket_for(sector: str | None) -> str:
    if not sector:
        return "equity"
    s = sector.strip()
    if s in CASH_SECTORS:
        return "cash"
    if s in DEBT_SECTORS:
        return "debt"
    return "equity"


def compute_drift(
    holdings: list[dict[str, Any]],
    risk_profile: str | None,
) -> float | None:
    """Max absolute % deviation of actual vs target equity/debt/cash allocation.

    Returns None for empty or zero-value portfolios.
    """
    if not holdings:
        return None
    actual = {"equity": 0.0, "debt": 0.0, "cash": 0.0}
    total = sum(_mv(h) for h in holdings)
    if total <= 0:
        return None
    for h in holdings:
        bucket = _bucket_for(h.get("sector"))
        actual[bucket] += _mv(h) / total * 100.0
    target = target_for(risk_profile)
    return max(abs(actual[k] - target[k]) for k in target)
