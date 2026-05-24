# Backfill News Design

**Date:** 2026-05-23
**Status:** Approved (brainstorming complete)
**Owner:** Build sprint

## Problem

On Day 1 of the build, `daily_news` and `weekly_summaries` are empty. The report generator depends on the last 4 weekly summaries (`backend/services/context_builder.py:234`) and produces a weak Section 4 ("Market Context") without them. Waiting 7 days for the natural Sunday cron to populate `weekly_summaries` is not viable for development or demos.

## Goal

Seed 30 days of `daily_news` and 4 weeks of `weekly_summaries` in one manual run, using real NewsAPI data with honest `publishedAt` dates, so the report generator works fully on Day 1.

## Non-Goals

- Not a recurring or scheduled job — manual one-off tool
- Not a UI feature — CLI only
- No `job_runs` logging — stdout is enough
- No backfill of RSS feeds (no historical lookback available; would require fabricated dates)
- No automated re-fetch / retry — user re-runs if needed
- No backfill of holdings, clients, portfolios, or reports tables

## Approach

A single new Python script: `scripts/backfill_news.py`. Standalone CLI. Zero edits to production code. Reuses existing persistence and summarisation helpers.

## Architecture

### File Layout

```
Portfolionarator/
├── scripts/                              # new
│   └── backfill_news.py                  # new (~200 lines)
└── backend/
    ├── services/
    │   ├── news_fetcher.py               # untouched
    │   └── summariser.py                 # imported, not modified
    └── db/
        └── news_db.py                    # imported, not modified
```

### Boundaries

- **Depends on:** `backend/db/news_db.py` (for `save_daily_news`, `save_weekly_summary`, `get_daily_news_since`), `backend/services/summariser.py` (for `_group_by_category`, `_summarise_category`), `python-dotenv`, `requests`, `cohere`, `supabase`.
- **Depended on by:** Nothing. Script is a leaf node. Can be deleted post-demo with zero impact.
- **Env loading:** Loads `backend/.env` via `python-dotenv`. Requires `NEWSAPI_KEY`, `COHERE_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.

### Invocation

```bash
python scripts/backfill_news.py            # full run
python scripts/backfill_news.py --dry-run  # fetch from NewsAPI, print rows, no DB writes, no Cohere
```

Script prepends the project root to `sys.path` at startup so `backend.*` imports resolve.

## Data Flow

### Phase 1 — Daily News Backfill

```
# Hardcoded at top of script. Mirrors backend/config/feeds.json at time of
# writing. Acceptable drift since backfill is a one-off tool — if feeds.json
# changes meaningfully later, edit this list and re-run.
queries = ["Indian stock market", "Nifty 50", "RBI monetary policy"]

For each query:
  GET https://newsapi.org/v2/everything
    ?q=<query>
    &from=<today-30d>
    &to=<today>
    &pageSize=100
    &sortBy=publishedAt
    &language=en
    &apiKey=<NEWSAPI_KEY>
  For each article in response.articles:
    parsed_date = parse(article.publishedAt).date()
    if parsed_date is None: skip
    if (today - parsed_date).days > 30: skip
    row = {
      date: parsed_date,
      category: "newsapi",
      headline: article.title[:500],
      summary: article.description[:2000] or "",
      source: article.source.name or "NewsAPI",
    }
    accumulate

Dedupe accumulated rows by (date, headline) tuple.

existing_dates = SELECT DISTINCT date FROM daily_news WHERE date >= today - 30d
new_rows = [r for r in rows if r.date not in existing_dates]

await news_db.save_daily_news(new_rows)
```

### Phase 2 — Weekly Summaries

```
For week_offset in [0, 1, 2, 3]:
  week_end   = today - week_offset * 7 days
  week_start = week_end - 7 days

  if SELECT 1 FROM weekly_summaries WHERE week_start = <start> LIMIT 1: skip

  rows = await news_db.get_daily_news_since(week_start)
  rows = [r for r in rows if r.date <= week_end]   # bound the upper end

  if not rows: skip with log message

  buckets = summariser._group_by_category(rows)
  summaries = {}
  for category, items in buckets.items():
    summaries[category] = await summariser._summarise_category(category, items)

  await news_db.save_weekly_summary(week_start, week_end, summaries)
