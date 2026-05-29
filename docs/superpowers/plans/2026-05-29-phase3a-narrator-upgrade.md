# Phase 3A — AI Narrator Upgrade + Multi-Cadence Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject a plain-text change summary (rationale events + drift) into the Cohere prompt so the letter explains *why* the portfolio changed, and add weekly/quarterly cadences alongside the existing monthly report.

**Architecture:** A new `build_change_summary(sb, client_id, window_days)` helper queries `rationale_events` and `wealth_snapshots` and renders a ≤500-char string added to the context packet under `"change_summary"`. The prompt builder injects this block when non-empty. A `cadence` field flows from request → context → report row. Quarterly cron reuses the existing `generate_report_batch` pattern.

**Tech Stack:** Python 3.11, FastAPI, Supabase postgrest-py v2, Pydantic v2, React 18, Tailwind CSS. Tests run from `backend/` with `pytest` — imports use `from db.*` / `from services.*` (no `backend.` prefix).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/db_schema/migrations/004_cadence_column.sql` | Create | ALTER TABLE reports ADD cadence + index |
| `backend/services/context_builder.py` | Modify | Add `build_change_summary()` + private helpers; add `cadence` param to `build_context_packet` |
| `backend/services/prompt_builder.py` | Modify | Add change_summary block + cadence window label |
| `backend/models/report.py` | Modify | Add `cadence: Literal` field to `GenerateReportRequest` |
| `backend/routes/reports.py` | Modify | Pass `cadence` to context builder and report generator |
| `backend/routes/jobs.py` | Modify | Add `POST /jobs/quarterly-reports` + `_current_quarter()` |
| `backend/tests/test_context_builder.py` | Create | 4 tests for `build_change_summary` |
| `backend/tests/test_prompt_builder.py` | Create | 6 tests for change_summary block + window label |
| `backend/tests/test_jobs_quarterly.py` | Create | 3 tests for quarterly-reports endpoint |
| `frontend/src/pages/ClientDetail.jsx` | Modify | Cadence dropdown + conditional month picker |
| `frontend/src/components/report/PastReportsList.jsx` | Modify | W/Q badge next to each report |

---

## Task 1: Migration — add `cadence` column to `reports`

**Files:**
- Create: `backend/db_schema/migrations/004_cadence_column.sql`

- [ ] **Step 1: Write the migration SQL file**

Save `backend/db_schema/migrations/004_cadence_column.sql`:

```sql
-- 004_cadence_column.sql
ALTER TABLE reports
  ADD COLUMN cadence text NOT NULL DEFAULT 'monthly'
    CHECK (cadence IN ('weekly', 'monthly', 'quarterly'));

CREATE INDEX reports_cadence_created_idx
  ON reports(cadence, created_at DESC);
```

- [ ] **Step 2: Apply via Supabase MCP**

Use `mcp__claude_ai_Supabase__apply_migration`:
- project_id: `qkydgmingqpiqzxcuqpn`
- name: `004_cadence_column`
- query: the SQL above

Expected: `{"success": true}`

- [ ] **Step 3: Verify the column exists**

Use `mcp__claude_ai_Supabase__execute_sql`:

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'reports' AND column_name = 'cadence';
```

Expected: one row — `data_type = text`, `column_default = 'monthly'`

- [ ] **Step 4: Commit**

```bash
git add backend/db_schema/migrations/004_cadence_column.sql
git commit -m "feat(db): migration 004 — add cadence column to reports"
```

---

## Task 2: `build_change_summary()` in context_builder

**Files:**
- Modify: `backend/services/context_builder.py`
- Create: `backend/tests/test_context_builder.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_context_builder.py`:

