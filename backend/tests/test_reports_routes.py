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
