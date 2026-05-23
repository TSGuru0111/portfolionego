# Report Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw-text streaming `ReportPage` and stub-chart `ClientDetail` with a unified React dashboard featuring shared chart components, inline letter editing, and a streaming UX that renders a full skeleton dashboard immediately.

**Architecture:** Single backend `build_report_data()` helper feeds both the existing HTML route and a new `/reports/{id}/data` JSON endpoint. Frontend ports the report into native React components under `frontend/src/components/report/`. Letter editing uses paragraph-level `contentEditable` and a `PATCH /reports/{id}` endpoint. Streaming chunk handling rewritten to fix duplication bug.

**Tech Stack:** FastAPI · Supabase Postgres · React 18 + Vite · recharts ^2.12.7 · Jinja2 (existing HTML renderer unchanged at the consumer level)

**DB column name:** the existing column is `generated_text` (not `letter_text`). All backend code uses `generated_text`. The spec's "letter_text" refers to this column.

---

## Task 1: Backend — DB helper `update_report_text`

**Files:**
- Modify: `backend/db/reports_db.py` (add new function after `update_report_hindi` at line 89)
- Test: `backend/tests/test_reports_db.py` (create)

- [ ] **Step 1: Check if a tests directory exists**

Run: `ls backend/tests/ 2>/dev/null || echo "no tests dir"`
If missing, create it: `mkdir -p backend/tests && touch backend/tests/__init__.py`

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_reports_db.py`:
```python
"""Tests for reports_db.update_report_text."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from db import reports_db


@pytest.mark.asyncio
async def test_update_report_text_returns_true_on_success():
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "abc", "generated_text": "new text"}
    ]
    with patch("db.reports_db.get_supabase", return_value=fake_supabase):
        result = await reports_db.update_report_text("abc", "new text")
    assert result is True
    fake_supabase.table.assert_called_with("reports")


@pytest.mark.asyncio
async def test_update_report_text_returns_false_when_no_row_updated():
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    with patch("db.reports_db.get_supabase", return_value=fake_supabase):
        result = await reports_db.update_report_text("missing", "x")
    assert result is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_reports_db.py -v`
Expected: FAIL with `AttributeError: module 'db.reports_db' has no attribute 'update_report_text'` or `ImportError`.

- [ ] **Step 4: Add the function to `backend/db/reports_db.py`**

Append at end of file (after `update_report_hindi`):
```python
async def update_report_text(report_id: str, generated_text: str) -> bool:
    """Patch the ``generated_text`` column for one report.

    Returns True if a row was updated, False otherwise.
    """
    supabase = _require_supabase()
    res = (
        supabase.table("reports")
        .update({"generated_text": generated_text})
        .eq("id", report_id)
        .execute()
    )
    return bool(res.data)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_reports_db.py -v`
Expected: PASS on both tests.

- [ ] **Step 6: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add backend/db/reports_db.py backend/tests/test_reports_db.py backend/tests/__init__.py
git commit -m "feat(reports_db): add update_report_text helper"
```

---

## Task 2: Backend — `PATCH /reports/{id}` endpoint

**Files:**
- Modify: `backend/routes/reports.py` (append new route at end of file, after line 118)
- Test: `backend/tests/test_reports_routes.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_reports_routes.py`:
```python
"""Tests for PATCH /reports/{id}."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_patch_report_updates_text():
    fake_row = {"id": "abc", "client_id": "c1", "month": "2026-04",
                "generated_text": "old", "qa_score": 8}
    updated_row = {**fake_row, "generated_text": "edited body"}
    with patch("routes.reports.reports_db.get_report",
               new=AsyncMock(side_effect=[fake_row, updated_row])), \
         patch("routes.reports.reports_db.update_report_text",
               new=AsyncMock(return_value=True)):
        res = client.patch("/reports/abc",
                           json={"generated_text": "edited body"})
    assert res.status_code == 200
    assert res.json()["generated_text"] == "edited body"


def test_patch_report_returns_404_when_missing():
    with patch("routes.reports.reports_db.get_report",
               new=AsyncMock(return_value=None)):
        res = client.patch("/reports/missing",
                           json={"generated_text": "x"})
    assert res.status_code == 404


def test_patch_report_returns_422_on_empty_text():
    res = client.patch("/reports/abc", json={"generated_text": ""})
    assert res.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_reports_routes.py -v`
Expected: FAIL — endpoint returns 405 (Method Not Allowed).

- [ ] **Step 3: Add a Pydantic body model**

In `backend/routes/reports.py`, add this import and model after the existing imports (after line 15):
```python
from pydantic import BaseModel, Field


class UpdateReportBody(BaseModel):
    generated_text: str = Field(..., min_length=1)
