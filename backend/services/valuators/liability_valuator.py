"""Loan / liability outstanding-balance calculator."""
from __future__ import annotations
from datetime import date


def emi_for(principal: float, rate: float, months: int) -> float:
    """Closed-form EMI for a standard amortising loan."""
    if rate == 0:
        return principal / months
    r = rate / 12.0
    factor = (1 + r) ** months
    return principal * r * factor / (factor - 1)


def _months_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month)


def outstanding_balance(
    principal: float,
    rate: float,
    months: int,
    start: date,
    as_of: date,
    emi: float | None = None,
) -> float:
    """Outstanding balance after k EMIs have been paid (k = months elapsed)."""
    if as_of <= start:
        return float(principal)
    k = min(_months_between(start, as_of), months)
    if k >= months:
        return 0.0
    pay = emi if emi is not None else emi_for(principal, rate, months)
    r = rate / 12.0
    if r == 0:
        return max(0.0, principal - pay * k)
    bal = principal * (1 + r) ** k - pay * (((1 + r) ** k - 1) / r)
    return max(0.0, float(bal))
