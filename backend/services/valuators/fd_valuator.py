"""Fixed-deposit current-value calculator."""
from __future__ import annotations
from datetime import date


_FREQ = {"simple": None, "annual": 1, "quarterly": 4, "monthly": 12, "daily": 365}


def value_fd(
    principal: float,
    rate: float,
    start: date,
    compounding: str,
    as_of: date,
) -> float:
    """Return the current value of an FD.

    Args:
        principal: deposit amount in INR
        rate: annual rate as a decimal (0.07 == 7%)
        start: deposit start date
        compounding: one of simple, annual, quarterly, monthly, daily
        as_of: valuation date
    """
    if as_of <= start:
        return float(principal)
    years = (as_of - start).days / 365.0
    if compounding == "simple":
        return float(principal * (1 + rate * years))
    n = _FREQ.get(compounding)
    if n is None:
        raise ValueError(f"unknown compounding: {compounding}")
    return float(principal * (1 + rate / n) ** (n * years))
