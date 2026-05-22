"""Context-packet builder — Day 4.

Assembles everything the LLM needs to write one client's monthly letter:

  * client profile + RM contact info
  * portfolio holdings with **live** prices (yfinance → cached fallback)
  * portfolio return, alpha vs Nifty, top performers, underperformers
  * Nifty 1-month return + macro (USD/INR, crude)
  * portfolio-aware news (by sector + by ticker + RSS context)
  * last 4 weekly news summaries
  * recent transactions with RM rationale
  * cheap token estimate; trims the news bundle if the packet would
    overflow Cohere Command R+'s ~128k context window.

The output dict is consumed by ``services.prompt_builder.build_prompt_safe``
on Day 5 and ``services.report_generator.generate_report`` on Day 6.
"""
from __future__ import annotations

import json
import re
from typing import Any

_TAG_RE = re.compile(r"<[^>]+>")
_MEETING_NOTES_CAP = 500
_RATIONALE_CAP = 400


def _strip_tags(text: str) -> str:
    """Remove any HTML tags from free-form text fields before prompt use."""
    if not text:
        return ""
    return _TAG_RE.sub("", str(text))


def _sanitise_client(client: dict[str, Any]) -> dict[str, Any]:
    """Strip HTML and cap free-form fields that get serialised into prompts."""
    out = dict(client)
    notes = (client.get("last_meeting_notes") or "").strip()
    if notes:
        notes = _strip_tags(notes)
        if len(notes) > _MEETING_NOTES_CAP:
            notes = notes[:_MEETING_NOTES_CAP].rstrip() + "…"
        out["last_meeting_notes"] = notes
    return out


