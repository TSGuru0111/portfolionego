"""Tests for build_report_data."""
from __future__ import annotations

from services import html_renderer


def test_build_report_data_returns_expected_keys():
    packet = {
        "client": {"id": "c1", "name": "Test Client",
                   "currency": "INR", "liquidity_need_pct": 10,
                   "income_need_monthly": 0, "tax_bracket": "30",
                   "language": "english"},
        "portfolio": {"holdings": [], "aum_cr": 1.0,
                      "inception_date": "2024-01-01"},
        "holdings": [{"ticker": "TCS", "sector": "IT",
                      "qty": 100, "current_price": 3000,
                      "month_return_pct": 5.0}],
        "month": "2026-04",
        "market": {"nifty_mtd_pct": -2.7, "usd_inr_mtd_pct": 1.0,
                   "crude_mtd_pct": 0.0},
        "letter_text": "Dear Test,\n\nSample body.",
        "qa_score": 8,
        "report_id": "abc",
        "has_stale_prices": False,
    }
    data = html_renderer.build_report_data(packet)
    expected_keys = {
        "report_id", "client_name", "month", "currency", "qa_score",
        "kpis", "holdings", "top_contributors", "top_detractors",
        "sector_allocation", "nav_series", "market_context",
        "next_steps", "letter_text",
    }
    assert expected_keys.issubset(set(data.keys()))
    assert data["client_name"] == "Test Client"
    assert data["letter_text"] == "Dear Test,\n\nSample body."
    assert isinstance(data["next_steps"], list)
    assert len(data["next_steps"]) <= 3


# --- New v2 KPI tests (Task 6) ---

from datetime import date
from services.html_renderer import build_report_data


def _packet(**overrides):
    base = {
        "client": {"name": "Test", "risk_profile": "moderate"},
        "holdings": [
            {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": 1000, "sector": "Technology"},
            {"ticker": "B", "qty":  50, "buy_price": 200, "current_price":  300, "sector": "Debt"},
        ],
        "transactions": [
            {"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 80000},
            {"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 10000},
        ],
        "market": {"nifty_mtd_pct": 1.0, "usdinr_change_pct": 0.0, "crude_change_pct": 0.0},
        "month": "2025-11",
    }
    base.update(overrides)
    return base


def test_report_data_has_new_kpis():
    data = build_report_data(_packet())
    k = data["kpis"]
    assert "absolute_gain" in k
    assert "xirr_pct" in k
    assert "drift_pct" in k
    assert "concentration_pct" in k


def test_report_data_absolute_gain_shape():
    data = build_report_data(_packet())
    g = data["kpis"]["absolute_gain"]
    assert g is None or set(g.keys()) >= {"value", "partial", "missing_tickers"}


def test_report_data_drift_is_number_or_none():
    data = build_report_data(_packet())
    d = data["kpis"]["drift_pct"]
    assert d is None or isinstance(d, (int, float))


def test_report_data_concentration_is_number_or_none():
    data = build_report_data(_packet())
    c = data["kpis"]["concentration_pct"]
    assert c is None or isinstance(c, (int, float))


def test_report_data_missing_prices_yield_none_not_zero():
    packet = _packet(holdings=[
        {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": None, "sector": "Technology"},
    ])
    data = build_report_data(packet)
    assert data["kpis"]["absolute_gain"]["value"] is None