```

- [ ] **Step 4: Add the PATCH route**

Append to `backend/routes/reports.py` (after line 118):
```python
@router.patch("/{report_id}")
async def patch_report(report_id: str, body: UpdateReportBody) -> dict:
    """Update only the ``generated_text`` column of one report.

    The RM can edit the letter inline; KPIs and charts stay locked.
    """
    try:
        row = await reports_db.get_report(report_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    ok = await reports_db.update_report_text(report_id, body.generated_text)
    if not ok:
        raise HTTPException(status_code=500, detail="Update failed")

    updated = await reports_db.get_report(report_id)
    return updated or row
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_reports_routes.py -v`
Expected: all three tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add backend/routes/reports.py backend/tests/test_reports_routes.py
git commit -m "feat(reports): PATCH /reports/{id} for RM letter edits"
```

---

## Task 3: Backend — extract `build_report_data()` helper

**Files:**
- Modify: `backend/services/html_renderer.py` (refactor — extract data shaping from rendering)
- Test: `backend/tests/test_html_renderer_data.py` (create)

- [ ] **Step 1: Read the current renderer to understand existing structure**

Run: `wc -l backend/services/html_renderer.py`
Expected: file is ~380 lines after the Task #16 `_next_steps` rewrite.

Locate the function that builds the Jinja context dict (search for the call to `template.render(...)` or `env.get_template(...).render(...)`).

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_html_renderer_data.py`:
```python
"""Tests for build_report_data."""
from __future__ import annotations

from services import html_renderer


def test_build_report_data_returns_expected_keys():
    packet = {
        "client": {"id": "c1", "name": "Test Client",
                   "currency": "INR", "liquidity_need_pct": 10,
                   "income_need_monthly": 0, "tax_bracket": "30",
                   "language": "english"},
        "portfolio": {"holdings": [], "aum_cr": 1.0,
                      "inception_date": "2024-01-01"},
        "holdings": [{"ticker": "TCS", "sector": "IT",
                      "qty": 100, "current_price": 3000,
                      "month_return_pct": 5.0}],
        "month": "2026-04",
        "market": {"nifty_mtd_pct": -2.7, "usd_inr_mtd_pct": 1.0,
                   "crude_mtd_pct": 0.0},
        "letter_text": "Dear Test,\n\nSample body.",
        "qa_score": 8,
        "report_id": "abc",
        "has_stale_prices": False,
    }
    data = html_renderer.build_report_data(packet)
    expected_keys = {
        "report_id", "client_name", "month", "currency", "qa_score",
        "kpis", "holdings", "top_contributors", "top_detractors",
        "sector_allocation", "nav_series", "market_context",
        "next_steps", "letter_text",
    }
    assert expected_keys.issubset(set(data.keys()))
    assert data["client_name"] == "Test Client"
    assert data["letter_text"] == "Dear Test,\n\nSample body."
    assert isinstance(data["next_steps"], list)
    assert len(data["next_steps"]) <= 3
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_html_renderer_data.py -v`
Expected: FAIL — `AttributeError: module 'services.html_renderer' has no attribute 'build_report_data'`.

- [ ] **Step 4: Refactor `html_renderer.py` — extract `build_report_data()`**

Open `backend/services/html_renderer.py`. Find the function that currently builds the dict passed to Jinja (it lives inside `render_report_card()` or a sibling like `_build_context()`). Extract that dict-building logic into a new module-level function:

```python
def build_report_data(packet: dict) -> dict:
    """Shape the report packet into the JSON dict consumed by both the
    Jinja HTML template and the /reports/{id}/data JSON endpoint.

    Single source of truth for KPIs, sector allocation, top movers,
    market context, next-steps cards, and the letter text.
    """
    client = packet.get("client") or {}
    portfolio = packet.get("portfolio") or {}
    holdings = packet.get("holdings") or []
    market = packet.get("market") or {}

    kpis = {
        "portfolio_value_cr": _portfolio_value_cr(holdings),
        "holdings_count": len(holdings),
        "return_mtd_pct": _portfolio_return_pct(holdings),
        "nifty_mtd_pct": _safe_float(market.get("nifty_mtd_pct")),
    }
    kpis["alpha_pct"] = (
        kpis["return_mtd_pct"] - kpis["nifty_mtd_pct"]
        if kpis["return_mtd_pct"] is not None and kpis["nifty_mtd_pct"] is not None
        else None
    )

    sector_alloc = _allocation_by_sector(holdings)
    sector_allocation = [
        {"sector": s, "weight_pct": round(w, 2)}
        for s, w in sorted(sector_alloc.items(), key=lambda kv: -kv[1])
    ]

    movers_sorted = sorted(
        holdings,
        key=lambda h: _safe_float(h.get("month_return_pct")) or 0,
        reverse=True,
    )
    top_contributors = movers_sorted[:3]
    top_detractors = list(reversed(movers_sorted[-3:]))

    return {
        "report_id": packet.get("report_id"),
        "client_name": client.get("name"),
        "month": packet.get("month"),
        "currency": client.get("currency", "INR"),
        "qa_score": packet.get("qa_score"),
        "kpis": kpis,
        "holdings": holdings,
        "top_contributors": top_contributors,
        "top_detractors": top_detractors,
        "sector_allocation": sector_allocation,
        "nav_series": packet.get("nav_series"),  # None until backfilled
        "market_context": _market_context(market, packet),
        "next_steps": _next_steps(packet),
        "letter_text": packet.get("letter_text") or packet.get("generated_text", ""),
    }
```

If helpers like `_portfolio_value_cr`, `_portfolio_return_pct`, `_allocation_by_sector`, `_market_context`, `_safe_float`, `_next_steps` don't all already exist with these names, locate the existing equivalent and use that name in the function above instead.

Then change the existing `render_report_card()` (or whichever function renders Jinja) so it calls `build_report_data(packet)` and passes the resulting dict into the template under the same keys the template already expects. The HTML output must be identical to before this task.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_html_renderer_data.py -v`
Expected: PASS.

- [ ] **Step 6: Verify HTML still renders identically**

Run:
```bash
cd /Users/guruts/Desktop/Portfolionarator
curl -s http://localhost:8000/reports/1c5038bd-b94a-4a1e-ac1d-752acd4b3897/view-html > /tmp/after.html
diff /tmp/rajesh_report2.html /tmp/after.html | head -40
```
Expected: zero meaningful diffs (timestamps may differ). The HTML render must be unchanged.

- [ ] **Step 7: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add backend/services/html_renderer.py backend/tests/test_html_renderer_data.py
git commit -m "refactor(html_renderer): extract build_report_data() helper"
```

---

## Task 4: Backend — `GET /reports/{id}/data` endpoint

**Files:**
- Modify: `backend/routes/reports.py` (add route)
- Test: extend `backend/tests/test_reports_routes.py`

- [ ] **Step 1: Append failing test to existing file**

Append to `backend/tests/test_reports_routes.py`:
```python
def test_get_report_data_returns_full_dashboard_json():
    fake_row = {"id": "abc", "client_id": "c1", "month": "2026-04",
                "generated_text": "Dear Test,\n\nBody.", "qa_score": 8}
    fake_packet = {
        "client": {"id": "c1", "name": "Test", "currency": "INR",
                   "liquidity_need_pct": 10, "income_need_monthly": 0,
                   "tax_bracket": "30"},
        "portfolio": {"holdings": [], "aum_cr": 1.0,
                      "inception_date": "2024-01-01"},
        "holdings": [],
        "month": "2026-04",
        "market": {"nifty_mtd_pct": -2.7},
        "letter_text": fake_row["generated_text"],
        "qa_score": 8,
        "report_id": "abc",
        "has_stale_prices": False,
    }
    with patch("routes.reports.reports_db.get_report",
               new=AsyncMock(return_value=fake_row)), \
         patch("routes.reports.build_context_packet",
               new=AsyncMock(return_value=fake_packet)):
        res = client.get("/reports/abc/data")
    assert res.status_code == 200
    body = res.json()
    for k in ("kpis", "holdings", "top_contributors", "top_detractors",
              "sector_allocation", "market_context", "next_steps",
              "letter_text", "client_name", "month"):
        assert k in body
    assert body["letter_text"] == "Dear Test,\n\nBody."


def test_get_report_data_returns_404_when_missing():
    with patch("routes.reports.reports_db.get_report",
               new=AsyncMock(return_value=None)):
        res = client.get("/reports/missing/data")
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd backend && python -m pytest tests/test_reports_routes.py -v`
Expected: the two new tests FAIL with 404 (route missing) for the success case.

- [ ] **Step 3: Add the route**

In `backend/routes/reports.py`, append after the `patch_report` function from Task 2:

```python
@router.get("/{report_id}/data")
async def get_report_data(report_id: str) -> dict:
    """JSON shape consumed by the React dashboard.

    Loads the saved report row, rebuilds the context packet, and
    delegates to ``html_renderer.build_report_data`` — same source the
    server-rendered HTML uses.
    """
    try:
        row = await reports_db.get_report(report_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        packet = await build_context_packet(row["client_id"], row["month"])
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    packet = {
        **packet,
        "report_id": report_id,
        "letter_text": row.get("generated_text") or "",
        "qa_score": row.get("qa_score"),
    }
    return html_renderer.build_report_data(packet)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_reports_routes.py -v`
Expected: all five tests in the file PASS.

- [ ] **Step 5: Smoke-test against the live server**

Run:
```bash
curl -s http://localhost:8000/reports/1c5038bd-b94a-4a1e-ac1d-752acd4b3897/data | python -m json.tool | head -40
```
Expected: JSON with `client_name`, `kpis`, `holdings`, `top_contributors`, etc. — no errors.

- [ ] **Step 6: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add backend/routes/reports.py backend/tests/test_reports_routes.py
git commit -m "feat(reports): GET /reports/{id}/data JSON endpoint"
```

---

## Task 5: Frontend — fix streaming duplication + add API helpers

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Replace `generateReportStream` to fix the chunk duplication**

In `frontend/src/services/api.js`, replace lines 59–144 (the entire `generateReportStream` function and its docstring) with this corrected version:

```javascript
  /**
   * Streaming report generation.
   *
   * Server appends a JSON meta trailer of the form
   *   \n\n[[META]]{"report_id":"...","qa_score":8}[[END]]
   * which we strip out of the visible stream and parse for the caller.
   *
   * Chunk handling: we keep a local accumulator string, and on every
   * frame we emit ONLY the new bytes since the previous emit — never
   * the whole accumulator. This avoids the duplication bug where the
   * caller's setState was reseeing earlier text on every chunk.
   *
   * Caller passes onChunk(textDelta) for live rendering. The delta
   * should be appended with functional setState: setText(p => p + d).
   *
   * Returns { text, report_id, qa_score } after the stream closes.
   */
  generateReportStream: async ({ clientId, month, onChunk }) => {
    const headers = await authHeader()
    const res = await fetch(`${API}/reports/generate-stream`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: clientId, month }),
    })

    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch { /* ignore */ }
      throw new Error(detail)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    const META = '[[META]]'

    let full = ''      // entire stream so far
    let emitted = 0    // index up to which we've already called onChunk

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      full += decoder.decode(value, { stream: true })

      const metaIdx = full.indexOf(META)
      if (metaIdx !== -1) {
        // Stop emitting at META; keep reading until [[END]] for safety.
        if (metaIdx > emitted) {
          onChunk?.(full.slice(emitted, metaIdx))
          emitted = metaIdx
        }
        continue
      }

      // No META in buffer — emit everything except the last (META.length - 1)
      // chars, in case "[[META]]" is split across two frames.
      const safeEnd = full.length - (META.length - 1)
      if (safeEnd > emitted) {
        onChunk?.(full.slice(emitted, safeEnd))
        emitted = safeEnd
      }
    }

    // Final flush: parse META, emit any visible tail before it.
    const metaIdx = full.indexOf(META)
    let text = full
    let meta = {}
    if (metaIdx !== -1) {
      if (metaIdx > emitted) {
        onChunk?.(full.slice(emitted, metaIdx))
      }
      const endIdx = full.indexOf('[[END]]', metaIdx)
      const jsonStr = full.slice(
        metaIdx + META.length,
        endIdx === -1 ? undefined : endIdx,
      )
      try { meta = JSON.parse(jsonStr) } catch { /* ignore */ }
      text = full.slice(0, metaIdx).replace(/\s+$/, '')
    } else if (full.length > emitted) {
      onChunk?.(full.slice(emitted))
    }

    return {
      text,
      report_id: meta.report_id ?? null,
      qa_score: meta.qa_score ?? null,
    }
  },
```

- [ ] **Step 2: Add `getReportData` and `updateReport` helpers**

In `frontend/src/services/api.js`, find the `getReport` function (around lines 52–57) and add these two helpers immediately after it:

```javascript
  getReportData: async (reportId) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/reports/${reportId}/data`, { headers }),
    )
  },

  updateReport: async (reportId, { generated_text }) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/reports/${reportId}`, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ generated_text }),
      }),
    )
  },
```

