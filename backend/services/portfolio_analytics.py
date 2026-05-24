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


from datetime import date as _date
from scipy.optimize import brentq

_BUY_TYPES = {"BUY", "SIP", "PURCHASE"}


def _npv(rate: float, cashflows: list[tuple[_date, float]]) -> float:
    t0 = cashflows[0][0]
    total = 0.0
    for d, cf in cashflows:
        years = (d - t0).days / 365.0
        total += cf / ((1 + rate) ** years)
    return total


def compute_xirr(
    transactions: list[dict[str, Any]],
    current_value: float,
    today: _date | None = None,
) -> float | None:
    """Return XIRR as a decimal (0.14 == 14% p.a.).

    BUY/SIP/PURCHASE cashflows are outflows (negative); everything else is an
    inflow. The terminal current_value is added as a positive cashflow at
    `today`. Returns None when inputs are insufficient or root-finder fails.
    """
    if not transactions:
        return None
    if current_value is None or current_value <= 0:
        return None

    cashflows: list[tuple[_date, float]] = []
    for t in transactions:
        try:
            amt = float(t["total_value"])
        except (KeyError, TypeError, ValueError):
            continue
        sign = -1 if (t.get("txn_type") or "").upper() in _BUY_TYPES else +1
        cashflows.append((t["txn_date"], sign * amt))

    cashflows.append((today or _date.today(), float(current_value)))
    cashflows.sort(key=lambda x: x[0])

    try:
        return brentq(_npv, -0.99, 10.0, args=(cashflows,), maxiter=200)
    except (ValueError, RuntimeError):
        return None
