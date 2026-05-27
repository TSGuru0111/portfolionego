"""PV-of-cashflows bond pricer with linear-interpolated yield curve."""
from __future__ import annotations
from datetime import date


def interpolate_yield(curve: list[tuple[float, float]], tenor_years: float) -> float:
    """Linearly interpolate the yield curve at `tenor_years`.

    `curve` is a sorted list of (tenor_years, yield_pct).
    Clamps to the nearest endpoint outside the curve's range.
    """
    if not curve:
        raise ValueError("empty yield curve")
    pts = sorted(curve)
    if tenor_years <= pts[0][0]:
        return pts[0][1]
    if tenor_years >= pts[-1][0]:
        return pts[-1][1]
    for (t0, y0), (t1, y1) in zip(pts, pts[1:]):
        if t0 <= tenor_years <= t1:
            return y0 + (y1 - y0) * (tenor_years - t0) / (t1 - t0)
    return pts[-1][1]


def price_bond(
    face: float,
    coupon_pct: float,
    maturity: date,
    as_of: date,
    curve: list[tuple[float, float]],
    spread_bps: int = 0,
    frequency: int = 1,
) -> float:
    """Discounted-cashflow price for a vanilla coupon bond.

    Returns INR price for one unit of `face`.
    """
    years_to_maturity = (maturity - as_of).days / 365.25
    if years_to_maturity <= 0:
        return float(face)
    base_y = interpolate_yield(curve, years_to_maturity) / 100.0
    discount = base_y + spread_bps / 10_000.0
    coupon = face * coupon_pct / 100.0 / frequency
    periods = max(1, int(round(years_to_maturity * frequency)))
    r = discount / frequency
    pv = 0.0
    for k in range(1, periods + 1):
        pv += coupon / (1 + r) ** k
    pv += face / (1 + r) ** periods
    return float(pv)