```

Mirrors `summariser.weekly_summarisation()` at `backend/services/summariser.py:132` — same Cohere model (`command-r`), same prompt template, same banned-phrase strip.

**Week window semantics:** Windows are `[week_start, week_end]` inclusive on both ends, matching the existing summariser. Consecutive weeks share their boundary day (e.g., 2026-05-16 appears in both the 5/9–5/16 and 5/16–5/23 windows). This is the existing production behavior — accepted as-is to avoid divergence. A headline on a boundary day will appear in two summaries; this is harmless context redundancy, not a bug.

**Categories from NewsAPI:** All NewsAPI rows use `category="newsapi"` (matching `news_fetcher.py:148`), so each backfilled week will have a single category bucket. This is consistent with what the production cron produces when only NewsAPI ran that week.

### Logging Format

```
[1/2] Fetching NewsAPI for "Indian stock market"... 87 articles
[1/2] Fetching NewsAPI for "Nifty 50"... 93 articles
[1/2] Fetching NewsAPI for "RBI monetary policy"... 41 articles
[1/2] Deduped to 198 unique rows
[1/2] Skipped 0 existing dates, inserting 198 rows... done
[2/2] Week 2026-05-16 to 2026-05-23: 1 category (newsapi), generating summary... done
[2/2] Week 2026-05-09 to 2026-05-16: 1 category (newsapi), generating summary... done
[2/2] Week 2026-05-02 to 2026-05-09: 1 category (newsapi), generating summary... done
[2/2] Week 2026-04-25 to 2026-05-02: 1 category (newsapi), generating summary... done
Done. 198 daily_news rows, 4 weekly_summaries rows.
```

## Error Handling

| Failure | Behavior |
|---|---|
| NewsAPI request fails for one query | Log to stderr, skip query, continue with others |
| NewsAPI rate limit hit | Treat as request failure (same path) |
| Missing required env var at startup | Hard-fail with clear message, exit 1 |
| Cohere call fails for a week | Log warning, skip that week's insert, continue with other weeks |
| Empty article list for a week | Skip Cohere call entirely, log `"no headlines, skipping summary"` |
| Article missing `publishedAt` | Drop that article (do NOT fall back to today) |
| Article `publishedAt` older than 30 days | Drop that article |
| Duplicate headline across queries | Dedupe by `(date, headline)` in-script before insert |
| Race with daily cron firing mid-backfill | Acceptable — worst case a few duplicate rows for today |

No retries. User re-runs the script; idempotency check picks up where it left off.

## Idempotency

Re-running the script is safe. Both phases check for existing data before writing:

- Daily news: skip dates already present in `daily_news`
- Weekly summaries: skip weeks already present in `weekly_summaries` (matched by `week_start`)

This means partial runs can be completed by re-running. No `--force` flag.

## Testing

### Layer 1 — Unit Tests

`backend/tests/test_backfill.py` — pure-function tests with NewsAPI and Cohere mocked. About 5 tests:

| Test | Assertion |
|---|---|
| `test_parse_article_honors_publishedAt` | Article dict → row with `date = publishedAt.date()`, not today |
| `test_parse_article_drops_missing_publishedAt` | Article with no `publishedAt` returns `None` |
| `test_parse_article_drops_out_of_window` | Article older than 30 days is filtered out |
| `test_dedupe_by_date_and_headline` | Same headline+date across two queries → one row |
| `test_skip_existing_dates_filter` | Given `existing_dates={d1, d2}`, only rows for other dates pass through |

Fast, no network, no Supabase.

### Layer 2 — Dry Run

`python scripts/backfill_news.py --dry-run` performs real NewsAPI fetches, runs all parsing and dedup logic, prints the row count and a sample to stdout, but performs zero DB writes and zero Cohere calls.

Manual eyeball check before running for real:
- Dates spread across 30 days?
- Headlines look like real Indian-market content?
- ~200+ rows after dedup?

### Layer 3 — Post-Run Verification

Two Supabase SQL Editor checks:

```sql
-- Expect 25-30 distinct dates
SELECT COUNT(DISTINCT date) FROM daily_news WHERE date >= CURRENT_DATE - 30;

-- Expect 4 rows, each with multiple categories
SELECT week_start, week_end, jsonb_object_keys(summaries) AS cat
FROM weekly_summaries
ORDER BY week_start DESC LIMIT 10;
```

Then trigger one report generation in the UI — Section 4 of the letter should contain specific weekly market context rather than "No news available."

### Out of Test Scope

- NewsAPI response-shape correctness (covered by their docs + dry-run)
- `news_db.save_daily_news()` / `summariser._summarise_category()` (production code, exercised by daily/weekly cron)
- Cohere output quality (covered by the QA-check layer in `report_generator.py:109`)

## Cost Estimate

- NewsAPI: 3 requests per run, well under the 100/day free-tier cap
- Cohere: ~12 `command-r` calls per run (4 weeks × ~3 categories), negligible cost
- Supabase: 1 batch insert + 4 single inserts per run

## Decisions Captured

| Decision | Choice |
|---|---|
| Scope | Full 30d daily_news + 4 weekly summaries |
| Invocation | CLI script `python scripts/backfill_news.py` |
| Re-run behavior | Skip existing dates (idempotent) |
| RSS handling | Skip in backfill, NewsAPI only |
| Code structure | Inline in backfill script, no edits to `news_fetcher.py` |
