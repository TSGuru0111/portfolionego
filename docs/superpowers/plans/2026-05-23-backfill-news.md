# Backfill News Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-off CLI script that seeds 30 days of `daily_news` and 4 `weekly_summaries` from NewsAPI so the report generator works on Day 1.

**Architecture:** Single standalone script `scripts/backfill_news.py`. Zero edits to production code. Pure helper functions are factored out for unit testing. The script orchestrates: (1) fetch NewsAPI `/v2/everything` for 3 queries over the last 30 days, (2) parse honest `publishedAt` dates, (3) dedupe + skip existing dates, (4) batch-insert via existing `news_db.save_daily_news()`, (5) loop 4 weeks calling existing `summariser._summarise_category()` for Cohere weekly summaries.

**Tech Stack:** Python 3.11+, `requests`, `python-dotenv`, `cohere`, `supabase-py`. Reuses `backend/db/news_db.py` and `backend/services/summariser.py`.

**Spec reference:** `docs/superpowers/specs/2026-05-23-backfill-news-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `scripts/backfill_news.py` | Create | Main script. CLI entry point, pure parsing helpers, orchestration. |
| `backend/tests/test_backfill.py` | Create | Unit tests for the pure helpers in the script. |

**Boundaries:**
- Pure helpers (`parse_article`, `dedupe_rows`, `filter_existing_dates`) live in the same file as the orchestrator. They are pure functions, easily unit-tested via mocked inputs.
- The script's `main()` is async and uses `asyncio.run()` at the bottom.
- No new module is needed under `backend/` — backfill is leaf-level tooling.

---

## Task 1: Scaffolding — Script Skeleton, Env Loading, Path Wiring

**Files:**
- Create: `scripts/backfill_news.py`
- Create: `scripts/__init__.py` (empty, makes scripts a package)

- [ ] **Step 1: Create scripts/ directory and empty `__init__.py`**

```bash
mkdir -p scripts
touch scripts/__init__.py
```

- [ ] **Step 2: Create `scripts/backfill_news.py` with skeleton + env loading**

```python
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
```

- [ ] **Step 3: Smoke-test the skeleton**

Run: `python scripts/backfill_news.py --dry-run`
Expected: `Backfill starting (dry_run=True)` and exit 0. If env vars are missing, hard-fail with a clear message.

- [ ] **Step 4: Commit**

```bash
git add scripts/__init__.py scripts/backfill_news.py
git commit -m "Add backfill_news scaffolding with env loading and CLI args"
```

---

## Task 2: Article Parser (Pure Function + Tests)

**Files:**
- Modify: `scripts/backfill_news.py` (add `parse_article` function)
- Create: `backend/tests/test_backfill.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_backfill.py`:

```python
"""Unit tests for scripts/backfill_news.py pure helpers."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# Make the script importable.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backfill_news import parse_article  # noqa: E402


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_backfill.py -v`
Expected: ImportError or `parse_article` not defined — all tests FAIL.

- [ ] **Step 3: Implement `parse_article` in `scripts/backfill_news.py`**

Insert below `WEEKS_TO_SUMMARISE = 4` and above `def check_env()`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_backfill.py -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/backfill_news.py backend/tests/test_backfill.py
git commit -m "Add parse_article helper with unit tests"
```

---

## Task 3: Dedupe and Existing-Dates Filter (Pure Functions + Tests)

**Files:**
- Modify: `scripts/backfill_news.py` (add `dedupe_rows`, `filter_existing_dates`)
- Modify: `backend/tests/test_backfill.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_backfill.py`:

```python
from scripts.backfill_news import dedupe_rows, filter_existing_dates  # noqa: E402


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_backfill.py -v`
Expected: 4 new tests FAIL with ImportError on `dedupe_rows`/`filter_existing_dates`.

- [ ] **Step 3: Implement the helpers**

Insert below `parse_article` in `scripts/backfill_news.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_backfill.py -v`
Expected: 9 tests total PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/backfill_news.py backend/tests/test_backfill.py
git commit -m "Add dedupe_rows and filter_existing_dates with tests"
```

---

## Task 4: NewsAPI Historical Fetcher (with Real HTTP, Error-Tolerant)

**Files:**
- Modify: `scripts/backfill_news.py` (add `fetch_newsapi_range`)

This function makes real network calls; we don't unit-test it. It will be exercised by the dry-run verification step in Task 7.

- [ ] **Step 1: Add the import for requests and the fetcher**

At the top of `scripts/backfill_news.py`, add to the imports block (after `from dotenv import load_dotenv`):

```python
import requests  # noqa: E402
```

Insert below `filter_existing_dates`:

```python
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
```

- [ ] **Step 2: Quick syntax check (no test added — this hits the network)**

Run: `python -c "from scripts.backfill_news import fetch_newsapi_range; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill_news.py
git commit -m "Add fetch_newsapi_range with error-tolerant HTTP handling"
```

---

## Task 5: Phase 1 Orchestration — Daily News Backfill

**Files:**
- Modify: `scripts/backfill_news.py` (add `backfill_daily_news`)

- [ ] **Step 1: Add imports for the existing news_db helper**

At the top of `scripts/backfill_news.py`, add after the existing `import requests` line:

```python
from db import news_db  # noqa: E402
```

(Note: `sys.path` was already prepended with `BACKEND_DIR` in Task 1, so `from db import news_db` resolves to `backend/db/news_db.py`.)

- [ ] **Step 2: Add the orchestration function**

Insert below `fetch_newsapi_range`:

```python
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
```

- [ ] **Step 3: Wire it into `main()`**

Replace the body of `main()` with:

```python
async def main() -> int:
    args = parse_args()
    check_env()
    today = date.today()
    print(f"Backfill starting (today={today.isoformat()}, dry_run={args.dry_run})")

    await backfill_daily_news(today, args.dry_run)
    # Phase 2 wired in next task.
    print("Done.")
    return 0
```

- [ ] **Step 4: Verify import + syntax**

Run: `python -c "import scripts.backfill_news; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Run a dry-run end-to-end**

Run: `python scripts/backfill_news.py --dry-run`
Expected: prints fetch progress for each query, dedup count, existing-dates check, sample rows. Exits 0.

If NEWSAPI_KEY isn't set in `.env`, the script will hard-fail at startup. If it's set but invalid, you'll see WARN messages and `0 rows to insert`.

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_news.py
git commit -m "Add Phase 1 orchestration for daily_news backfill"
```

---

## Task 6: Phase 2 Orchestration — Weekly Summaries

**Files:**
- Modify: `scripts/backfill_news.py` (add `backfill_weekly_summaries`)

- [ ] **Step 1: Add import for the summariser helpers**

At the top of `scripts/backfill_news.py`, add after `from db import news_db`:

```python
from services import summariser  # noqa: E402
```

- [ ] **Step 2: Add the orchestration function**

Insert below `backfill_daily_news`:

```python
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
```

- [ ] **Step 3: Wire it into `main()`**

Update `main()` to call Phase 2 after Phase 1:

```python
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
```

- [ ] **Step 4: Verify import + syntax**

Run: `python -c "import scripts.backfill_news; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Run the full unit-test suite**

Run: `pytest backend/tests/test_backfill.py -v`
Expected: 9 tests PASS (no regressions from Task 3).

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_news.py
git commit -m "Add Phase 2 orchestration for weekly summaries backfill"
```

---

## Task 7: Manual Verification — Dry Run, Real Run, SQL Check

This task has no code changes — it's the operational verification the spec calls for. Run through it before declaring victory.

- [ ] **Step 1: Dry run**

Run: `python scripts/backfill_news.py --dry-run`

Expected output shape:
```
Backfill starting (today=2026-05-23, dry_run=True)
[1/2] Fetching NewsAPI for 'Indian stock market' (1/3)...
       <N> articles, <M> kept after filter
[1/2] Fetching NewsAPI for 'Nifty 50' (2/3)...
       ...
[1/2] Fetching NewsAPI for 'RBI monetary policy' (3/3)...
       ...
[1/2] Deduped <X> -> <Y> unique rows
[1/2] <0 or more> dates already populated; <Z> rows to insert
[1/2] DRY-RUN: skipping insert. Sample rows:
       2026-05-22 | Reuters | <headline>
       ...
[2/2] DRY-RUN: skipping weekly summary generation
Done. <Z> daily_news rows, 0 weekly_summaries rows.
```

Eyeball check:
- Sample row dates are real, spread across the last ~30 days
- Headlines look like real Indian-market content
- Total rows after dedup is roughly 100-300

If anything looks wrong (e.g., 0 rows), check `NEWSAPI_KEY` validity, re-run with verbose stderr captured.

- [ ] **Step 2: Real run**

Run: `python scripts/backfill_news.py`

Expected: same output but with real inserts. Final line should report inserted counts > 0 for both phases on a fresh DB.

- [ ] **Step 3: Post-run SQL verification**

In the Supabase SQL Editor, run:

```sql
-- Should return 20-30 distinct dates (depends on NewsAPI coverage).
SELECT COUNT(DISTINCT date) AS distinct_dates,
       COUNT(*) AS total_rows
FROM daily_news
WHERE date >= CURRENT_DATE - 30;
```

Expected: `distinct_dates` between 20 and 30; `total_rows` between 100 and 300.

```sql
-- Should return 4 rows.
SELECT week_start, week_end, jsonb_object_keys(summaries) AS category
FROM weekly_summaries
ORDER BY week_start DESC
LIMIT 20;
```

Expected: 4 distinct `(week_start, week_end)` pairs covering the last 4 weeks, each with at least one category (typically `newsapi`).

- [ ] **Step 4: Idempotency check**

Run: `python scripts/backfill_news.py` a second time.

Expected: `<N> dates already populated` is non-zero, `0 rows to insert` for Phase 1, and Phase 2 logs `already exists, skipping` for all 4 weeks. Final line: `Done. 0 daily_news rows, 0 weekly_summaries rows.`

- [ ] **Step 5: Functional smoke**

Trigger one report generation in the frontend UI. Section 4 ("Market Context") should now contain specific weekly market language rather than empty / generic boilerplate.

- [ ] **Step 6: No commit needed** — verification only.

---

## Self-Review Notes

Spec coverage check:
- ✅ 30 days daily_news + 4 weekly_summaries — Tasks 5 + 6
- ✅ CLI script `python scripts/backfill_news.py` — Task 1
- ✅ Skip existing dates (idempotent) — Tasks 3 + 5 + 6
- ✅ NewsAPI only, no RSS — Task 4 + 5 (only NEWSAPI_QUERIES consulted)
- ✅ Inline in backfill script, no `news_fetcher.py` edits — Tasks 1–6 all live in `scripts/backfill_news.py`
- ✅ Honest publishedAt dates — Task 2 (`parse_article`)
- ✅ Dedupe by (date, headline) — Task 3
- ✅ Error handling per spec table — Tasks 4 + 6 (per-query, per-week try/except)
- ✅ Unit tests for pure helpers — Tasks 2 + 3 (5 + 4 tests)
- ✅ Dry-run flag — Task 1 + 5 + 6
- ✅ Post-run SQL verification — Task 7

Type/signature consistency check:
- `parse_article(article, today)` defined Task 2, called in Task 5 ✓
- `dedupe_rows(rows)` defined Task 3, called in Task 5 ✓
- `filter_existing_dates(rows, existing)` defined Task 3, called in Task 5 ✓
- `fetch_newsapi_range(query, from_date, to_date, api_key)` defined Task 4, called in Task 5 ✓
- `summariser._cohere_client()` — verified in `backend/services/summariser.py:29`
- `summariser._group_by_category(rows)` — verified at line 106
- `summariser._summarise_category(client, category, items)` — verified at line 85 (note: takes client as first arg)
- `news_db.save_daily_news(rows)` — verified at line 22
- `news_db.get_daily_news_since(start_date_iso)` — verified at line 46
- `news_db.get_recent_weekly_summaries(weeks)` — verified at line 59
- `news_db.save_weekly_summary(week_start, week_end, summaries)` — verified at line 72

No placeholders. All code blocks are complete. All commands have expected output.
