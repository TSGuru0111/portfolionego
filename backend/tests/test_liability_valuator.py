import pytest
from datetime import date
from services.valuators.liability_valuator import outstanding_balance, emi_for


def test_emi_derivation_round_loan():
    # 10L home loan, 8% p.a., 240 months
    emi = emi_for(principal=1_000_000.0, rate=0.08, months=240)
    # closed form: 1_000_000 * 0.08/12 * (1 + 0.08/12)^240 /
    #              ((1 + 0.08/12)^240 - 1) ≈ 8364.40
    assert round(emi, 2) == 8364.40


def test_outstanding_at_origination_equals_principal():
    bal = outstanding_balance(
        principal=1_000_000.0,
        rate=0.08,
        months=240,
        start=date(2025, 1, 1),
        as_of=date(2025, 1, 1),
        emi=None,
    )
    assert round(bal, 2) == 1_000_000.00


def test_outstanding_after_one_year():
    bal = outstanding_balance(
        principal=1_000_000.0,
        rate=0.08,
        months=240,
        start=date(2024, 1, 1),
        as_of=date(2025, 1, 1),
        emi=None,
    )
    # 12 payments in -> outstanding should be ~ 979_822
    assert 975_000 < bal < 985_000


def test_outstanding_after_full_tenor_is_zero():
    bal = outstanding_balance(
        principal=1_000_000.0,
        rate=0.08,
        months=240,
        start=date(2005, 1, 1),
        as_of=date(2025, 1, 1),
        emi=None,
    )
    assert round(bal, 2) == 0.00


def test_emi_zero_months_raises():
    with pytest.raises(ValueError, match="months must be positive"):
        emi_for(principal=1_000_000.0, rate=0.08, months=0)


def test_explicit_emi_overrides_derivation():
    bal = outstanding_balance(
        principal=1_000_000.0,
        rate=0.08,
        months=240,
        start=date(2024, 1, 1),
        as_of=date(2025, 1, 1),
        emi=10_000.0,
    )
    # higher EMI -> faster paydown than the round case
    assert bal < 979_822.0