- [ ] **Step 3: Verify no syntax errors**

Run:
```bash
cd frontend && node --check src/services/api.js 2>&1 || echo "syntax error"
```
Expected: no output (clean). If the project uses ES modules and node refuses, run `npx vite build --mode development 2>&1 | head -30` instead and verify no errors mention `api.js`.

- [ ] **Step 4: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add frontend/src/services/api.js
git commit -m "fix(api): streaming chunk duplication + add report data/update helpers"
```

---

## Task 6: Frontend — shared chart components (KpiTile, SectorDonut, NavLineChart, TopMoversTable, MarketContextGrid, NextStepsCards) + CSS

**Files:**
- Create: `frontend/src/components/report/report.css`
- Create: `frontend/src/components/report/KpiTile.jsx`
- Create: `frontend/src/components/report/SectorDonut.jsx`
- Create: `frontend/src/components/report/NavLineChart.jsx`
- Create: `frontend/src/components/report/TopMoversTable.jsx`
- Create: `frontend/src/components/report/MarketContextGrid.jsx`
- Create: `frontend/src/components/report/NextStepsCards.jsx`

- [ ] **Step 1: Create the CSS file**

Create `frontend/src/components/report/report.css`:
```css
.report-dashboard {
  display: grid;
  gap: 20px;
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
  color: #1a1a1a;
}

