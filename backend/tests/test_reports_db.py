"""Tests for reports_db.update_report_text."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from db import reports_db


@pytest.mark.asyncio
async def test_update_report_text_returns_true_on_success():
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "abc", "generated_text": "new text"}
    ]
    with patch("db.reports_db.get_supabase", return_value=fake_supabase):
        result = await reports_db.update_report_text("abc", "new text")
    assert result is True
    fake_supabase.table.assert_called_with("reports")


@pytest.mark.asyncio
async def test_update_report_text_returns_false_when_no_row_updated():
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    with patch("db.reports_db.get_supabase", return_value=fake_supabase):
        result = await reports_db.update_report_text("missing", "x")
    assert result is False
