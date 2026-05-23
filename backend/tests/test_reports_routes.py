"""Tests for PATCH /reports/{id}."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_patch_report_updates_text():
    fake_row = {"id": "abc", "client_id": "c1", "month": "2026-04",
                "generated_text": "old", "qa_score": 8}
    updated_row = {**fake_row, "generated_text": "edited body"}
    with patch("routes.reports.reports_db.get_report",
               new=AsyncMock(side_effect=[fake_row, updated_row])), \
         patch("routes.reports.reports_db.update_report_text",
               new=AsyncMock(return_value=True)):
        res = client.patch("/reports/abc",
                           json={"generated_text": "edited body"})
    assert res.status_code == 200
    assert res.json()["generated_text"] == "edited body"


def test_patch_report_returns_404_when_missing():
    with patch("routes.reports.reports_db.get_report",
               new=AsyncMock(return_value=None)):
        res = client.patch("/reports/missing",
                           json={"generated_text": "x"})
    assert res.status_code == 404


def test_patch_report_returns_422_on_empty_text():
    res = client.patch("/reports/abc", json={"generated_text": ""})
    assert res.status_code == 422


def test_get_report_data_returns_full_dashboard_json():
    fake_row = {"id": "abc", "client_id": "c1", "month": "2026-04",
                "generated_text": "Dear Test,\n\nBody.", "qa_score": 8}
    fake_packet = {
        "client": {"id": "c1", "name": "Test", "currency": "INR",
                   "liquidity_need_pct": 10, "income_need_monthly": 0,
                   "tax_bracket": "30"},
        "portfolio": {"holdings": [], "aum_cr": 1.0,
                      "inception_date": "2024-01-01"},
        "holdings": [],
        "month": "2026-04",
        "nifty_return": -2.7,
        "portfolio_return": None,
        "macro": {"usdinr_change_pct": 1.0, "crude_change_pct": 0.0},
        "has_stale_prices": False,
    }
    with patch("routes.reports.reports_db.get_report",
               new=AsyncMock(return_value=fake_row)), \
         patch("routes.reports.build_context_packet",
               new=AsyncMock(return_value=fake_packet)):
        res = client.get("/reports/abc/data")
    assert res.status_code == 200
    body = res.json()
    for k in ("kpis", "holdings", "top_contributors", "top_detractors",
              "sector_allocation", "market_context", "next_steps",
              "letter_text", "client_name", "month"):
        assert k in body, f"missing key: {k}"
    assert body["letter_text"] == "Dear Test,\n\nBody."


def test_get_report_data_returns_404_when_missing():
    with patch("routes.reports.reports_db.get_report",
               new=AsyncMock(return_value=None)):
        res = client.get("/reports/missing/data")
    assert res.status_code == 404
