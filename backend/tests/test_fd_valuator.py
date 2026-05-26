from datetime import date

import pytest

from services.valuators.fd_valuator import value_fd


def test_simple_interest():
    # 100000 @ 7% simple, 1 year (non-leap span for exact arithmetic)
    v = value_fd(
        principal=100000.0,
        rate=0.07,
        start=date(2023, 1, 1),
        compounding="simple",
        as_of=date(2024, 1, 1),
    )
    assert round(v, 2) == 107000.00


def test_quarterly_compounding_one_year():
    # 100000 @ 8% quarterly for 1 year -> 100000 * (1.02)^4
    v = value_fd(
        principal=100000.0,
        rate=0.08,
        start=date(2023, 1, 1),
        compounding="quarterly",
        as_of=date(2024, 1, 1),
    )
    assert round(v, 2) == 108243.22


def test_monthly_compounding_two_years():
    # 50000 * (1 + 0.06/12) ** 24  — uses non-leap span so days/365 == 2.0
    v = value_fd(
        principal=50000.0,
        rate=0.06,
        start=date(2022, 1, 1),
        compounding="monthly",
        as_of=date(2024, 1, 1),
    )
    assert round(v, 2) == 56357.99


def test_as_of_before_start_returns_principal():
    v = value_fd(
        principal=100000.0,
        rate=0.07,
        start=date(2025, 6, 1),
        compounding="annual",
        as_of=date(2025, 1, 1),
    )
    assert v == 100000.0


def test_as_of_equal_to_start_returns_principal():
    # Same-day valuation: interest accrues from the day after deposit.
    v = value_fd(
        principal=100000.0,
        rate=0.07,
        start=date(2025, 1, 1),
        compounding="annual",
        as_of=date(2025, 1, 1),
    )
    assert v == 100000.0


def test_unknown_compounding_raises():
    with pytest.raises(ValueError, match="unknown compounding"):
        value_fd(
            principal=100000.0,
            rate=0.07,
            start=date(2023, 1, 1),
            compounding="weekly",
            as_of=date(2024, 1, 1),
        )
