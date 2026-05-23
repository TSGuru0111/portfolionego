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
    print(f"Backfill starting (dry_run={args.dry_run})")
    # Phase 1 + Phase 2 wired in later tasks.
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
