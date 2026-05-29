from __future__ import annotations
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from services import context_builder
from services.context_builder import build_change_summary

_TODAY = date.today()
_WINDOW = 30

def _sb():
    return MagicMock()

def _make_event(title, rationale, days_ago=5):
    return {"event_date": str(_TODAY - timedelta(days=days_ago)),
            "title": title, "rationale_text": rationale}

def _make_snapshot():
    return {"allocation_pct": {"equity": "0.55", "debt": "0.25",
            "gold": "0.08", "cash": "0.10", "alternatives": "0.02"}}

def _make_target():
    return {"equity_pct": "45", "debt_pct": "35", "gold_pct": "8",
            "cash_pct": "10", "alternatives_pct": "2",
            "equity_band_pct": "5", "debt_band_pct": "5",
            "gold_band_pct": "2", "cash_band_pct": "3",
            "alternatives_band_pct": "3"}

def test_returns_empty_string_when_no_events():
    with patch.object(context_builder, "_fetch_events_in_window", return_value=[]), \
         patch.object(context_builder, "_fetch_latest_snapshot", return_value=None), \
         patch.object(context_builder, "_fetch_active_target", return_value=None):
        assert build_change_summary(_sb(), "c1", _WINDOW) == ""

def test_renders_event_title_and_rationale():
    events = [_make_event("Gold target raised", "Inflation hedge strategy")]
    with patch.object(context_builder, "_fetch_events_in_window", return_value=events), \
         patch.object(context_builder, "_fetch_latest_snapshot", return_value=None), \
         patch.object(context_builder, "_fetch_active_target", return_value=None):
        result = build_change_summary(_sb(), "c1", _WINDOW)
    assert "Gold target raised" in result
    assert "Inflation hedge strategy" in result
    assert "Portfolio changes since last review" in result

def test_caps_total_at_500_chars():
    events = [_make_event(f"Event {i}", "X" * 300) for i in range(10)]
    with patch.object(context_builder, "_fetch_events_in_window", return_value=events), \
         patch.object(context_builder, "_fetch_latest_snapshot", return_value=None), \
         patch.object(context_builder, "_fetch_active_target", return_value=None):
        result = build_change_summary(_sb(), "c1", _WINDOW)
    assert len(result) <= 500
    assert "more event" in result

def test_drift_line_shows_over():
    events = [_make_event("Rebalance", "Equity was overweight")]
    with patch.object(context_builder, "_fetch_events_in_window", return_value=events), \
         patch.object(context_builder, "_fetch_latest_snapshot", return_value=_make_snapshot()), \
         patch.object(context_builder, "_fetch_active_target", return_value=_make_target()):
        result = build_change_summary(_sb(), "c1", _WINDOW)
    assert "equity" in result.lower()
    assert "over" in result.lower()
