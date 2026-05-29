"""Tests for backend.services.allocation_rollup.roll_up_to_classes."""
from __future__ import annotations

from decimal import Decimal

from services.allocation_rollup import roll_up_to_classes


class _Holding:
    def __init__(self, current_value, category=None):
        self.current_value = Decimal(str(current_value))
        self.category = category


class _Bucket:
    def __init__(self, holdings):
        self.holdings = holdings


class _Snap:
    """Stub: rollup reads `.<bucket>.holdings` and each holding's `.current_value` / `.category`."""
    def __init__(self, **buckets):
        self.mutual_funds = _Bucket(buckets.get("mutual_funds", []))
        self.bonds = _Bucket(buckets.get("bonds", []))
        self.gold = _Bucket(buckets.get("gold", []))
        self.cash = _Bucket(buckets.get("cash", []))
        self.fixed_deposits = _Bucket(buckets.get("fixed_deposits", []))
        self.insurance = _Bucket(buckets.get("insurance", []))


def test_pure_equity_mf_rolls_to_equity():
    snap = _Snap(mutual_funds=[_Holding(100, "equity")])
    out = roll_up_to_classes(snap)
    assert out == {"equity": Decimal("1"), "debt": Decimal("0"),
                   "gold": Decimal("0"), "cash": Decimal("0"),
                   "alternatives": Decimal("0")}


def test_debt_mf_and_bond_both_go_to_debt():
    snap = _Snap(
        mutual_funds=[_Holding(50, "debt")],
        bonds=[_Holding(50)],
    )
    out = roll_up_to_classes(snap)
    assert out["debt"] == Decimal("1")
    assert out["equity"] == Decimal("0")


def test_hybrid_mf_maps_to_equity():
    snap = _Snap(mutual_funds=[_Holding(100, "hybrid")])
    assert roll_up_to_classes(snap)["equity"] == Decimal("1")


def test_liquid_mf_maps_to_debt():
    snap = _Snap(mutual_funds=[_Holding(100, "liquid")])
    assert roll_up_to_classes(snap)["debt"] == Decimal("1")


def test_fd_and_insurance_map_to_debt():
    snap = _Snap(
        fixed_deposits=[_Holding(60)],
        insurance=[_Holding(40)],
    )
    assert roll_up_to_classes(snap)["debt"] == Decimal("1")


def test_full_mix_sums_to_one():
    snap = _Snap(
        mutual_funds=[_Holding(45, "equity")],
        bonds=[_Holding(35)],
        gold=[_Holding(8)],
        cash=[_Holding(10)],
        fixed_deposits=[_Holding(2)],
    )
    out = roll_up_to_classes(snap)
    assert sum(out.values()) == Decimal("1")
    assert out["alternatives"] == Decimal("0")


def test_empty_snapshot_returns_zeros():
    out = roll_up_to_classes(_Snap())
    assert out == {"equity": Decimal("0"), "debt": Decimal("0"),
                   "gold": Decimal("0"), "cash": Decimal("0"),
                   "alternatives": Decimal("0")}
