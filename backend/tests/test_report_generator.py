"""Tests for QA-score-and-reasons extraction (Task 8)."""
from services.report_generator import _extract_score_and_reasons


def test_extract_returns_score_and_reasons():
    raw = '{"score": 8, "reasons": ["good ticker mentions", "client name used"]}'
    result = _extract_score_and_reasons(raw)
    assert result == {"score": 8, "reasons": ["good ticker mentions", "client name used"]}


def test_extract_missing_reasons_defaults_empty():
    raw = '{"score": 7}'
    assert _extract_score_and_reasons(raw) == {"score": 7, "reasons": []}


def test_extract_malformed_returns_zero():
    assert _extract_score_and_reasons("garbage") == {"score": 0, "reasons": []}


def test_extract_clamps_score_range():
    high = '{"score": 99, "reasons": []}'
    assert _extract_score_and_reasons(high)["score"] == 10
    low = '{"score": -3, "reasons": []}'
    assert _extract_score_and_reasons(low)["score"] == 0
