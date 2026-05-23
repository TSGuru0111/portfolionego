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
