"""Backfill 30 days of daily_news + 4 weekly_summaries from NewsAPI.

One-off CLI. Safe to re-run (idempotent on existing dates/weeks).

Usage:
    python scripts/backfill_news.py            # full run
    python scripts/backfill_news.py --dry-run  # fetch, print, no DB writes
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Allow `from backend.db import news_db` style imports when running from repo root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402
import requests  # noqa: E402
from db import news_db  # noqa: E402
from services import summariser  # noqa: E402

# Load backend/.env so SUPABASE_*, COHERE_*, NEWSAPI_KEY are available.
load_dotenv(BACKEND_DIR / ".env")


REQUIRED_ENV = ("NEWSAPI_KEY", "COHERE_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY")

# Mirrors backend/config/feeds.json at time of writing. Acceptable drift since
# backfill is a one-off tool — if feeds.json changes meaningfully later, edit
# this list and re-run.
NEWSAPI_QUERIES = ("Indian stock market", "Nifty 50", "RBI monetary policy")

LOOKBACK_DAYS = 30
WEEKS_TO_SUMMARISE = 4


def parse_article(article: dict, today: date) -> dict | None:
    """Convert a NewsAPI article dict into a daily_news row.

    Returns None for articles that should be dropped:
    - missing or unparseable publishedAt
    - publishedAt older than LOOKBACK_DAYS
    - missing title
    """
    published_at = article.get("publishedAt")
    if not published_at:
        return None
    try:
        # NewsAPI returns ISO 8601 like "2026-05-10T08:30:00Z".
        parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

    article_date = parsed.date()
    if (today - article_date).days > LOOKBACK_DAYS:
        return None
    if article_date > today:
        return None

    title = (article.get("title") or "").strip()
    if not title:
        return None

    description = (article.get("description") or "").strip()
    source_name = ((article.get("source") or {}).get("name") or "NewsAPI").strip()

    return {
        "date": article_date.isoformat(),
        "category": "newsapi",
        "headline": title[:500],
        "summary": description[:2000],
        "source": source_name,
    }


def dedupe_rows(rows: list[dict]) -> list[dict]:
    """Drop rows with duplicate (date, headline) tuples. Preserves first occurrence."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for r in rows:
        key = (r.get("date", ""), r.get("headline", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def filter_existing_dates(rows: list[dict], existing_dates: set[str]) -> list[dict]:
    """Return only rows whose date is NOT in existing_dates."""
    return [r for r in rows if r.get("date") not in existing_dates]


NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWSAPI_PAGE_SIZE = 100
REQUEST_TIMEOUT = 30  # seconds


def fetch_newsapi_range(query: str, from_date: date, to_date: date, api_key: str) -> list[dict]:
    """Fetch articles for a single query across a date range.

    Returns the raw `articles` list from NewsAPI. On HTTP error or non-200
    response, logs to stderr and returns an empty list (never raises).
    """
    params = {
        "q": query,
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "pageSize": NEWSAPI_PAGE_SIZE,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": api_key,
    }
    try:
        res = requests.get(NEWSAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        payload = res.json()
    except requests.RequestException as exc:
        print(f"  WARN: NewsAPI request failed for {query!r}: {exc}", file=sys.stderr)
        return []
    except ValueError as exc:
        print(f"  WARN: NewsAPI JSON decode failed for {query!r}: {exc}", file=sys.stderr)
        return []

    if payload.get("status") != "ok":
        print(
            f"  WARN: NewsAPI returned non-ok status for {query!r}: "
            f"{payload.get('code')} {payload.get('message')}",
            file=sys.stderr,
        )
        return []

    return payload.get("articles") or []


async def backfill_daily_news(today: date, dry_run: bool) -> int:
    """Phase 1: fetch from NewsAPI, dedupe, skip existing dates, insert.

    Returns the number of rows inserted (or that would be inserted in dry-run).
    """
    api_key = os.getenv("NEWSAPI_KEY", "")
    from_date = today - timedelta(days=LOOKBACK_DAYS)

    all_rows: list[dict] = []
    for i, query in enumerate(NEWSAPI_QUERIES, start=1):
        print(f"[1/2] Fetching NewsAPI for {query!r} ({i}/{len(NEWSAPI_QUERIES)})...")
        articles = fetch_newsapi_range(query, from_date, today, api_key)
        parsed = [parse_article(a, today=today) for a in articles]
        kept = [r for r in parsed if r is not None]
        print(f"       {len(articles)} articles, {len(kept)} kept after filter")
        all_rows.extend(kept)

    deduped = dedupe_rows(all_rows)
    print(f"[1/2] Deduped {len(all_rows)} -> {len(deduped)} unique rows")

    existing_rows = await news_db.get_daily_news_since(from_date.isoformat())
    existing_dates = {r["date"] for r in existing_rows if r.get("date")}
    new_rows = filter_existing_dates(deduped, existing_dates)
    print(
        f"[1/2] {len(existing_dates)} dates already populated; "
        f"{len(new_rows)} rows to insert"
    )

    if dry_run:
        print("[1/2] DRY-RUN: skipping insert. Sample rows:")
        for r in new_rows[:3]:
            print(f"       {r['date']} | {r['source']} | {r['headline'][:80]}")
        return len(new_rows)

    inserted = await news_db.save_daily_news(new_rows)
    print(f"[1/2] Inserted {inserted} rows into daily_news")
    return inserted


async def backfill_weekly_summaries(today: date, dry_run: bool) -> int:
    """Phase 2: generate weekly summaries for the last WEEKS_TO_SUMMARISE weeks.

    Skips weeks that already have a row in weekly_summaries. Returns the number
    of weekly_summaries rows inserted (or that would be inserted in dry-run).
    """
    if dry_run:
        print("[2/2] DRY-RUN: skipping weekly summary generation")
        return 0

    client = summariser._cohere_client()
    if client is None:
        print("[2/2] WARN: no COHERE_API_KEY, skipping weekly summaries", file=sys.stderr)
        return 0

    # Fetch existing summary week_starts once.
    existing_summaries = await news_db.get_recent_weekly_summaries(weeks=20)
    existing_week_starts = {
        s["week_start"] for s in existing_summaries if s.get("week_start")
    }

    inserted_count = 0
    for week_offset in range(WEEKS_TO_SUMMARISE):
        week_end = today - timedelta(days=week_offset * 7)
        week_start = week_end - timedelta(days=7)
        week_start_iso = week_start.isoformat()
        week_end_iso = week_end.isoformat()
        label = f"[2/2] Week {week_start_iso} to {week_end_iso}"

        if week_start_iso in existing_week_starts:
            print(f"{label}: already exists, skipping")
            continue

        # Fetch rows in [week_start, week_end] inclusive.
        rows = await news_db.get_daily_news_since(week_start_iso)
        rows = [r for r in rows if r.get("date") and r["date"] <= week_end_iso]
        if not rows:
            print(f"{label}: no headlines, skipping summary")
            continue

        grouped = summariser._group_by_category(rows)
        summaries: dict[str, str] = {}
        for category, items in grouped.items():
            text = await summariser._summarise_category(client, category, items)
            if text:
                summaries[category] = text

        if not summaries:
            print(f"{label}: all categories failed Cohere call, skipping insert")
            continue

        try:
            summary_id = await news_db.save_weekly_summary(
                week_start=week_start_iso,
                week_end=week_end_iso,
                summaries=summaries,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{label}: ERROR saving summary: {exc}", file=sys.stderr)
            continue

        print(
            f"{label}: {len(summaries)} category(s), {len(rows)} headlines, "
            f"saved id={summary_id}"
        )
        inserted_count += 1

    return inserted_count


def check_env() -> None:
    """Hard-fail with a clear message if any required env var is missing."""
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}", file=sys.stderr)
        print(f"Set them in {BACKEND_DIR / '.env'} and re-run.", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill daily_news + weekly_summaries")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch from NewsAPI and print rows; skip all DB writes and Cohere calls.",
    )
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    check_env()
    today = date.today()
    print(f"Backfill starting (today={today.isoformat()}, dry_run={args.dry_run})")

    daily_inserted = await backfill_daily_news(today, args.dry_run)
    weekly_inserted = await backfill_weekly_summaries(today, args.dry_run)

    print(
        f"Done. {daily_inserted} daily_news rows, "
        f"{weekly_inserted} weekly_summaries rows."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
