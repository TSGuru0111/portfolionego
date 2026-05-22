"""Daily news + weekly summaries CRUD against Supabase.

Tables: ``daily_news``, ``weekly_summaries``.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from db.supabase_client import get_supabase


def _require_supabase():
    supabase = get_supabase()
    if supabase is None:
        raise RuntimeError(
            "Supabase client not configured. Set SUPABASE_URL + SUPABASE_SERVICE_KEY."
        )
    return supabase


async def save_daily_news(headlines: list[dict[str, Any]]) -> int:
    """Insert a batch of normalised headlines. Returns rows inserted."""
    if not headlines:
        return 0
    supabase = _require_supabase()
    today = date.today().isoformat()
    rows = [
        {
            "date": h.get("date") or today,
            "category": h.get("category") or "general",
            "headline": (h.get("headline") or "").strip()[:500],
            "summary": (h.get("summary") or "")[:2000],
            "source": h.get("source") or "rss",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        for h in headlines
        if h.get("headline")
    ]
    if not rows:
        return 0
    res = supabase.table("daily_news").insert(rows).execute()
    return len(res.data or [])


async def get_recent_weekly_summaries(weeks: int = 4) -> list[dict[str, Any]]:
    """Return the last ``weeks`` summaries, most recent first."""
    supabase = _require_supabase()
    res = (
        supabase.table("weekly_summaries")
        .select("id, week_start, week_end, summaries, created_at")
        .order("week_end", desc=True)
        .limit(weeks)
        .execute()
    )
    return res.data or []


async def save_weekly_summary(
    week_start: str,
    week_end: str,
    summaries: dict[str, str],
) -> str | None:
    """Insert one ``weekly_summaries`` row. Returns the new row id."""
    supabase = _require_supabase()
    res = (
        supabase.table("weekly_summaries")
        .insert(
            {
                "week_start": week_start,
                "week_end": week_end,
                "summaries": summaries,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .execute()
    )
    rows = res.data or []
    return rows[0].get("id") if rows else None
