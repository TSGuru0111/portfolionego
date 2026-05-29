"""Tests for backend.models.wealth_snapshot."""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from models.wealth_snapshot import WealthSnapshotRow


def _row(**overrides):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "client_id": "22222222-2222-2222-2222-222222222222",
        "as_of": "2026-05-01T00:00:00+00:00",
        "trigger": "monthly",
        "rationale_event_id": None,
        "report_id": None,
        "net_worth": "1000000.00",
        "total_assets": "1200000.00",
        "total_liabilities": "200000.00",
        "total_unrealised_gain": "50000.00",
        "allocation_pct": {
            "equity": 0.45, "debt": 0.35, "gold": 0.08,
            "cash": 0.10, "alternatives": 0.02,
        },
        "snapshot_json": {"net_worth": "1000000.00"},
        "has_stale_values": False,
        "stale_sources": [],
        "created_at": "2026-05-01T00:00:01+00:00",
    }
    base.update(overrides)
    return base


def test_row_parses_minimum():
    row = WealthSnapshotRow.model_validate(_row())
    assert row.trigger == "monthly"
    assert row.allocation_pct["equity"] == Decimal("0.45")


def test_row_rejects_bad_trigger():
    with pytest.raises(ValidationError):
        WealthSnapshotRow.model_validate(_row(trigger="adhoc"))
