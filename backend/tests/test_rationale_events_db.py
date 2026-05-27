"""Tests for backend.db.rationale_events_db (mocked Supabase)."""
from __future__ import annotations

from unittest.mock import MagicMock

from backend.db.rationale_events_db import (
    insert_rationale_event,
    list_rationale_events,
    update_snapshot_id,
)


def _chain(data):
    res = MagicMock()
    res.data = data
    c = MagicMock()
    for m in ("insert", "update", "select", "eq", "in_", "gte", "lte",
              "order", "limit", "single", "is_"):
        getattr(c, m).return_value = c
    c.execute.return_value = res
    return c


def _sb(data):
    sb = MagicMock()
    sb.table.return_value = _chain(data)
    return sb


def test_insert_returns_row():
    row = {"id": "ev-1", "event_type": "rebalance"}
    chain = _chain(row)
    chain.single.return_value = chain
    single_res = MagicMock()
    single_res.data = row
    chain.execute.return_value = single_res
    sb = MagicMock()
    sb.table.return_value = chain

    result = insert_rationale_event(
        sb,
        client_id="c1",
        event_type="rebalance",
        event_date="2026-05-01",
        title="Rebalance",
        body="why",
        author_rm_id="rm1",
    )
    assert result["id"] == "ev-1"


def test_update_snapshot_id_calls_update():
    sb = _sb([])
    update_snapshot_id(sb, "ev-id", "snap-id")
    sb.table.return_value.update.assert_called_with({"snapshot_id": "snap-id"})


def test_list_rationale_events_returns_list():
    rows = [{"id": "e1"}, {"id": "e2"}]
    sb = _sb(rows)
    result = list_rationale_events(sb, "c1", "2026-01-01", "2026-12-31")
    assert len(result) == 2


def test_list_rationale_events_with_type_filter():
    rows = [{"id": "e1", "event_type": "rebalance"}]
    c = _chain(rows)
    sb = MagicMock()
    sb.table.return_value = c
    result = list_rationale_events(sb, "c1", "2026-01-01", "2026-12-31", types=["rebalance"])
    c.in_.assert_called_with("event_type", ["rebalance"])
    assert len(result) == 1
