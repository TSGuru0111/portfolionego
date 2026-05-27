"""Tests for backend.db.allocation_targets_db (mocked Supabase)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from backend.db.allocation_targets_db import (
    change_allocation_target,
    get_active_target,
    get_target_history,
)


def _chain(data):
    res = MagicMock()
    res.data = data
    c = MagicMock()
    for m in ("select", "eq", "is_", "order", "limit"):
        getattr(c, m).return_value = c
    c.execute.return_value = res
    return c


def test_get_active_target_returns_row():
    row = {"id": "t1", "client_id": "c1", "effective_to": None}
    c = _chain([row])
    sb = MagicMock()
    sb.table.return_value = c
    result = get_active_target(sb, "c1")
    assert result["id"] == "t1"
    c.is_.assert_called_with("effective_to", "null")


def test_get_active_target_returns_none_when_empty():
    c = _chain([])
    sb = MagicMock()
    sb.table.return_value = c
    result = get_active_target(sb, "c1")
    assert result is None


def test_get_target_history_returns_list():
    rows = [{"id": "t1"}, {"id": "t2"}]
    c = _chain(rows)
    sb = MagicMock()
    sb.table.return_value = c
    result = get_target_history(sb, "c1")
    assert len(result) == 2


def test_change_allocation_target_calls_rpc():
    rpc_res = MagicMock()
    rpc_res.data = "new-target-uuid"
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = rpc_res

    pcts = {
        "equity": Decimal("45"), "debt": Decimal("35"),
        "gold": Decimal("8"), "cash": Decimal("10"), "alternatives": Decimal("2"),
    }
    bands = {
        "equity": Decimal("5"), "debt": Decimal("5"),
        "gold": Decimal("2"), "cash": Decimal("3"), "alternatives": Decimal("3"),
    }
    result = change_allocation_target(
        sb,
        client_id="c1",
        risk_profile="Moderate",
        target_pct=pcts,
        band_pct=bands,
        rationale_event_id="e1",
        set_by="rm1",
    )
    sb.rpc.assert_called_once()
    call_args = sb.rpc.call_args[0]
    assert call_args[0] == "change_allocation_target"
    assert call_args[1]["p_client_id"] == "c1"
    assert call_args[1]["p_equity_pct"] == "45"
    assert result["id"] == "new-target-uuid"