.report-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 12px;
}

.report-header h1 { margin: 0; font-size: 28px; font-weight: 700; }
.report-header .month { color: #6b7280; font-size: 14px; }
.report-header .qa-badge {
  background: #ecfdf5; color: #047857; padding: 4px 12px;
  border-radius: 999px; font-size: 13px; font-weight: 600;
}

.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }

.kpi-tile {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
  padding: 16px 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.kpi-tile .label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; }
.kpi-tile .value { font-size: 26px; font-weight: 700; margin-top: 6px; }
.kpi-tile .sublabel { font-size: 13px; color: #6b7280; margin-top: 4px; }
.kpi-tile.tone-positive .value { color: #047857; }
.kpi-tile.tone-negative .value { color: #b91c1c; }

.chart-row { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }

.chart-card, .movers-card, .market-card, .next-card, .letter-card {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
  padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.chart-card h3, .movers-card h3, .market-card h3, .next-card h3, .letter-card h3 {
  margin: 0 0 12px 0; font-size: 16px; font-weight: 600;
}

.movers-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.movers-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.movers-table th { text-align: left; color: #6b7280; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid #e5e7eb; }
.movers-table td { padding: 8px; border-bottom: 1px solid #f3f4f6; }
.movers-table td.ret-pos { color: #047857; font-weight: 600; }
.movers-table td.ret-neg { color: #b91c1c; font-weight: 600; }

.market-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.market-card-inner { padding: 12px; background: #f9fafb; border-radius: 8px; }
.market-card-inner h4 { margin: 0 0 6px 0; font-size: 13px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; }
.market-card-inner p { margin: 0; font-size: 14px; line-height: 1.5; }

.next-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.next-card { display: flex; flex-direction: column; gap: 8px; }
.next-card .icon { font-size: 22px; }
.next-card .title { font-size: 14px; font-weight: 600; }
.next-card .body { font-size: 13px; color: #4b5563; line-height: 1.5; }

.letter-card .letter-body { font-size: 15px; line-height: 1.7; color: #1f2937; }
.letter-card .letter-body p { margin: 0 0 14px 0; }
.letter-card.editing .letter-body p {
  outline: 1px dashed #9ca3af; padding: 6px 8px; border-radius: 6px;
}
.letter-card.editing .letter-body p:hover { background: #fffbeb; }
.streaming-cursor { display: inline-block; width: 8px; height: 18px; background: #1f2937; margin-left: 2px; animation: blink 1s steps(2) infinite; vertical-align: middle; }
@keyframes blink { 50% { opacity: 0; } }

.action-bar {
  position: sticky; bottom: 0; background: #fff;
  border-top: 1px solid #e5e7eb; padding: 12px 24px;
  display: flex; gap: 12px; justify-content: flex-end;
  box-shadow: 0 -1px 3px rgba(0,0,0,0.04);
}
.action-bar button {
  border: 1px solid #d1d5db; background: #fff; color: #111827;
  padding: 8px 16px; border-radius: 8px; font-size: 14px;
  cursor: pointer; font-weight: 500;
}
.action-bar button.primary { background: #111827; color: #fff; border-color: #111827; }
.action-bar button.primary:disabled { opacity: 0.4; cursor: not-allowed; }
.action-bar button.danger { color: #b91c1c; }

.empty-chart { display: flex; align-items: center; justify-content: center; height: 240px; color: #9ca3af; font-size: 13px; border: 1px dashed #e5e7eb; border-radius: 8px; }
```

- [ ] **Step 2: Create `KpiTile.jsx`**

Create `frontend/src/components/report/KpiTile.jsx`:
```jsx
import './report.css'

export default function KpiTile({ label, value, sublabel, tone }) {
  const toneClass = tone ? `tone-${tone}` : ''
  return (
    <div className={`kpi-tile ${toneClass}`}>
      <div className="label">{label}</div>
      <div className="value">{value ?? '—'}</div>
      {sublabel ? <div className="sublabel">{sublabel}</div> : null}
    </div>
  )
}
```

- [ ] **Step 3: Create `SectorDonut.jsx`**

Create `frontend/src/components/report/SectorDonut.jsx`:
```jsx
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './report.css'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
                '#06b6d4', '#a855f7', '#eab308', '#22c55e']

export default function SectorDonut({ allocation }) {
  if (!allocation || allocation.length === 0) {
    return <div className="empty-chart">No allocation data</div>
  }
  const data = allocation.map(a => ({ name: a.sector, value: a.weight_pct }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name"
             innerRadius={55} outerRadius={90} paddingAngle={1}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip formatter={(v) => `${v.toFixed(1)}%`} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
```

- [ ] **Step 4: Create `NavLineChart.jsx`**

Create `frontend/src/components/report/NavLineChart.jsx`:
```jsx
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import './report.css'

export default function NavLineChart({ series }) {
  if (!series || series.length === 0) {
    return <div className="empty-chart">90-day NAV chart — coming soon</div>
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={series}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="portfolio" stroke="#3b82f6" strokeWidth={2} dot={false} name="Portfolio" />
        <Line type="monotone" dataKey="nifty" stroke="#9ca3af" strokeWidth={2} dot={false} name="Nifty 50" />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

- [ ] **Step 5: Create `TopMoversTable.jsx`**

Create `frontend/src/components/report/TopMoversTable.jsx`:
```jsx
import './report.css'

export default function TopMoversTable({ title, movers }) {
  return (
    <div className="movers-card">
      <h3>{title}</h3>
      {(!movers || movers.length === 0) ? (
        <div style={{ fontSize: 13, color: '#9ca3af' }}>No data</div>
      ) : (
        <table className="movers-table">
          <thead>
            <tr><th>Ticker</th><th>Sector</th><th style={{ textAlign: 'right' }}>Return</th></tr>
          </thead>
          <tbody>
            {movers.map((m, i) => {
              const pct = Number(m.month_return_pct ?? 0)
              const cls = pct >= 0 ? 'ret-pos' : 'ret-neg'
              return (
                <tr key={i}>
                  <td>{m.ticker}</td>
                  <td>{m.sector || '—'}</td>
                  <td className={cls} style={{ textAlign: 'right' }}>
                    {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Create `MarketContextGrid.jsx`**

Create `frontend/src/components/report/MarketContextGrid.jsx`:
```jsx
import './report.css'

export default function MarketContextGrid({ cards }) {
  if (!cards || cards.length === 0) return null
  return (
    <div className="market-card">
      <h3>Market Context</h3>
      <div className="market-grid">
        {cards.map((c, i) => (
          <div key={i} className="market-card-inner">
            <h4>{c.title}</h4>
            <p>{c.body}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Create `NextStepsCards.jsx`**

Create `frontend/src/components/report/NextStepsCards.jsx`:
```jsx
import './report.css'

export default function NextStepsCards({ items }) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <h3 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600 }}>What's Next</h3>
      <div className="next-cards">
        {items.map((it, i) => (
          <div key={i} className="next-card">
            <div className="icon">{it.icon || '•'}</div>
            <div className="title">{it.title}</div>
            <div className="body">{it.body}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 8: Verify build**

Run:
```bash
cd /Users/guruts/Desktop/Portfolionarator/frontend && npx vite build --mode development 2>&1 | tail -20
```
Expected: build succeeds. No errors mentioning the new component files.

- [ ] **Step 9: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add frontend/src/components/report/
git commit -m "feat(report): shared dashboard components (KPI, donut, charts, movers, market, next-steps)"
```

---

## Task 7: Frontend — LetterCard + ActionBar

**Files:**
- Create: `frontend/src/components/report/LetterCard.jsx`
- Create: `frontend/src/components/report/ActionBar.jsx`

- [ ] **Step 1: Create `LetterCard.jsx`**

Create `frontend/src/components/report/LetterCard.jsx`:
```jsx
import { useEffect, useRef } from 'react'
import './report.css'

/**
 * Editable letter body. Splits text on blank lines into paragraphs.
 * When isEditing=true, each <p> becomes contentEditable; onChange
 * is called with the new joined text on every input event.
 * When isStreaming=true, shows a blinking cursor after the text.
 */
export default function LetterCard({ text, isEditing, isStreaming, onChange }) {
  const containerRef = useRef(null)
  const paragraphs = (text || '').split(/\n\s*\n/).filter(p => p.length > 0)

  // Re-sync paragraph DOM to incoming text when not editing (handles
  // streaming chunks). When editing, we DON'T overwrite to preserve
  // the RM's cursor and edits in flight.
  useEffect(() => {
    if (isEditing || !containerRef.current) return
    const el = containerRef.current
    const ps = el.querySelectorAll('p')
    ps.forEach((p, i) => {
      const next = paragraphs[i] ?? ''
      if (p.textContent !== next) p.textContent = next
    })
  }, [text, isEditing, paragraphs])

  function handleInput() {
    if (!isEditing || !containerRef.current || !onChange) return
    const ps = containerRef.current.querySelectorAll('p')
    const joined = Array.from(ps)
      .map(p => p.textContent.replace(/[\u200B-\u200D\uFEFF]/g, ''))
      .filter(t => t.length > 0)
      .join('\n\n')
    onChange(joined)
  }

  return (
    <div className={`letter-card ${isEditing ? 'editing' : ''}`}>
      <h3>Letter to the client</h3>
      <div
        ref={containerRef}
        className="letter-body"
        onInput={handleInput}
        suppressContentEditableWarning
      >
        {paragraphs.length === 0 ? (
          <p contentEditable={isEditing} />
        ) : (
          paragraphs.map((p, i) => (
            <p key={i} contentEditable={isEditing}>{p}</p>
          ))
        )}
        {isStreaming ? <span className="streaming-cursor" /> : null}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `ActionBar.jsx`**

Create `frontend/src/components/report/ActionBar.jsx`:
```jsx
import './report.css'

export default function ActionBar({
  reportId, isEditing, isDirty, isStreaming,
  onToggleEdit, onSave, onCancel, onDownload,
}) {
  return (
    <div className="action-bar">
      {!isEditing && !isStreaming && reportId ? (
        <button onClick={onToggleEdit}>Edit letter</button>
      ) : null}

      {isEditing ? (
        <>
          <button className="danger" onClick={onCancel}>Cancel</button>
          <button className="primary" onClick={onSave} disabled={!isDirty}>
            Save changes
          </button>
        </>
      ) : null}

      {!isEditing && reportId ? (
        <button className="primary" onClick={onDownload}>Download PDF</button>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 3: Verify build**

Run:
```bash
cd /Users/guruts/Desktop/Portfolionarator/frontend && npx vite build --mode development 2>&1 | tail -10
```
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add frontend/src/components/report/LetterCard.jsx frontend/src/components/report/ActionBar.jsx
git commit -m "feat(report): LetterCard (contentEditable paragraphs) + ActionBar"
```

---

## Task 8: Frontend — rewrite `ReportPage.jsx` as the dashboard

**Files:**
- Modify: `frontend/src/pages/ReportPage.jsx` (full rewrite)

- [ ] **Step 1: Read the current `ReportPage.jsx` to understand the route and any imports we must keep**

Run: `cat frontend/src/pages/ReportPage.jsx | head -40`
Note: route params (clientId, reportId, month query), navigation imports, page wrapper class names used elsewhere.

- [ ] **Step 2: Replace `frontend/src/pages/ReportPage.jsx` with the dashboard version**

Replace the entire contents with:
```jsx
import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'

import KpiTile from '../components/report/KpiTile'
import SectorDonut from '../components/report/SectorDonut'
import NavLineChart from '../components/report/NavLineChart'
import TopMoversTable from '../components/report/TopMoversTable'
import MarketContextGrid from '../components/report/MarketContextGrid'
import NextStepsCards from '../components/report/NextStepsCards'
import LetterCard from '../components/report/LetterCard'
import ActionBar from '../components/report/ActionBar'
import '../components/report/report.css'

function fmtCr(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return `₹${Number(v).toFixed(2)} Cr`
}
function fmtPct(v) {
  if (v == null || Number.isNaN(v)) return '—'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function toneFromPct(v) {
  if (v == null) return undefined
  return Number(v) >= 0 ? 'positive' : 'negative'
}

export default function ReportPage() {
  const { id, reportId: reportIdParam } = useParams()
  const [searchParams] = useSearchParams()
  const month = searchParams.get('month') || new Date().toISOString().slice(0, 7)
  const isNew = !reportIdParam   // /clients/:id/report/new uses :id

  const [data, setData] = useState(null)
  const [letterText, setLetterText] = useState('')
  const [reportId, setReportId] = useState(reportIdParam || null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [error, setError] = useState(null)

  const originalTextRef = useRef('')

  // Load existing report
  useEffect(() => {
    if (isNew || !reportIdParam) return
    let cancelled = false
    api.getReportData(reportIdParam).then(d => {
      if (cancelled) return
      setData(d)
      setLetterText(d.letter_text || '')
      originalTextRef.current = d.letter_text || ''
      setReportId(d.report_id)
    }).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [isNew, reportIdParam])

  // Stream new report — and immediately fetch skeleton data
  useEffect(() => {
    if (!isNew) return
    let cancelled = false

    // Skeleton data: we don't have a saved report yet, so we fetch the
    // client's portfolio + holdings via existing endpoints and build a
    // minimal data shape. The full /data swap happens once streaming
    // completes and we have a report_id.
    api.getClientPortfolio(id).then(p => {
      if (cancelled) return
      const holdings = p?.portfolio?.holdings || p?.holdings || []
      const skeleton = {
        client_name: p?.client?.name || '',
        month,
        currency: p?.client?.currency || 'INR',
        qa_score: null,
        kpis: {
          portfolio_value_cr: null,
          holdings_count: holdings.length,
          return_mtd_pct: null,
          nifty_mtd_pct: null,
          alpha_pct: null,
        },
        holdings,
        top_contributors: [],
        top_detractors: [],
        sector_allocation: [],
        nav_series: null,
        market_context: [],
        next_steps: [],
        letter_text: '',
      }
      setData(skeleton)
    }).catch(() => { /* skeleton optional */ })

    setIsStreaming(true)
    api.generateReportStream({
      clientId: id,
      month,
      onChunk: (delta) => {
        if (cancelled) return
        setLetterText(prev => prev + delta)
      },
    }).then(async (res) => {
      if (cancelled) return
      setIsStreaming(false)
      if (res.report_id) {
        setReportId(res.report_id)
        try {
          const full = await api.getReportData(res.report_id)
          if (cancelled) return
          setData(full)
          setLetterText(full.letter_text || res.text || '')
          originalTextRef.current = full.letter_text || res.text || ''
        } catch (e) {
          setError(e.message)
        }
      }
    }).catch(e => {
      if (cancelled) return
      setIsStreaming(false)
      setError(e.message)
    })

    return () => { cancelled = true }
  }, [isNew, id, month])

  const kpis = data?.kpis || {}
  const alphaTone = toneFromPct(kpis.alpha_pct)
  const returnTone = toneFromPct(kpis.return_mtd_pct)

  function handleLetterChange(next) {
    setLetterText(next)
    setIsDirty(next !== originalTextRef.current)
  }
  function handleToggleEdit() {
    setIsEditing(true)
    setIsDirty(false)
  }
  function handleCancel() {
    setLetterText(originalTextRef.current)
    setIsEditing(false)
    setIsDirty(false)
  }
  async function handleSave() {
    if (!reportId) return
    try {
      await api.updateReport(reportId, { generated_text: letterText })
      originalTextRef.current = letterText
      setIsEditing(false)
      setIsDirty(false)
    } catch (e) {
      setError(e.message)
    }
  }
  function handleDownload() {
    if (!reportId) return
    const headers = {}
    fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/reports/${reportId}/export-pdf?lang=english`, { headers })
      .then(r => r.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `portfolio-review-${data?.month || month}.pdf`
        document.body.appendChild(a); a.click(); a.remove()
        URL.revokeObjectURL(url)
      })
      .catch(e => setError(e.message))
  }

  if (error) {
    return <div className="report-dashboard"><div style={{ color: '#b91c1c' }}>Error: {error}</div></div>
  }
  if (!data) {
    return <div className="report-dashboard"><div>Loading…</div></div>
  }

  return (
    <div className="report-dashboard">
      <header className="report-header">
        <div>
          <h1>{data.client_name || 'Client'}</h1>
          <div className="month">Portfolio review · {data.month}</div>
        </div>
        {data.qa_score != null ? (
          <div className="qa-badge">QA · {data.qa_score}/10</div>
        ) : null}
      </header>

      <div className="kpi-row">
        <KpiTile label="Portfolio Value"
                 value={fmtCr(kpis.portfolio_value_cr)}
                 sublabel={`${kpis.holdings_count ?? 0} holdings`} />
        <KpiTile label="Return (MTD)"
                 value={fmtPct(kpis.return_mtd_pct)}
                 tone={returnTone} />
        <KpiTile label="Nifty 50 (MTD)"
                 value={fmtPct(kpis.nifty_mtd_pct)}
                 tone={toneFromPct(kpis.nifty_mtd_pct)} />
        <KpiTile label="vs Nifty"
                 value={fmtPct(kpis.alpha_pct)}
                 tone={alphaTone}
                 sublabel="Alpha" />
      </div>

      <div className="chart-row">
        <div className="chart-card">
          <h3>NAV vs Nifty 50 — last 90 days</h3>
          <NavLineChart series={data.nav_series} />
        </div>
        <div className="chart-card">
          <h3>Sector allocation</h3>
          <SectorDonut allocation={data.sector_allocation} />
        </div>
      </div>

      <div className="movers-row">
        <TopMoversTable title="Top contributors" movers={data.top_contributors} />
        <TopMoversTable title="Top detractors" movers={data.top_detractors} />
      </div>

      <MarketContextGrid cards={data.market_context} />
      <NextStepsCards items={data.next_steps} />

      <LetterCard
        text={letterText}
        isEditing={isEditing}
        isStreaming={isStreaming}
        onChange={handleLetterChange}
      />

      <ActionBar
        reportId={reportId}
        isEditing={isEditing}
        isDirty={isDirty}
        isStreaming={isStreaming}
        onToggleEdit={handleToggleEdit}
        onSave={handleSave}
        onCancel={handleCancel}
        onDownload={handleDownload}
      />
    </div>
  )
}
```

- [ ] **Step 3: Verify the route still matches**

Run: `grep -n "report/new\|reports/:reportId\|ReportPage" frontend/src/App.jsx frontend/src/main.jsx 2>/dev/null`
Confirm the existing routes pass either `:id` (for /clients/:id/report/new) or `:reportId` (for /reports/:reportId). The component uses `useParams()` to pick whichever is present. If the actual route param name differs (e.g. `:clientId`), update the `useParams()` destructuring to match.

- [ ] **Step 4: Verify build**

Run:
```bash
cd /Users/guruts/Desktop/Portfolionarator/frontend && npx vite build --mode development 2>&1 | tail -15
```
Expected: build succeeds.

- [ ] **Step 5: Manual smoke test**

In a browser:
1. Open `http://localhost:5173/clients/<rajesh-id>/report/new?month=2026-04`
2. Verify: skeleton dashboard appears immediately (KPI tiles, sector donut)
3. Verify: letter card streams text **without duplication** (no "DearDear Rajesh,")
4. Verify: after streaming completes, full data swap happens — top movers, market context, next-steps populate
5. Click **Edit letter** → click a paragraph → modify text → click **Save changes** → reload → change persists
6. Click **Download PDF** → file downloads

- [ ] **Step 6: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add frontend/src/pages/ReportPage.jsx
git commit -m "feat(ReportPage): full React dashboard with inline edit, streaming skeleton, PDF download"
```

---

## Task 9: Frontend — ClientDetail uses shared chart + KPI components

**Files:**
- Modify: `frontend/src/pages/ClientDetail.jsx`

- [ ] **Step 1: Read current ClientDetail layout**

Run: `cat frontend/src/pages/ClientDetail.jsx`
Identify:
- Where the `<SectorChart>` stub is (lines 127–132 per spec)
- Where the KPI summary block is rendered
- What props/state are available (holdings, portfolio, client)

- [ ] **Step 2: Add imports and replace SectorChart**

In `frontend/src/pages/ClientDetail.jsx`:

Add to the imports at the top of the file:
```jsx
import SectorDonut from '../components/report/SectorDonut'
import KpiTile from '../components/report/KpiTile'
import '../components/report/report.css'
```

Remove the existing `<SectorChart holdings={holdings} />` line and its surrounding stub. Replace the entire "Sector mix" Card block (lines 127–132 in the original file) with:

```jsx
<Card>
  <h2>Sector mix</h2>
  <SectorDonut allocation={sectorAllocation} />
</Card>
```

Above the return statement (or wherever holdings is available), add:

```jsx
const sectorAllocation = (() => {
  const totals = {}
  let grand = 0
  for (const h of holdings || []) {
    const mv = Number(h.qty || 0) * Number(h.current_price || h.avg_price || 0)
    if (!mv) continue
    const s = h.sector || 'Other'
    totals[s] = (totals[s] || 0) + mv
    grand += mv
  }
  if (!grand) return []
  return Object.entries(totals)
    .map(([sector, mv]) => ({ sector, weight_pct: (mv / grand) * 100 }))
    .sort((a, b) => b.weight_pct - a.weight_pct)
})()

const portfolioValueCr = (() => {
  let total = 0
  for (const h of holdings || []) {
    total += Number(h.qty || 0) * Number(h.current_price || h.avg_price || 0)
  }
  return total / 1e7
})()
```

- [ ] **Step 3: Add KPI tile row above existing sections**

Locate the top of the rendered JSX inside the page (just below the page header / client name). Insert:

```jsx
<div className="kpi-row" style={{ marginBottom: 20 }}>
  <KpiTile label="Portfolio value"
           value={`₹${portfolioValueCr.toFixed(2)} Cr`}
           sublabel={`${(holdings || []).length} holdings`} />
  <KpiTile label="Risk profile"
           value={client?.risk_profile || '—'} />
  <KpiTile label="Tax bracket"
           value={client?.tax_bracket ? `${client.tax_bracket}%` : '—'} />
  <KpiTile label="Liquidity need"
           value={client?.liquidity_need_pct != null ? `${client.liquidity_need_pct}%` : '—'} />
</div>
```

If a `client` variable isn't already in scope, source it from the same hook that loads portfolio (e.g. `portfolio?.client` or whichever shape the existing code uses — match what's already there).

- [ ] **Step 4: Verify build**

Run:
```bash
cd /Users/guruts/Desktop/Portfolionarator/frontend && npx vite build --mode development 2>&1 | tail -10
```
Expected: build succeeds.

- [ ] **Step 5: Manual smoke**

Open `http://localhost:5173/clients/<rajesh-id>` → verify KPI tile row appears at top and the sector donut renders with real data (not the stub).

- [ ] **Step 6: Commit**

```bash
cd /Users/guruts/Desktop/Portfolionarator
git add frontend/src/pages/ClientDetail.jsx
git commit -m "feat(ClientDetail): real sector donut + KPI tile row using shared components"
```

---

## Task 10: Final visual verification across all 5 clients

**Files:** none (verification only)

- [ ] **Step 1: Visual check of each client's new-report flow**

For each of the five client IDs (Rajesh, Priya, Arjun, Sunita, Vikram):
1. Open `http://localhost:5173/clients/<id>/report/new?month=2026-04` in the browser
2. Confirm: KPI tiles render immediately from skeleton data
3. Confirm: letter streams **without duplication** (no "DearDear")
4. Confirm: full dashboard swaps in after streaming completes
5. Take a screenshot

- [ ] **Step 2: Visual check of existing-report view**

Open `http://localhost:5173/reports/<rajesh-existing-report-id>` and verify the dashboard renders identically to fresh generation (but with persisted `qa_score` badge).

- [ ] **Step 3: Edit + persistence check**

1. Edit a paragraph in Rajesh's letter
2. Save
3. Hard-refresh the page
4. Confirm the edit persisted
5. Click Download PDF — confirm the PDF contains the edit

- [ ] **Step 4: ClientDetail check**

Open `http://localhost:5173/clients/<id>` for each client → confirm KPI row + sector donut render correctly. The donut percentages should sum to ~100%.

- [ ] **Step 5: Final commit (if any small fixes were needed)**

If any of the above checks revealed a bug, fix inline and commit. Otherwise, no commit needed.

```bash
cd /Users/guruts/Desktop/Portfolionarator && git status
```