```python
from __future__ import annotations
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from services import context_builder
from services.context_builder import build_change_summary

_TODAY = date.today()
_WINDOW = 30

def _sb():
    return MagicMock()

def _make_event(title, rationale, days_ago=5):
    return {"event_date": str(_TODAY - timedelta(days=days_ago)),
            "title": title, "rationale_text": rationale}

def _make_snapshot():
    return {"allocation_pct": {"equity": "0.55", "debt": "0.25",
            "gold": "0.08", "cash": "0.10", "alternatives": "0.02"}}

def _make_target():
    return {"equity_pct": "45", "debt_pct": "35", "gold_pct": "8",
            "cash_pct": "10", "alternatives_pct": "2",
            "equity_band_pct": "5", "debt_band_pct": "5",
            "gold_band_pct": "2", "cash_band_pct": "3",
            "alternatives_band_pct": "3"}

def test_returns_empty_string_when_no_events():
    with patch.object(context_builder, "_fetch_events_in_window", return_value=[]), \
         patch.object(context_builder, "_fetch_latest_snapshot", return_value=None), \
         patch.object(context_builder, "_fetch_active_target", return_value=None):
        assert build_change_summary(_sb(), "c1", _WINDOW) == ""

def test_renders_event_title_and_rationale():
    events = [_make_event("Gold target raised", "Inflation hedge strategy")]
    with patch.object(context_builder, "_fetch_events_in_window", return_value=events), \
         patch.object(context_builder, "_fetch_latest_snapshot", return_value=None), \
         patch.object(context_builder, "_fetch_active_target", return_value=None):
        result = build_change_summary(_sb(), "c1", _WINDOW)
    assert "Gold target raised" in result
    assert "Inflation hedge strategy" in result
    assert "Portfolio changes since last review" in result

def test_caps_total_at_500_chars():
    events = [_make_event(f"Event {i}", "X" * 300) for i in range(10)]
    with patch.object(context_builder, "_fetch_events_in_window", return_value=events), \
         patch.object(context_builder, "_fetch_latest_snapshot", return_value=None), \
         patch.object(context_builder, "_fetch_active_target", return_value=None):
        result = build_change_summary(_sb(), "c1", _WINDOW)
    assert len(result) <= 500
    assert "more event" in result

def test_drift_line_shows_over():
    events = [_make_event("Rebalance", "Equity was overweight")]
    with patch.object(context_builder, "_fetch_events_in_window", return_value=events), \
         patch.object(context_builder, "_fetch_latest_snapshot", return_value=_make_snapshot()), \
         patch.object(context_builder, "_fetch_active_target", return_value=_make_target()):
        result = build_change_summary(_sb(), "c1", _WINDOW)
    assert "equity" in result.lower()
    assert "over" in result.lower()
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_context_builder.py -v 2>&1 | tail -15
```

Expected: 4 failures — `AttributeError: module has no attribute '_fetch_events_in_window'`

- [ ] **Step 3: Add helpers and `build_change_summary` to `context_builder.py`**

Insert after `_extract_rationale_trades` and before `async def build_context_packet`:

```python
# ─── Phase 3A: change-summary ─────────────────────────────────────────────────

_CHANGE_SUMMARY_CAP = 500
_RATIONALE_INLINE_CAP = 120
_CADENCE_WINDOW: dict[str, int] = {"weekly": 7, "monthly": 30, "quarterly": 90}


def _fetch_events_in_window(sb, client_id: str, window_days: int) -> list[dict]:
    from datetime import date, timedelta
    from_date = str(date.today() - timedelta(days=window_days))
    res = (
        sb.table("rationale_events")
        .select("event_date,title,rationale_text")
        .eq("client_id", str(client_id))
        .gte("event_date", from_date)
        .order("event_date", desc=False)
        .execute()
    )
    return res.data or []


def _fetch_latest_snapshot(sb, client_id: str) -> dict | None:
    res = (
        sb.table("wealth_snapshots")
        .select("allocation_pct")
        .eq("client_id", str(client_id))
        .order("as_of", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def _fetch_active_target(sb, client_id: str) -> dict | None:
    res = (
        sb.table("allocation_targets")
        .select(
            "equity_pct,debt_pct,gold_pct,cash_pct,alternatives_pct,"
            "equity_band_pct,debt_band_pct,gold_band_pct,"
            "cash_band_pct,alternatives_band_pct"
        )
        .eq("client_id", str(client_id))
        .is_("effective_to", "null")
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def _build_drift_line(snapshot: dict, target: dict) -> str:
    allocation = snapshot.get("allocation_pct") or {}
    parts: list[str] = []
    for cls in ("equity", "debt", "gold", "cash", "alternatives"):
        try:
            actual_pct = float(allocation.get(cls, 0)) * 100  # 0..1 -> 0..100
            target_pct = float(target.get(f"{cls}_pct", 0))
            band_pct = float(target.get(f"{cls}_band_pct", 5))
        except (ValueError, TypeError):
            continue
        delta = actual_pct - target_pct
        if delta > band_pct:
            parts.append(f"{cls} +{delta:.0f}% over target")
        elif delta < -band_pct:
            parts.append(f"{cls} {delta:.0f}% under target")
        else:
            parts.append(f"{cls} on track")
    return ("Current allocation: " + ", ".join(parts) + ".") if parts else ""


def build_change_summary(sb, client_id: str, window_days: int) -> str:
    """Return <=500-char plain-text change summary. Returns '' if no events."""
    events = _fetch_events_in_window(sb, client_id, window_days)
    if not events:
        return ""
    snapshot = _fetch_latest_snapshot(sb, client_id)
    target = _fetch_active_target(sb, client_id)
    lines: list[str] = ["Portfolio changes since last review:"]
    skipped = 0
    for ev in events:
        ev_date = str(ev.get("event_date", ""))[:10]
        title = (ev.get("title") or "").strip()
        rat = (ev.get("rationale_text") or "").strip()
        if len(rat) > _RATIONALE_INLINE_CAP:
            rat = rat[:_RATIONALE_INLINE_CAP].rstrip() + "..."
        candidate = f"[{ev_date}] {title} -- {rat}"
        used = sum(len(line) + 1 for line in lines)
        if used + len(candidate) + 80 > _CHANGE_SUMMARY_CAP:
            skipped = len(events) - (len(lines) - 1)
            break
        lines.append(candidate)
    if skipped:
        lines.append(f"...and {skipped} more event{'s' if skipped > 1 else ''}.")
    if snapshot and target:
        drift = _build_drift_line(snapshot, target)
        if drift:
            lines.append(drift)
    return "\n".join(lines)[:_CHANGE_SUMMARY_CAP]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_context_builder.py -v 2>&1 | tail -15
```

