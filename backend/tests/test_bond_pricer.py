from datetime import date
from services.valuators.bond_pricer import price_bond, interpolate_yield


def test_yield_interpolation_midpoint():
    curve = [(1, 6.5), (5, 7.0), (10, 7.3)]
    # midway between 1y (6.5) and 5y (7.0) -> at 3y should be 6.75
    assert round(interpolate_yield(curve, 3.0), 4) == 6.75


def test_yield_interpolation_below_min_clamps():
    curve = [(1, 6.5), (5, 7.0)]
    assert interpolate_yield(curve, 0.5) == 6.5


def test_yield_interpolation_above_max_clamps():
    curve = [(1, 6.5), (5, 7.0)]
    assert interpolate_yield(curve, 30.0) == 7.0


def test_par_bond_prices_at_face():
    # 5y bond, 7% coupon, curve flat at 7%, no spread -> price ≈ face
    curve = [(1, 7.0), (5, 7.0), (10, 7.0)]
    px = price_bond(
        face=1000.0,
        coupon_pct=7.0,
        maturity=date(2030, 1, 1),
        as_of=date(2025, 1, 1),
        curve=curve,
        spread_bps=0,
        frequency=1,
    )
    assert 995.0 <= px <= 1005.0


def test_yield_above_coupon_prices_below_face():
    curve = [(1, 8.0), (5, 8.0), (10, 8.0)]
    px = price_bond(
        face=1000.0,
        coupon_pct=7.0,
        maturity=date(2030, 1, 1),
        as_of=date(2025, 1, 1),
        curve=curve,
        spread_bps=0,
        frequency=1,
    )
    assert px < 1000.0


def test_credit_spread_lowers_price():
    curve = [(1, 7.0), (5, 7.0), (10, 7.0)]
    base = price_bond(
        face=1000.0, coupon_pct=7.0, maturity=date(2030, 1, 1),
        as_of=date(2025, 1, 1), curve=curve, spread_bps=0, frequency=1,
    )
    with_spread = price_bond(
        face=1000.0, coupon_pct=7.0, maturity=date(2030, 1, 1),
        as_of=date(2025, 1, 1), curve=curve, spread_bps=200, frequency=1,
    )
    assert with_spread < base
