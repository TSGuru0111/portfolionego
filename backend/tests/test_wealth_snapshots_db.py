"""Tests for backend.db.wealth_snapshots_db (mocked Supabase)."""
from __future__ import annotations

from unittest.mock import MagicMock

from db.wealth_snapshots_db import (
    get_latest_snapshot,
    get_snapshots_range,
    insert_snapshot,
)


def _chain(returned_data):
    res = MagicMock()
    res.data = returned_data
    c = MagicMock()
    for m in ("insert", "select", "eq", "lte", "gte", "order", "limit", "single", "is_"):
        getattr(c, m).return_value = c
    c.execute.return_value = res
    return c


def _sb(data):
    sb = MagicMock()
    sb.table.return_value = _chain(data)
    return sb


def test_get_latest_returns_row():
    row = {"id": "snap-1", "client_id": "c1"}
    sb = _sb([row])
    result = get_latest_snapshot(sb, "c1")
    assert result["id"] == "snap-1"


def test_get_latest_returns_none_when_empty():
    sb = _sb([])
    result = get_latest_snapshot(sb, "c1")
    assert result is None


def test_insert_returns_id():
    chain = _chain([{"id": "snap-new"}])
    chain.single.return_value = chain
    single_res = MagicMock()
    single_res.data = {"id": "snap-new"}
    chain.execute.return_value = single_res

    sb = MagicMock()
    sb.table.return_value = chain

    result = insert_snapshot(sb, {"client_id": "c1", "trigger": "monthly"})
    assert result == "snap-new"


def test_get_snapshots_range_returns_list():
    rows = [{"id": "s1"}, {"id": "s2"}]
    sb = _sb(rows)
    result = get_snapshots_range(sb, "c1", "2026-01-01", "2026-12-31")
    assert len(result) == 2
