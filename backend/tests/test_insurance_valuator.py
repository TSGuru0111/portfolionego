from datetime import date
from services.valuators.insurance_valuator import surrender_value


def test_term_plan_always_zero():
    v = surrender_value(
        policy_type="term",
        premium_amount=50_000.0,
        premium_frequency="annual",
        start=date(2020, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert v == 0.0


def test_endowment_under_three_years_returns_zero():
    v = surrender_value(
        policy_type="endowment",
        premium_amount=100_000.0,
        premium_frequency="annual",
        start=date(2024, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert v == 0.0


def test_endowment_three_years_factor_thirty_pct():
    # 3 full years paid, factor = 0.30 + 0.05 * (3-3) = 0.30
    # premiums paid = 100k * 4 (years 0,1,2,3) = 400k
    # value = 0.30 * 400_000 = 120_000
    v = surrender_value(
        policy_type="endowment",
        premium_amount=100_000.0,
        premium_frequency="annual",
        start=date(2022, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert round(v, 2) == 120_000.00


def test_endowment_caps_at_ninety_pct():
    # 20 years in: factor = min(0.90, 0.30 + 0.05*17) = 0.90
    # premiums = 100k * 21 = 2_100_000; value = 0.90 * 2_100_000 = 1_890_000
    v = surrender_value(
        policy_type="endowment",
        premium_amount=100_000.0,
        premium_frequency="annual",
        start=date(2005, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert round(v, 2) == 1_890_000.00


def test_monthly_frequency_counts_payments_correctly():
    # 5 years monthly @ 5000 -> 60 payments paid by anniversary
    # factor at 5y = 0.30 + 0.05*2 = 0.40
    # value = 0.40 * 60 * 5000 = 120_000
    v = surrender_value(
        policy_type="endowment",
        premium_amount=5_000.0,
        premium_frequency="monthly",
        start=date(2020, 1, 1),
        as_of=date(2025, 1, 1),
    )
    assert round(v, 2) == 120_000.00
