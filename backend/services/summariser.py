"""Weekly news summarisation — Day 4.

Once a week (EasyCron → ``GET /jobs/weekly-summarise``) we condense the
previous 7 days of ``daily_news`` rows into a small dict keyed by
category, then persist to ``weekly_summaries``. The context_builder pulls
the latest 4 of these rows so every monthly letter has a rolling
"what's been happening" feed without paying for a full news scrape on
the report path.

Model: Cohere Command R (the cheaper sibling of Command R+).
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from typing import Any

import cohere

from db import news_db
from services.error_logger import log_error

SUMMARY_MODEL = "command-r"
MAX_HEADLINES_PER_CATEGORY = 30
MAX_OUTPUT_TOKENS = 350


def _cohere_client() -> cohere.Client | None:
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        return None
    return cohere.Client(api_key=api_key)


def _format_headlines(items: list[dict[str, Any]]) -> str:
    """Compact bullet list of ``headline — summary`` lines."""
    lines: list[str] = []
    for h in items[:MAX_HEADLINES_PER_CATEGORY]:
        headline = (h.get("headline") or "").strip()
        if not headline:
            continue
        summary = (h.get("summary") or "").strip()
        source = (h.get("source") or "").strip()
        line = f"- {headline}"
        if summary:
            line += f" — {summary[:240]}"
        if source:
            line += f" [{source}]"
        lines.append(line)
    return "\n".join(lines)


def _build_prompt(category: str, headlines_block: str) -> str:
    return (
        "You are a markets analyst writing a weekly news digest for an "
        "Indian wealth-management RM. Summarise the headlines below into a "
        "single tight paragraph (90–130 words) covering the key themes, "
        "named companies/sectors, and any policy or RBI signals. Use "
        "Indian English. Do NOT use phrases like 'market volatility', "
        "'headwinds', 'going forward', 'at this juncture'. No bullet "
        "points. No disclaimers.\n\n"
        f"Category: {category}\n\n"
        f"Headlines:\n{headlines_block}\n\n"
        "Weekly summary:"
    )


def _summarise_one_blocking(
    client: cohere.Client,
    category: str,
    headlines_block: str,
) -> str:
    """Synchronous Cohere chat call — runs in a thread."""
    resp = client.chat(
        model=SUMMARY_MODEL,
        message=_build_prompt(category, headlines_block),
        temperature=0.3,
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    text = (getattr(resp, "text", "") or "").strip()
    return text


async def _summarise_category(
    client: cohere.Client,
    category: str,
    items: list[dict[str, Any]],
) -> str | None:
    headlines_block = _format_headlines(items)
    if not headlines_block:
        return None
    try:
        return await asyncio.to_thread(
            _summarise_one_blocking, client, category, headlines_block
        )
    except Exception as exc:  # noqa: BLE001
        await log_error(
            "weekly_summarisation",
            exc,
            {"category": category, "items": len(items)},
        )
        return None


def _group_by_category(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        cat = (r.get("category") or "general").strip().lower()
        out.setdefault(cat, []).append(r)
    return out


async def weekly_summarisation() -> dict[str, Any]:
    """Summarise the last 7 days of ``daily_news`` and persist.

    Returns
    -------
    dict with::

        status:        "ok" | "empty" | "no_api_key"
        week_start:    YYYY-MM-DD
        week_end:      YYYY-MM-DD
        categories:    int            # how many we successfully summarised
        rows_used:     int            # daily_news rows that fed the summary
        summary_id:    str | None     # weekly_summaries row id
    """
    today = date.today()
    week_start = (today - timedelta(days=7)).isoformat()
    week_end = today.isoformat()

    rows = await news_db.get_daily_news_since(week_start)
    if not rows:
        return {
            "status": "empty",
            "week_start": week_start,
            "week_end": week_end,
            "categories": 0,
            "rows_used": 0,
            "summary_id": None,
        }

    client = _cohere_client()
    if client is None:
        return {
            "status": "no_api_key",
            "week_start": week_start,
            "week_end": week_end,
            "categories": 0,
            "rows_used": len(rows),
            "summary_id": None,
        }

    grouped = _group_by_category(rows)
    tasks = {
        cat: _summarise_category(client, cat, items)
        for cat, items in grouped.items()
    }
    results = await asyncio.gather(*tasks.values())
    summaries: dict[str, str] = {
        cat: text
        for cat, text in zip(tasks.keys(), results)
        if text
    }

    summary_id = None
    if summaries:
        summary_id = await news_db.save_weekly_summary(
            week_start=week_start,
            week_end=week_end,
            summaries=summaries,
        )

    return {
        "status": "ok",
        "week_start": week_start,
        "week_end": week_end,
        "categories": len(summaries),
        "rows_used": len(rows),
        "summary_id": summary_id,
    }
