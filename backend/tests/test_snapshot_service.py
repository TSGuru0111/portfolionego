"""Tests for backend.services.snapshot_service.persist_snapshot."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from backend.services import snapshot_service


def _make_snap():
    s = MagicMock()
    s.net_worth = 1000000.0
    s.has_stale_values = False
    s.stale_sources = []
    s.total_unrealised_gain = 50000.0
    mf = MagicMock()
    mf.current_value = 600000.0
    mf.holdings = []
    bonds = MagicMock()
    bonds.current_value = 200000.0
    bonds.holdings = []
    gold = MagicMock()
    gold.current_value = 80000.0
    gold.holdings = []
    cash = MagicMock()
    cash.current_value = 120000.0
    cash.holdings = []
    fds = MagicMock()
    fds.current_value = 0.0
    fds.holdings = []
    ins = MagicMock()
    ins.current_value = 0.0
    ins.holdings = []
    liabs = MagicMock()
    liabs.total_outstanding = 0.0
    s.mutual_funds = mf
    s.bonds = bonds
    s.gold = gold
    s.cash = cash
    s.fixed_deposits = fds
    s.insurance = ins
    s.liabilities = liabs
    s.model_dump.return_value = {"net_worth": 1000000.0}
    return s


def test_persist_snapshot_report_trigger():
    sb = MagicMock()
    fake_snap = _make_snap()
    rollup = {
        "equity": Decimal("0.6"), "debt": Decimal("0.2"),
        "gold": Decimal("0.08"), "cash": Decimal("0.12"), "alternatives": Decimal("0"),
    }

    with patch.object(snapshot_service, "build_wealth_snapshot", return_value=fake_snap), \
         patch.object(snapshot_service, "roll_up_to_classes", return_value=rollup), \
         patch.object(snapshot_service, "insert_snapshot", return_value="snap-id") as mock_ins:
        result = snapshot_service.persist_snapshot(
            sb, client_id="c1", trigger="report", report_id="r1",
        )

    assert result["id"] == "snap-id"
    row = mock_ins.call_args[0][1]
    assert row["trigger"] == "report"
    assert row["report_id"] == "r1"
    assert row["rationale_event_id"] is None
    assert row["client_id"] == "c1"
    assert row["allocation_pct"]["equity"] == "0.6"


def test_persist_snapshot_rationale_trigger():
    sb = MagicMock()
    fake_snap = _make_snap()
    rollup = {
        "equity": Decimal("0.6"), "debt": Decimal("0.2"),
        "gold": Decimal("0.08"), "cash": Decimal("0.12"), "alternatives": Decimal("0"),
    }
    with patch.object(snapshot_service, "build_wealth_snapshot", return_value=fake_snap), \
         patch.object(snapshot_service, "roll_up_to_classes", return_value=rollup), \
         patch.object(snapshot_service, "insert_snapshot", return_value="snap-id") as mock_ins:
        snapshot_service.persist_snapshot(
            sb, client_id="c1", trigger="rationale", rationale_event_id="e1",
        )
    row = mock_ins.call_args[0][1]
    assert row["trigger"] == "rationale"
    assert row["rationale_event_id"] == "e1"
    assert row["report_id"] is None


def test_persist_snapshot_rejects_bad_trigger():
    with pytest.raises(ValueError, match="trigger"):
        snapshot_service.persist_snapshot(MagicMock(), client_id="c1", trigger="foo")
