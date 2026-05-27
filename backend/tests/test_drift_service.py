"""Tests for backend.services.drift_service.compute_drift."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.services import drift_service
from backend.services.drift_service import compute_drift


def _sb():
    return MagicMock()


def test_returns_none_when_no_target():
    with patch.object(drift_service, "get_active_target", return_value=None):
        result = compute_drift(_sb(), "c1")
    assert result is None


def test_in_band_when_close_to_target():
    # target 45%, band 5% → 40-50% ok; actual 46% → in band
    target_pct = {
        "equity": "45", "debt": "35", "gold": "8", "cash": "10", "alternatives": "2"
    }
    band_pct = {
        "equity": "5", "debt": "5", "gold": "2", "cash": "3", "alternatives": "3"
    }
    actual_pct = {
        "equity": "0.46", "debt": "0.34", "gold": "0.08", "cash": "0.10", "alternatives": "0.02"
    }
    result = compute_drift(
        _sb(), "c1",
        target_pct=target_pct, band_pct=band_pct, actual_pct=actual_pct,
    )
    equity = next(r for r in result if r["class"] == "equity")
    assert equity["status"] == "ok"


def test_over_breach_flagged():
    target_pct = {
        "equity": "45", "debt": "35", "gold": "8", "cash": "10", "alternatives": "2"
    }
    band_pct = {
        "equity": "5", "debt": "5", "gold": "2", "cash": "3", "alternatives": "3"
    }
    actual_pct = {
        "equity": "0.55", "debt": "0.25", "gold": "0.08", "cash": "0.10", "alternatives": "0.02"
    }
    result = compute_drift(
        _sb(), "c1",
        target_pct=target_pct, band_pct=band_pct, actual_pct=actual_pct,
    )
    equity = next(r for r in result if r["class"] == "equity")
    debt = next(r for r in result if r["class"] == "debt")
    assert equity["status"] == "over"
    assert debt["status"] == "under"


def test_exactly_at_band_edge_is_ok():
    # target 45, band 5 → 40-50 inclusive; actual exactly 50 → ok
    target_pct = {
        "equity": "45", "debt": "35", "gold": "8", "cash": "10", "alternatives": "2"
    }
    band_pct = {
        "equity": "5", "debt": "5", "gold": "2", "cash": "3", "alternatives": "3"
    }
    actual_pct = {
        "equity": "0.50", "debt": "0.30", "gold": "0.08", "cash": "0.10", "alternatives": "0.02"
    }
    result = compute_drift(
        _sb(), "c1",
        target_pct=target_pct, band_pct=band_pct, actual_pct=actual_pct,
    )
    equity = next(r for r in result if r["class"] == "equity")
    assert equity["status"] == "ok"
