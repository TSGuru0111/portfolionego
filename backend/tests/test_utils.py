"""Unit tests for the utility layer (Day 2 deliverable)."""
from __future__ import annotations

from datetime import date

from utils.formatters import (
    format_cr,
    format_date_in,
    format_inr,
    format_month,
    format_pct,
)
from utils.json_safe import safe_parse_json
from utils.token_counter import estimate_tokens, fits_within
from utils.validators import validate_context


# ─── validate_context ───

def _ok_context() -> dict:
    return {
        "client_name": "Rajesh Mehta",
        "portfolio_return": 4.2,
        "nifty_return": 3.1,
        "holdings": [
            {"ticker": "TCS", "source": "live"},
            {"ticker": "INFY", "source": "live"},
        ],
    }


def test_validate_context_ok():
    ok, reason = validate_context(_ok_context())
    assert ok is True
    assert reason == "OK"


def test_validate_context_missing_client_name():
    ctx = _ok_context()
    ctx["client_name"] = ""
    ok, reason = validate_context(ctx)
    assert ok is False
    assert "Client name" in reason


def test_validate_context_no_holdings():
    ctx = _ok_context()
    ctx["holdings"] = []
    ok, reason = validate_context(ctx)
    assert ok is False
    assert "no holdings" in reason.lower()


def test_validate_context_missing_portfolio_return():
    ctx = _ok_context()
    ctx["portfolio_return"] = None
    ok, reason = validate_context(ctx)
    assert ok is False
    assert "portfolio return" in reason.lower()


def test_validate_context_too_many_unavailable():
    ctx = _ok_context()
    ctx["holdings"] = [
        {"ticker": "A", "source": "unavailable"},
        {"ticker": "B", "source": "unavailable"},
        {"ticker": "C", "source": "live"},
    ]
    ok, reason = validate_context(ctx)
    assert ok is False
    assert "unavailable" in reason.lower()


# ─── safe_parse_json ───

def test_safe_parse_json_clean_object():
    assert safe_parse_json('{"score": 9}') == {"score": 9}


def test_safe_parse_json_with_markdown_fences():
    raw = "```json\n{\"score\": 7, \"weakest_section\": \"S3\"}\n```"
    parsed = safe_parse_json(raw)
    assert parsed["score"] == 7
    assert parsed["weakest_section"] == "S3"


def test_safe_parse_json_with_preamble():
    raw = "Here is the result: {\"score\": 8}\nThank you."
    assert safe_parse_json(raw)["score"] == 8


def test_safe_parse_json_malformed_returns_defaults():
    parsed = safe_parse_json("totally broken { not json")
    assert parsed["score"] == 8
    assert parsed["reason"] == "json_parse_error"


def test_safe_parse_json_empty_input():
    parsed = safe_parse_json("")
    assert parsed["score"] == 8


# ─── token_counter ───

def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_short():
    assert estimate_tokens("hello") >= 1


def test_estimate_tokens_proportional():
    short = estimate_tokens("a" * 100)
    long = estimate_tokens("a" * 400)
    assert long > short


def test_fits_within_true():
    assert fits_within("short text", max_tokens=100) is True


def test_fits_within_false():
    assert fits_within("a" * 10_000, max_tokens=100) is False


# ─── formatters ───

def test_format_inr_basic():
    assert format_inr(123456.78) == "₹1,23,456.78"


def test_format_pct_positive():
    assert format_pct(4.234) == "+4.23%"


def test_format_pct_negative():
    assert format_pct(-1.5) == "-1.50%"


def test_format_cr():
    assert format_cr(2.5) == "₹2.50 Cr"


def test_format_month():
    assert format_month("2026-04") == "April 2026"


def test_format_date_in_from_date():
    assert format_date_in(date(2026, 4, 15)) == "15 April 2026"
