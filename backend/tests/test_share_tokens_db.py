"""Tests for backend.db.share_tokens_db (mocked Supabase)."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from db.share_tokens_db import create_share_token, get_latest_share_token, resolve_token

def _chain(data):
    res = MagicMock()
    res.data = data
    c = MagicMock()
    for m in ("insert", "select", "eq", "gt", "order", "limit", "single", "is_"):
        getattr(c, m).return_value = c
    c.execute.return_value = res
    return c

def _sb(data):
    sb = MagicMock()
    sb.table.return_value = _chain(data)
    return sb

def test_create_share_token_returns_row():
    row = {"id": "tok-1", "token": "abc-uuid", "client_id": "c1", "expires_at": "2026-06-30T00:00:00+00:00"}
    chain = _chain([row])
    sb = MagicMock()
    sb.table.return_value = chain
    result = create_share_token(sb, client_id="c1", expires_in_days=30, rm_id="rm1")
    assert result["token"] == "abc-uuid"

def test_get_latest_share_token_returns_row():
    row = {"id": "tok-1", "token": "abc-uuid"}
    sb = _sb([row])
    result = get_latest_share_token(sb, "c1")
    assert result["token"] == "abc-uuid"

def test_get_latest_share_token_returns_none_when_empty():
    sb = _sb([])
    assert get_latest_share_token(sb, "c1") is None

def test_resolve_token_valid():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    row = {"id": "tok-1", "client_id": "c1", "token": "abc-uuid", "expires_at": future}
    sb = _sb([row])
    result = resolve_token(sb, "abc-uuid")
    assert result["client_id"] == "c1"

def test_resolve_token_expired_returns_none():
    sb = _sb([])
    result = resolve_token(sb, "abc-uuid")
    assert result is None

def test_resolve_token_unknown_returns_none():
    sb = _sb([])
    result = resolve_token(sb, "does-not-exist")
    assert result is None
