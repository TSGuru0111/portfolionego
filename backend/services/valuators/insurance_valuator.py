"""Insurance policy surrender-value calculator."""
from __future__ import annotations
from datetime import date


_FREQ_PER_YEAR = {"annual": 1, "semiannual": 2, "quarterly": 4, "monthly": 12, "single": 1}


def _full_years(start: date, as_of: date) -> int:
    """Count completed calendar years between start and as_of."""
    years = as_of.year - start.year
    if (as_of.month, as_of.day) < (start.month, start.day):
        years -= 1
    return max(0, years)


def _full_months(start: date, as_of: date) -> int:
    """Count completed calendar months between start and as_of."""
    months = (as_of.year - start.year) * 12 + (as_of.month - start.month)
    if as_of.day < start.day:
        months -= 1
    return max(0, months)


def _premiums_paid(
    premium_amount: float,
    frequency: str,
    start: date,
    as_of: date,
) -> float:
    if as_of < start:
        return 0.0
    if frequency == "single":
        return float(premium_amount)
    n = _FREQ_PER_YEAR.get(frequency)
    if n is None:
        raise ValueError(f"unknown frequency: {frequency}")
    # Count payments made:
    # Annual: initial payment at year 0 plus one each completed year = full_years + 1.
    # Sub-annual (monthly, quarterly, semiannual): one payment per completed period
    #   (the period that starts on as_of is not yet paid).
    if n == 1:
        payments = _full_years(start, as_of) + 1
    elif n == 12:
        payments = _full_months(start, as_of)
    else:
        # For semiannual (2) and quarterly (4): completed months / months-per-period
        months_per_period = 12 // n
        payments = _full_months(start, as_of) // months_per_period
    return float(premium_amount * payments)


def surrender_value(
    policy_type: str,
    premium_amount: float,
    premium_frequency: str,
    start: date,
    as_of: date,
) -> float:
    """Estimated surrender value.

    Term plans return 0. Endowment/ULIP/money-back use a piecewise factor:
        years < 3   -> 0
        years >= 3  -> min(0.90, 0.30 + 0.05 * (years - 3)) * premiums_paid
    """
    if policy_type == "term":
        return 0.0
    full_yrs = _full_years(start, as_of)
    if full_yrs < 3:
        return 0.0
    factor = min(0.90, 0.30 + 0.05 * (full_yrs - 3))
    paid = _premiums_paid(premium_amount, premium_frequency, start, as_of)
    return float(factor * paid)
