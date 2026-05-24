"""Unit tests for scripts/backfill_news.py pure helpers."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# Make the script importable.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backfill_news import parse_article  # noqa: E402
from scripts.backfill_news import dedupe_rows, filter_existing_dates  # noqa: E402


TODAY = date(2026, 5, 23)


def _article(published_at: str | None, title: str = "X", description: str = "Y") -> dict:
    return {
        "title": title,
        "description": description,
        "publishedAt": published_at,
        "source": {"name": "Reuters"},
    }


def test_parse_article_honors_publishedAt():
    art = _article("2026-05-10T08:30:00Z", title="Nifty hits record")
    row = parse_article(art, today=TODAY)
    assert row is not None
    assert row["date"] == "2026-05-10"
    assert row["category"] == "newsapi"
    assert row["headline"] == "Nifty hits record"
    assert row["source"] == "Reuters"


def test_parse_article_drops_missing_publishedAt():
    art = _article(None)
    assert parse_article(art, today=TODAY) is None


def test_parse_article_drops_out_of_window():
    old = (TODAY - timedelta(days=45)).isoformat() + "T00:00:00Z"
    art = _article(old)
    assert parse_article(art, today=TODAY) is None


def test_parse_article_drops_missing_title():
    art = _article("2026-05-10T08:30:00Z", title="")
    assert parse_article(art, today=TODAY) is None


def test_parse_article_truncates_long_fields():
    long_title = "x" * 600
    long_desc = "y" * 3000
    art = _article("2026-05-10T08:30:00Z", title=long_title, description=long_desc)
    row = parse_article(art, today=TODAY)
    assert row is not None
    assert len(row["headline"]) <= 500
    assert len(row["summary"]) <= 2000


def _row(date_str: str, headline: str) -> dict:
    return {
        "date": date_str,
        "category": "newsapi",
        "headline": headline,
        "summary": "",
        "source": "Reuters",
    }


def test_dedupe_by_date_and_headline():
    rows = [
        _row("2026-05-10", "Nifty hits record"),
        _row("2026-05-10", "Nifty hits record"),  # exact dup
        _row("2026-05-10", "RBI holds rates"),    # same date, diff headline
        _row("2026-05-11", "Nifty hits record"),  # same headline, diff date
    ]
    out = dedupe_rows(rows)
    assert len(out) == 3


def test_dedupe_preserves_first_occurrence():
    rows = [
        {"date": "2026-05-10", "headline": "A", "source": "first"},
        {"date": "2026-05-10", "headline": "A", "source": "second"},
    ]
    out = dedupe_rows(rows)
    assert out[0]["source"] == "first"


def test_filter_existing_dates_drops_known():
    rows = [
        _row("2026-05-10", "A"),
        _row("2026-05-11", "B"),
        _row("2026-05-12", "C"),
    ]
    existing = {"2026-05-11"}
    out = filter_existing_dates(rows, existing)
    assert len(out) == 2
    assert {r["date"] for r in out} == {"2026-05-10", "2026-05-12"}


def test_filter_existing_dates_empty_existing_keeps_all():
    rows = [_row("2026-05-10", "A"), _row("2026-05-11", "B")]
    out = filter_existing_dates(rows, set())
    assert len(out) == 2