Expected: 4 PASSED

- [ ] **Step 5: Add `cadence` param to `build_context_packet`**

Replace the signature:

```python
async def build_context_packet(
    client_id: str,
    month: str,
) -> dict[str, Any]:
```

With:

```python
async def build_context_packet(
    client_id: str,
    month: str,
    cadence: str = "monthly",
) -> dict[str, Any]:
```

After `rationale_trades = _extract_rationale_trades(transactions)`, add:

```python
    window_days = _CADENCE_WINDOW.get(cadence, 30)
    try:
        from db.supabase_client import get_supabase as _get_sb
        change_summary = build_change_summary(_get_sb(), client_id, window_days)
    except Exception:  # noqa: BLE001
        change_summary = ""
```

In the `packet` dict, after `"rationale_trades": rationale_trades,` add:

```python
        "change_summary": change_summary,
        "cadence": cadence,
```

- [ ] **Step 6: Run suite to confirm nothing broke**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_context_builder.py tests/test_snapshot_service.py tests/test_drift_service.py -v 2>&1 | tail -15
```

Expected: all PASSED

- [ ] **Step 7: Commit**

```bash
git add backend/services/context_builder.py backend/tests/test_context_builder.py
git commit -m "feat(context): add build_change_summary + cadence param to build_context_packet"
```

---

## Task 3: Prompt changes — change_summary block + cadence window label

**Files:**
- Modify: `backend/services/prompt_builder.py`
- Create: `backend/tests/test_prompt_builder.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_prompt_builder.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_prompt_builder.py -v 2>&1 | tail -15
```

Expected: failures on change_summary and window-label assertions

- [ ] **Step 3: Modify `prompt_builder.py`**

Add after the `BANNED_PHRASES` list:

```python
_CADENCE_WINDOW_LABEL: dict[str, str] = {
    "weekly": "this week",
    "monthly": "this month",
    "quarterly": "this quarter",
}


def _change_summary_block(context: dict[str, Any]) -> str | None:
    summary = (context.get("change_summary") or "").strip()
    return ("PORTFOLIO CHANGES SINCE LAST REVIEW:\n" + summary) if summary else None