def _sanitise_transactions(
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for t in transactions:
        row = dict(t)
        r = (row.get("rationale") or "").strip()
        if r:
            r = _strip_tags(r)
            if len(r) > _RATIONALE_CAP:
                r = r[:_RATIONALE_CAP].rstrip() + "…"
            row["rationale"] = r
        cleaned.append(row)
    return cleaned

from db import clients_db, news_db
from services.market_data import (
    compute_portfolio_return,
    enrich_holdings_with_prices,
    fetch_macro_data,
    fetch_nifty_return,
    get_top_performers,
    get_underperformers,
)
from services.news_fetcher import fetch_client_relevant_news

# Cohere Command R+ has a 128k context window. We cap the packet at 90k
# tokens to leave room for the prompt scaffold + few-shot letters +
# completion tokens. Below this we keep everything; above, we shed news.
MAX_CONTEXT_TOKENS = 90_000
TRANSACTION_LOOKBACK = 20
RATIONALE_TRADES = 3


def estimate_tokens(text: str) -> int:
    """Cheap heuristic — ~4 chars per token, no tokeniser dependency.

    Good enough to decide whether to shed news context before paying for
    a real Cohere call.
    """
    return max(1, len(text) // 4)


def _serialise(packet: dict[str, Any]) -> str:
    return json.dumps(packet, default=str, ensure_ascii=False)


def validate_context(packet: dict[str, Any]) -> None:
    """Raise ``ValueError`` if the packet is missing data we cannot
    sensibly generate a letter without.
    """
    client = packet.get("client")
    if not client or not client.get("id"):
        raise ValueError("context.client missing or has no id")
    if not client.get("name"):
        raise ValueError("context.client.name is required")

    holdings = packet.get("holdings") or []
    if not isinstance(holdings, list) or not holdings:
        raise ValueError("context.holdings is empty — cannot write a letter")

    # At least one holding must have a real price; otherwise the letter
    # would be 100 % "data unavailable" boilerplate.
    priced = [h for h in holdings if h.get("current_price") is not None]
    if not priced:
        raise ValueError(
            "All holdings are price-unavailable — refusing to build context"
        )


def _trim_news_bundle(news: dict[str, Any], keep_per_bucket: int) -> dict[str, Any]:
    """Truncate every sector / ticker list to ``keep_per_bucket`` items."""
    out: dict[str, Any] = dict(news)
    by_sector = news.get("by_sector") or {}
    by_ticker = news.get("by_ticker") or {}
    out["by_sector"] = {k: (v or [])[:keep_per_bucket] for k, v in by_sector.items()}
    out["by_ticker"] = {k: (v or [])[:keep_per_bucket] for k, v in by_ticker.items()}
    rss_context = news.get("rss_context") or []
    out["rss_context"] = rss_context[: keep_per_bucket * 2]
    return out


def _fit_to_budget(packet: dict[str, Any]) -> tuple[dict[str, Any], int, bool]:
    """Shed news progressively until ``estimate_tokens`` fits the budget.

    Returns ``(packet, final_token_count, trimmed)``.
    """
    tokens = estimate_tokens(_serialise(packet))
    if tokens <= MAX_CONTEXT_TOKENS:
        return packet, tokens, False

    trimmed = dict(packet)
    for keep in (3, 2, 1):
        trimmed["news"] = _trim_news_bundle(packet.get("news") or {}, keep)
        tokens = estimate_tokens(_serialise(trimmed))
        if tokens <= MAX_CONTEXT_TOKENS:
            return trimmed, tokens, True

    # Last resort — drop weekly summaries too.
    trimmed["weekly_summaries"] = []
    tokens = estimate_tokens(_serialise(trimmed))
    return trimmed, tokens, True


def _extract_rationale_trades(
    transactions: list[dict[str, Any]],
    limit: int = RATIONALE_TRADES,
) -> list[dict[str, Any]]:
    """Pick the most recent trades that carry an RM-written rationale."""
    picked: list[dict[str, Any]] = []
    for t in transactions:
        if (t.get("rationale") or "").strip():
            picked.append(t)
        if len(picked) >= limit:
            break
    return picked


async def build_context_packet(
    client_id: str,
    month: str,
) -> dict[str, Any]:
    """Assemble the full context packet for one client/month.

    Parameters
    ----------
    client_id:
        UUID-string primary key of the ``clients`` row.
    month:
        Reporting month as ``YYYY-MM``. Used by downstream prompt builders
        to phrase the letter ("for the month of October 2025").

    Returns
    -------
    dict with the following top-level keys::

        client                — profile + RM contact (joined)
        portfolio             — raw portfolio row (benchmark, xirr, fees, …)
        holdings              — enriched with current_price / change_pct / source
        portfolio_return      — market-value-weighted % vs buy_price
        nifty_return          — 1-month Nifty 50 return %
        alpha                 — portfolio_return − nifty_return
        top_performers        — list[holding]  (≤ 3, sorted desc by return_pct)
        underperformers       — list[holding]  (≤ 3, sorted asc by return_pct)
        macro                 — usdinr_change_pct, crude_change_pct
        news                  — by_sector / by_ticker / rss_context / sectors / tickers
        weekly_summaries      — last 4 weekly_summaries rows
        transactions          — last 20 transactions
        rationale_trades      — last 3 trades with RM-written rationale
        has_stale_prices      — bool
        stale_tickers         — list[str]
        month                 — echoed back for downstream prompts
        meta                  — { token_estimate, trimmed }

    Raises
    ------
    ValueError
        If the client has no holdings or every holding's price is unavailable.
    RuntimeError
        If Supabase is unconfigured (propagated from ``db`` layer).
    """
    client = await clients_db.get_client(client_id)
    if not client:
        raise ValueError(f"Client {client_id!r} not found")

    portfolio_row = await clients_db.get_portfolio(client_id) or {}
    raw_holdings = portfolio_row.get("holdings") or []

    enriched_holdings, stale = await enrich_holdings_with_prices(raw_holdings)

    portfolio_return = compute_portfolio_return(enriched_holdings)
    nifty_return = await fetch_nifty_return("1mo")
    macro = await fetch_macro_data()

    alpha: float | None = None
    if portfolio_return is not None and nifty_return is not None:
        alpha = portfolio_return - nifty_return

    top = get_top_performers(enriched_holdings, n=3)
    bottom = get_underperformers(enriched_holdings, n=3)

    news_bundle = await fetch_client_relevant_news(
        client_id,
        {"holdings": enriched_holdings},
    )

    weekly_summaries = await news_db.get_recent_weekly_summaries(weeks=4)
    transactions = await clients_db.get_transactions(
        client_id, limit=TRANSACTION_LOOKBACK
    )
    transactions = _sanitise_transactions(transactions)
    rationale_trades = _extract_rationale_trades(transactions)

    packet: dict[str, Any] = {
        "client": _sanitise_client(client),
        "portfolio": {k: v for k, v in portfolio_row.items() if k != "holdings"},
        "holdings": enriched_holdings,
        "portfolio_return": portfolio_return,
        "nifty_return": nifty_return,
        "alpha": alpha,
        "top_performers": top,
        "underperformers": bottom,
        "macro": macro,
        "news": news_bundle,
        "weekly_summaries": weekly_summaries,
        "transactions": transactions,
        "rationale_trades": rationale_trades,
        "has_stale_prices": bool(stale),
        "stale_tickers": stale,
        "month": month,
    }

    validate_context(packet)

    packet, tokens, trimmed = _fit_to_budget(packet)
    packet["meta"] = {"token_estimate": tokens, "trimmed": trimmed}
    return packet
