from __future__ import annotations
from services.prompt_builder import build_prompt_safe, build_strict_prompt

_BASE = {
    "client": {"id": "c1", "name": "Rajesh Mehta", "rm_name": "Priya Sharma"},
    "holdings": [{"ticker": "TCS", "current_price": 3500}],
    "portfolio_return": 2.5, "nifty_return": 1.3, "alpha": 1.2,
    "top_performers": [], "underperformers": [],
    "macro": {"usdinr_change_pct": 0.1, "crude_change_pct": -0.5},
    "news": {}, "weekly_summaries": [], "transactions": [],
    "rationale_trades": [], "has_stale_prices": False, "stale_tickers": [],
    "month": "2026-04", "meta": {"token_estimate": 500, "trimmed": False},
    "cadence": "monthly", "change_summary": "",
}


def test_change_summary_block_present_when_non_empty():
    ctx = {**_BASE, "change_summary": "Portfolio changes since last review:\n[2026-04-03] Gold raised -- inflation hedge."}
    prompt = build_prompt_safe(ctx)
    assert "PORTFOLIO CHANGES SINCE LAST REVIEW" in prompt
    assert "Gold raised" in prompt


def test_change_summary_block_absent_when_empty():
    assert "PORTFOLIO CHANGES SINCE LAST REVIEW" not in build_prompt_safe({**_BASE, "change_summary": ""})


def test_window_label_weekly():
    assert "this week" in build_prompt_safe({**_BASE, "cadence": "weekly"})


def test_window_label_monthly():
    assert "this month" in build_prompt_safe({**_BASE, "cadence": "monthly"})


def test_window_label_quarterly():
    assert "this quarter" in build_prompt_safe({**_BASE, "cadence": "quarterly"})


def test_strict_prompt_includes_change_summary():
    ctx = {**_BASE, "change_summary": "Portfolio changes since last review:\n[2026-04-03] Rebalance -- equity overweight."}
    assert "PORTFOLIO CHANGES SINCE LAST REVIEW" in build_strict_prompt(ctx)