```

Modify `_task_block` — replace function definition line and opening of `base`:

Old:
```python
def _task_block(strict: bool, note: str = "") -> str:
    base = (
        "Write the letter for the client described in the CONTEXT PACKET "
        "above. Follow the 7-section LETTER STRUCTURE.\n\n"
```

New:
```python
def _task_block(strict: bool, note: str = "", cadence: str = "monthly") -> str:
    window_label = _CADENCE_WINDOW_LABEL.get(cadence, "this month")
    base = (
        "Write the letter for the client described in the CONTEXT PACKET "
        f"above. The letter covers {window_label}. Follow the 7-section LETTER STRUCTURE.\n\n"
```

After the `rationale_trades` rule inside `_task_block`, add:

```python
        "- If `change_summary` is present in the context packet, naturally "
        "incorporate the key portfolio changes into the letter — weave into "
        "the narrative, do not copy verbatim.\n"
```

Replace `build_prompt_safe`:

```python
def build_prompt_safe(context: dict[str, Any], strict: bool = False) -> str:
    cadence = context.get("cadence", "monthly")
    blocks = [
        "[SYSTEM]", _system_block(),
        "[BANNED PHRASES — never use any of these, even reworded]", _banned_phrases_block(),
        "[LETTER STRUCTURE]", LETTER_STRUCTURE,
        "[EXAMPLE LETTERS]", _examples_block(include_style_samples=True),
        "[CONTEXT PACKET]", _serialise_context(context),
    ]
    cb = _change_summary_block(context)
    if cb:
        blocks += ["[PORTFOLIO CHANGES SINCE LAST REVIEW]", cb]
    blocks += ["[TASK]", _task_block(strict=strict, cadence=cadence)]
    return "\n\n".join(blocks)
```

Replace `build_strict_prompt`:

```python
def build_strict_prompt(context: dict[str, Any], note: str = "") -> str:
    cadence = context.get("cadence", "monthly")
    blocks = [
        "[SYSTEM]", _system_block(),
        "[BANNED PHRASES — never use any of these, even reworded]", _banned_phrases_block(),
        "[LETTER STRUCTURE]", LETTER_STRUCTURE,
        "[EXAMPLE LETTERS]", _examples_block(include_style_samples=False),
        "[CONTEXT PACKET]", _serialise_context(context),
    ]
    cb = _change_summary_block(context)
    if cb:
        blocks += ["[PORTFOLIO CHANGES SINCE LAST REVIEW]", cb]
    blocks += ["[TASK]", _task_block(strict=True, note=note, cadence=cadence)]
    return "\n\n".join(blocks)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_prompt_builder.py -v 2>&1 | tail -15
```

Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/services/prompt_builder.py backend/tests/test_prompt_builder.py
git commit -m "feat(prompt): inject change_summary block and cadence window label"
```

---

## Task 4: Backend routes — thread `cadence` from request to report row

**Files:**
- Modify: `backend/models/report.py`
- Modify: `backend/routes/reports.py`
- Modify: `backend/services/report_generator.py`

- [ ] **Step 1: Add `cadence` to `GenerateReportRequest`**

Replace the entire `backend/models/report.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class GenerateReportRequest(BaseModel):
    client_id: str
    month: str = Field(..., description='Month identifier, e.g. "2026-04"')
    cadence: Literal["weekly", "monthly", "quarterly"] = "monthly"


class ReportResponse(BaseModel):
    id: str
    client_id: str
    month: str
    qa_score: int | None = None
    has_hindi: bool = False
    created_at: datetime


class ReportSummary(BaseModel):
    id: str
    month: str
    qa_score: int | None = None
    created_at: datetime
```

- [ ] **Step 2: Pass `cadence` in `routes/reports.py`**

In `generate_report`, replace:

```python
    try:
        context = await build_context_packet(request.client_id, request.month)
    except ValueError as exc:
```

With:

```python
    try:
        context = await build_context_packet(
            request.client_id, request.month, cadence=request.cadence
        )
    except ValueError as exc:
```

Replace the `_body` inner function:

```python
    async def _body():
        async for chunk in report_generator.generate_report_stream(
            client_id=request.client_id,
            month=request.month,
            context=context,
            cadence=request.cadence,
        ):
            yield chunk
```

- [ ] **Step 3: Add `cadence` param to `report_generator.py`**

Run to find the relevant functions:

```bash
cd backend && grep -n "def generate_report_stream\|def generate_report_batch\|\"month\":" services/report_generator.py | head -20
```

For each of `generate_report_stream` and `generate_report_batch`:
1. Add `cadence: str = "monthly"` to the function signature
2. Find the dict passed to the reports_db save/insert call (look for `"client_id"` and `"month"` keys)
3. Add `"cadence": cadence` to that dict

- [ ] **Step 4: Verify OpenAPI schema shows cadence**

```bash
pkill -f "uvicorn main:app" 2>/dev/null; sleep 1
cd backend && source ../venv/bin/activate && uvicorn main:app --port 8000 &
sleep 3
curl -s http://localhost:8000/openapi.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
props = d['components']['schemas']['GenerateReportRequest']['properties']
print(json.dumps(props.get('cadence', 'NOT FOUND'), indent=2))
"
```

Expected: `{"enum": ["weekly", "monthly", "quarterly"], ...}`

- [ ] **Step 5: Commit**

```bash
git add backend/models/report.py backend/routes/reports.py backend/services/report_generator.py
git commit -m "feat(reports): thread cadence param from request through context builder to report row"
```

---

## Task 5: Quarterly cron endpoint

**Files:**
- Modify: `backend/routes/jobs.py`
- Create: `backend/tests/test_jobs_quarterly.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_jobs_quarterly.py`:

```python
from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
import routes.jobs as jobs_module


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_quarterly_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setenv("JOB_SECRET", "real-secret")
    assert client.post("/jobs/quarterly-reports?secret=wrong").status_code == 403


def test_quarterly_iterates_all_clients(client, monkeypatch):
    monkeypatch.setenv("JOB_SECRET", "test-secret")
    fake_clients = [{"id": "c1"}, {"id": "c2"}]

    async def _fake_ctx(cid, quarter, cadence="monthly"):
        return {"client": {"id": cid, "name": "X"},
                "holdings": [{"ticker": "T", "current_price": 1}]}

    with patch.object(jobs_module, "list_all_clients", return_value=fake_clients), \
         patch("routes.jobs.build_context_packet", side_effect=_fake_ctx), \
         patch("routes.jobs.report_generator") as mock_gen, \
         patch("routes.jobs.log_error", new_callable=AsyncMock), \
         patch("routes.jobs.log_job_run", new_callable=AsyncMock):
        mock_gen.generate_report_batch = AsyncMock(return_value={"status": "ok"})
        resp = client.post("/jobs/quarterly-reports?secret=test-secret")

    assert resp.status_code == 200
    body = resp.json()
    assert body["clients_total"] == 2
    assert body["ok"] == 2
    assert body["failed"] == 0


def test_quarterly_tolerates_per_client_failure(client, monkeypatch):
    monkeypatch.setenv("JOB_SECRET", "test-secret")
    fake_clients = [{"id": "c1"}, {"id": "c2"}]

    async def _fail_c1(cid, quarter, cadence="monthly"):
        if cid == "c1":
            raise RuntimeError("context build failed")
        return {"client": {"id": cid, "name": "X"},
                "holdings": [{"ticker": "T", "current_price": 1}]}

    with patch.object(jobs_module, "list_all_clients", return_value=fake_clients), \
         patch("routes.jobs.build_context_packet", side_effect=_fail_c1), \
         patch("routes.jobs.report_generator") as mock_gen, \
         patch("routes.jobs.log_error", new_callable=AsyncMock), \
         patch("routes.jobs.log_job_run", new_callable=AsyncMock):
        mock_gen.generate_report_batch = AsyncMock(return_value={"status": "ok"})
        resp = client.post("/jobs/quarterly-reports?secret=test-secret")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] == 1
    assert body["failed"] == 1
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_jobs_quarterly.py -v 2>&1 | tail -15
```

Expected: failures — `404 Not Found` on `/jobs/quarterly-reports`

- [ ] **Step 3: Add endpoint to `routes/jobs.py`**

At the very end of `backend/routes/jobs.py`, append:

```python

# ─── Phase 3A: quarterly reports cron ─────────────────────────────────────────
# EasyCron schedule:
#   URL:      https://<host>/jobs/quarterly-reports?secret=$JOB_SECRET
#   Cron:     30 6 1 1,4,7,10 *
#   Timezone: Asia/Kolkata
#   Retries:  3

from services.context_builder import build_context_packet
from services import report_generator as report_generator  # noqa: F811


def _current_quarter() -> str:
    now = datetime.now(timezone.utc)
    q = (now.month - 1) // 3 + 1
    return f"Q{q} {now.year}"


@router.post("/quarterly-reports")
async def quarterly_reports(secret: str = Query(...)):
    """Iterate every client and generate a quarterly report (window=90 days)."""
    _verify_job_secret(secret)
    from db.supabase_client import get_supabase
    sb = get_supabase()
    clients = list_all_clients(sb)
    ok = 0
    failed = 0
    target_quarter = _current_quarter()
    for c in clients:
        cid = c["id"]
        try:
            ctx = await build_context_packet(cid, target_quarter, cadence="quarterly")
            res = await report_generator.generate_report_batch(
                client_id=cid, month=target_quarter,
                context=ctx, cadence="quarterly",
            )
            if res.get("status") == "ok":
                ok += 1
            else:
                failed += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            await log_error("quarterly_reports.client", exc, {"client_id": cid})
    summary = {"clients_total": len(clients), "ok": ok, "failed": failed}
    await log_job_run(job_name="quarterly-reports",
                      status="ok" if failed == 0 else "partial", records=ok)
    return summary
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_jobs_quarterly.py -v 2>&1 | tail -15
```

Expected: 3 PASSED

- [ ] **Step 5: Run the full backend suite**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_*.py -q 2>&1 | tail -10
```

Expected: all PASSED (60+ tests)

- [ ] **Step 6: Commit**

```bash
git add backend/routes/jobs.py backend/tests/test_jobs_quarterly.py
git commit -m "feat(jobs): add quarterly-reports cron endpoint (cadence=quarterly, window=90d)"
```

---

## Task 6: Frontend — cadence selector + report list badge

**Files:**
- Modify: `frontend/src/pages/ClientDetail.jsx`
- Modify: `frontend/src/components/report/PastReportsList.jsx`

- [ ] **Step 1: Add cadence state + selector to `ClientDetail.jsx`**

Find `const [month, setMonth] = useState(defaultMonth())` and add after it:

```javascript
const [cadence, setCadence] = useState('monthly')
```

Replace the existing `newReportHref` useMemo:

```javascript
const newReportHref = useMemo(() => {
  if (cadence === 'weekly') {
    return `/clients/${id}/report/new?cadence=weekly`
  }
  if (cadence === 'quarterly') {
    const now = new Date()
    const q = Math.floor(now.getMonth() / 3) + 1
    const quarter = `Q${q} ${now.getFullYear()}`
    return `/clients/${id}/report/new?cadence=quarterly&month=${encodeURIComponent(quarter)}`
  }
  return `/clients/${id}/report/new?cadence=monthly&month=${month}`
}, [id, cadence, month])
```

Just above the month-picker input, add:

```jsx
<div className="flex items-center gap-2 mt-4">
  <label className="text-sm font-medium text-slate-700">Report type:</label>
  <select
    value={cadence}
    onChange={(e) => setCadence(e.target.value)}
    className="text-sm border border-slate-200 rounded px-2 py-1 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500"
  >
    <option value="weekly">Weekly digest</option>
    <option value="monthly">Monthly letter</option>
    <option value="quarterly">Quarterly review</option>
  </select>
</div>
```

Wrap the existing month `<input>` to hide it when weekly is selected:

```jsx
{cadence !== 'weekly' && (
  /* existing month picker JSX — paste unchanged here */
)}
```

- [ ] **Step 2: Add cadence badge to `PastReportsList.jsx`**

Inside `reports.map`, after the `<Link>` element and before `<QAScoreBadge>`:

```jsx
{r.cadence && r.cadence !== 'monthly' && (
  <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
    r.cadence === 'weekly' ? 'bg-sky-100 text-sky-700' : 'bg-purple-100 text-purple-700'
  }`}>
    {r.cadence === 'weekly' ? 'W' : 'Q'}
  </span>
)}
```

- [ ] **Step 3: Verify frontend builds cleanly**

```bash
cd /Users/guruts/Desktop/Portfolionarator/frontend && npm run build 2>&1 | tail -10
```

Expected: build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ClientDetail.jsx frontend/src/components/report/PastReportsList.jsx
git commit -m "feat(frontend): cadence selector (weekly/monthly/quarterly) + W/Q badge in report list"
```

---

## Task 7: Final integration check

- [ ] **Step 1: Run the full backend suite**

```bash
cd backend && source ../venv/bin/activate && python -m pytest tests/test_*.py -q 2>&1 | tail -10
```

Expected: all PASSED, 0 failures

- [ ] **Step 2: Confirm `cadence` in OpenAPI schema**

```bash
curl -s http://localhost:8000/openapi.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(json.dumps(d['components']['schemas']['GenerateReportRequest']['properties']['cadence'], indent=2))
"
```

Expected: `{"enum": ["weekly", "monthly", "quarterly"], ...}`

- [ ] **Step 3: Confirm migration in Supabase**

Use `mcp__claude_ai_Supabase__list_migrations` (project_id: `qkydgmingqpiqzxcuqpn`).
Expected: `004_cadence_column` in the list.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(phase3a): AI narrator upgrade + multi-cadence reports complete

- build_change_summary() injects rationale events + drift into Cohere prompt
- cadence (weekly/monthly/quarterly) flows request -> context -> report row
- quarterly-reports cron endpoint added
- frontend cadence selector + W/Q badge in report list
- migration 004_cadence_column applied to Supabase
- 13 new tests, all passing

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
