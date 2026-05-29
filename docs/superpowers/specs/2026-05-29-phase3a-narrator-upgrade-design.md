# Phase 3A — AI Narrator Upgrade + Multi-Cadence Reports

**Status:** Approved for implementation
**Date:** 2026-05-29
**Depends on:** Phase 2 (`2026-05-27-phase2-change-tracking-design.md`)

---

## 1. Purpose

Phase 2 built the change-tracking model (rationale events, wealth snapshots, allocation targets) but the Cohere report narrator does not read any of it yet. Phase 3A closes that gap and adds weekly and quarterly cadences alongside the existing monthly report.

**Lead outcomes:**
- Monthly letters explain *why* the portfolio changed, not just what it holds
- RMs can generate a quick weekly digest or a deep quarterly review from the same UI
- Monthly and quarterly generation are automated via EasyCron; weekly is manual

---

## 2. Design Decisions

| # | Question | Decision |
|---|----------|----------|
| Q1 | Where does "what changed" appear in the letter? | Cohere places it naturally — no rigid section |
| Q2 | What Phase 2 data enters the prompt? | Pre-computed summary string (lean on tokens) |
| Q3 | "Since last time" window | Since last rationale event, bounded by cadence window |
| Q4 | Content difference by cadence | Same template, `window_days` changes (7 / 30 / 90) |
| Q5 | Report triggering | Weekly: manual. Monthly + quarterly: EasyCron cron jobs |
| Q6 | Scope | Narrator upgrade + multi-cadence in one phase |

---

## 3. Architecture

```
Triggers
  Manual:    GET /clients/{id}/report/new?cadence=weekly|monthly|quarterly
  Cron:      POST /jobs/monthly-reports   (1st of month)
             POST /jobs/quarterly-reports (1st of Jan/Apr/Jul/Oct)
                        |
                        v
context_builder.build_context_packet()
  NEW: build_change_summary(client_id, window_days)
    -> queries rationale_events in window
    -> appends drift line from latest wealth_snapshot
    -> renders plain-text string (<=500 chars)
    -> returns "" if no events (block skipped)

  context["change_summary"] = str
  context["cadence"]        = "weekly"|"monthly"|"quarterly"
  context["window_days"]    = 7 | 30 | 90
                        |
                        v
prompt_builder.build_prompt_safe()
  NEW: change_summary block injected if non-empty
  NEW: window label varies by cadence
       weekly    -> "this week"
       monthly   -> "this month" (existing)
       quarterly -> "this quarter"
                        |
                        v
           Cohere Command R+ (unchanged)
```

---

## 4. `build_change_summary()` Specification

**Location:** `backend/services/context_builder.py`

**Signature:**
```python
def build_change_summary(sb, client_id: str, window_days: int) -> str
```

**Logic:**
1. Query `rationale_events` where `event_date >= now() - window_days` for `client_id`, ordered by `event_date ASC`
2. Query the latest `wealth_snapshot` for the drift line (actual vs target per class)
3. Render as plain text:

```
Portfolio changes since last review:
[YYYY-MM-DD] <title> -- <rationale_text truncated to 120 chars>
Current allocation: equity +3% over target, debt on track, gold on track.
```

4. Hard cap at **500 characters total** — truncate with `"...and N more events."` if needed
5. Return `""` if no events in window — the prompt block is skipped entirely

**Drift line format:**
- Classes where `|actual - target| > band`: shown with direction (over/under)
- Classes within band: shown as "on track"
- Omitted entirely if no snapshot exists

---

## 5. Schema Changes

### 5.1 `reports` table — add `cadence`

Migration file: `backend/db_schema/migrations/004_cadence_column.sql`

```sql
ALTER TABLE reports
  ADD COLUMN cadence text NOT NULL DEFAULT 'monthly'
    CHECK (cadence IN ('weekly', 'monthly', 'quarterly'));

CREATE INDEX reports_cadence_created_idx
  ON reports(cadence, created_at DESC);
```

### 5.2 Cadence window mapping

| Cadence   | window_days | Automated? | Cron (IST)               |
|-----------|-------------|------------|--------------------------|
| weekly    | 7           | No         | Manual only              |
| monthly   | 30          | Yes        | `30 6 1 * *` (existing)  |
| quarterly | 90          | Yes        | `30 6 1 1,4,7,10 *` (new)|

---

## 6. Prompt Changes

**File:** `backend/services/prompt_builder.py`

Add one new block after the transactions section:

```
{% if change_summary %}
PORTFOLIO CHANGES SINCE LAST REVIEW:
{{ change_summary }}
{% endif %}
```

Cadence-aware window label — current hardcoded "this month" becomes dynamic:
- weekly    -> "this week"
- monthly   -> "this month"
- quarterly -> "this quarter"

No other prompt changes. Cohere decides where the change narrative fits.

---

## 7. Backend Route Changes

### 7.1 Existing report generate endpoint

`POST /reports/generate-stream` gains optional `cadence` param (default: `monthly`).
`GET /clients/{id}/report/new` passes `cadence` as query param.

### 7.2 New cron endpoint

```
POST /jobs/quarterly-reports?secret=...
```

- Iterates all clients (same pattern as `generate-monthly`)
- Passes `cadence="quarterly"`, `window_days=90`
- EasyCron schedule: `30 6 1 1,4,7,10 *` Asia/Kolkata, 3 retries
- Error handling: per-client try/except, partial success returned

---

## 8. Frontend Changes

**File:** `frontend/src/pages/ClientDetail.jsx`

1. **Cadence selector** — dropdown above the existing month picker:
   - Weekly: no month picker shown, generates for current 7-day window
   - Monthly: existing month picker (default, unchanged)
   - Quarterly: quarter picker (Q1 2026, Q2 2026...)

2. **Report list badge** — `PastReportsList` shows W / M / Q badge next to each report

3. **Report page title** adapts:
   - Weekly:    "Weekly Digest — 26 May 2026"
   - Monthly:   "Monthly Letter — April 2026" (existing)
   - Quarterly: "Quarterly Review — Q1 2026"

---

## 9. Testing

| Test | File | What it verifies |
|------|------|-----------------|
| `test_build_change_summary_no_events` | `tests/test_context_builder.py` | Returns `""` when no events in window |
| `test_build_change_summary_with_events` | `tests/test_context_builder.py` | Renders correct plain-text string |
| `test_build_change_summary_cap` | `tests/test_context_builder.py` | Hard caps at 500 chars with "...and N more" |
| `test_build_change_summary_drift_line` | `tests/test_context_builder.py` | Drift line shows over/under/on-track correctly |
| `test_prompt_includes_change_summary` | `tests/test_prompt_builder.py` | Block appears when summary non-empty |
| `test_prompt_skips_change_summary` | `tests/test_prompt_builder.py` | Block absent when summary is `""` |
| `test_prompt_window_label_weekly` | `tests/test_prompt_builder.py` | "this week" label for weekly cadence |
| `test_quarterly_reports_job` | `tests/test_jobs.py` | Endpoint iterates all clients with cadence=quarterly |

All tests mock Supabase — no live calls.

---

## 10. Out of Scope (Deferred)

- Per-client cadence configuration
- Separate prompt templates per cadence
- Client-facing report delivery (Phase 3D)
- Backfill of historical rationale events for pre-Phase-2 reports
- Two-pass Cohere call for higher-quality change narrative
