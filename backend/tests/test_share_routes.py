"""Tests for share routes."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

def _make_client():
    from main import app
    return TestClient(app)

_CLIENT_UUID = "11111111-1111-1111-1111-111111111111"

_VALID_TOKEN_ROW = {
    "id": "tok-1",
    "client_id": _CLIENT_UUID,
    "token": "valid-token-uuid",
    "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
}

_PORTFOLIO_DATA = {
    "client": {"id": _CLIENT_UUID, "name": "Test Client"},
    "holdings": [],
    "portfolio_return": None,
    "nifty_return": None,
    "has_stale_prices": False,
    "stale_tickers": [],
}

def test_public_portfolio_valid_token():
    c = _make_client()
    with patch("routes.share.resolve_token", return_value=_VALID_TOKEN_ROW), \
         patch("routes.share.get_client_portfolio", new=AsyncMock(return_value=_PORTFOLIO_DATA)):
        resp = c.get("/share/valid-token-uuid/portfolio")
    assert resp.status_code == 200

def test_public_portfolio_expired_token():
    c = _make_client()
    with patch("routes.share.resolve_token", return_value=None):
        resp = c.get("/share/expired-token/portfolio")
    assert resp.status_code == 403
    assert "expired" in resp.json()["detail"]

def test_public_portfolio_unknown_token():
    c = _make_client()
    with patch("routes.share.resolve_token", return_value=None):
        resp = c.get("/share/unknown-token/portfolio")
    assert resp.status_code == 403

def test_create_token_endpoint():
    c = _make_client()
    new_row = {**_VALID_TOKEN_ROW, "token": "new-token-uuid"}
    with patch("routes.share.create_share_token", return_value=new_row), \
         patch("routes.share.get_supabase", return_value=MagicMock()):
        resp = c.post(
            "/clients/11111111-1111-1111-1111-111111111111/share-token",
            json={"expires_in_days": 30},
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "share_url" in body

def test_get_token_endpoint_404_when_none():
    c = _make_client()
    with patch("routes.share.get_latest_share_token", return_value=None), \
         patch("routes.share.get_supabase", return_value=MagicMock()):
        resp = c.get(
            "/clients/11111111-1111-1111-1111-111111111111/share-token",
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 404
