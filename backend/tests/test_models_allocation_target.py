"""Tests for backend.models.allocation_target."""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.models.allocation_target import AllocationTarget, AllocationTargetWrite


def _body(**overrides):
    base = {
        "equity_pct": Decimal("45"),
        "debt_pct": Decimal("35"),
        "gold_pct": Decimal("8"),
        "cash_pct": Decimal("10"),
        "alternatives_pct": Decimal("2"),
        "equity_band_pct": Decimal("5"),
        "debt_band_pct": Decimal("5"),
        "gold_band_pct": Decimal("2"),
        "cash_band_pct": Decimal("3"),
        "alternatives_band_pct": Decimal("3"),
        "rationale": {
            "event_date": "2026-05-01T00:00:00+00:00",
            "title": "Quarterly rebalance",
            "rationale_text": "Shifted to neutral after rally.",
        },
    }
    base.update(overrides)
    return base


def test_write_accepts_summing_to_100():
    body = AllocationTargetWrite.model_validate(_body())
    assert body.equity_pct == Decimal("45")
    assert body.rationale.title == "Quarterly rebalance"


def test_write_rejects_sum_not_100():
    with pytest.raises(ValidationError):
        AllocationTargetWrite.model_validate(_body(equity_pct=Decimal("50")))


def test_write_rejects_negative_pct():
    bad = _body(equity_pct=Decimal("-1"), debt_pct=Decimal("81"))
    with pytest.raises(ValidationError):
        AllocationTargetWrite.model_validate(bad)


def test_target_row_validates():
    row = AllocationTarget.model_validate({
        "id": "11111111-1111-1111-1111-111111111111",
        "client_id": "22222222-2222-2222-2222-222222222222",
        "effective_from": "2026-01-01T00:00:00+00:00",
        "effective_to": None,
        "equity_pct": "45", "debt_pct": "35", "gold_pct": "8",
        "cash_pct": "10", "alternatives_pct": "2",
        "equity_band_pct": "5", "debt_band_pct": "5", "gold_band_pct": "2",
        "cash_band_pct": "3", "alternatives_band_pct": "3",
        "rationale_event_id": "33333333-3333-3333-3333-333333333333",
        "created_by_rm_id": "44444444-4444-4444-4444-444444444444",
        "created_at": "2026-01-01T00:00:01+00:00",
    })
    assert row.effective_to is None
