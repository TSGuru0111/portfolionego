# Report Dashboard Redesign — Design Spec

**Date:** 2026-05-23
**Status:** Approved
**Author:** brainstorming session

## Goal

Replace the current raw-text streaming `ReportPage` and the stub-chart `ClientDetail` with a unified React dashboard. The report page must visually match (and exceed) the existing server-rendered rich HTML, support RM inline editing of the letter text, expose Download PDF, and reuse its chart components on `ClientDetail`.

## Background

- `ReportPage.jsx` currently streams report text into a plain `<pre>` block. A duplication bug renders chunks twice (e.g. "DearDear Rajesh,").
- `ClientDetail.jsx` has a `<SectorChart>` stub at lines 127–132; recharts ^2.12.7 is installed but unused.
- Backend serves a polished `/reports/{id}/view-html` and `/reports/{id}/export-pdf`. No edit endpoint exists.
- `What's Next` cards were just personalized using `liquidity_need_pct`, `income_need_monthly`, `tax_bracket`, `inception_date` (commit `64986c8`).

## Architectural Decisions

1. **Full React port** — no iframe. Both the report page and `ClientDetail` consume native React components.
2. **Single shared component library** under `frontend/src/components/report/`.
3. **Inline `contentEditable` per paragraph** for letter editing; Edit/Save/Cancel via sticky action bar.
4. **Skeleton dashboard during streaming** — KPIs and charts render immediately from existing client/portfolio/holdings endpoints; letter card shows typing cursor.
5. **Single backend data source** — `build_report_data(packet)` helper returns one dict consumed by both the HTML renderer and the new `/reports/{id}/data` JSON endpoint.
6. **Letter is the only editable field** — KPIs, charts, market context, and `What's Next` cards are deterministic and locked.

## Backend Changes

### New endpoint: `GET /reports/{id}/data`

Returns JSON shaped as:
```json
{
  "report_id": "...",
  "client_name": "Rajesh Mehta",
  "month": "2026-04",
  "currency": "INR",
  "qa_score": 8,
  "kpis": {
    "portfolio_value_cr": 2.59,
    "holdings_count": 12,
    "return_mtd_pct": 21.32,
    "nifty_mtd_pct": -2.70,
    "alpha_pct": 24.02
  },
  "holdings": [...],
  "top_contributors": [...],
  "top_detractors": [...],
  "sector_allocation": [{ "sector": "IT", "weight_pct": 18.4 }, ...],
  "nav_series": null,
  "market_context": [
    { "title": "Indian Markets", "body": "..." },
    { "title": "Global Markets", "body": "..." },
    { "title": "Economy", "body": "..." },
    { "title": "Outlook", "body": "..." }
  ],
  "next_steps": [
    { "icon": "💧", "title": "Liquidity Cushion", "body": "..." },
    ...
  ],
  "letter_text": "Dear Rajesh,\n\n..."
}
```

Implementation: thin wrapper that loads the `reports` row, rebuilds the packet via `context_builder.build_context_packet()`, and delegates to a new `html_renderer.build_report_data(packet)` helper (extracted from existing `render_html()` logic).

### New endpoint: `PATCH /reports/{id}`

Body: `{ "letter_text": "..." }`
Behavior: `UPDATE reports SET letter_text = $1, updated_at = now() WHERE id = $2`. Returns the updated row. No re-generation, no LLM call.
Errors: `422` for empty body, `404` for missing id.

### Modified: `services/html_renderer.py`

Extract `build_report_data(packet) -> dict` from the existing rendering logic. The current `render_html()` becomes a thin wrapper that calls `build_report_data()` then runs Jinja over the resulting dict. The new `/data` route reuses the same helper.

## Frontend Changes

### New components — `frontend/src/components/report/`

| Component | Props | Responsibility |
|---|---|---|
| `KpiTile.jsx` | `label, value, sublabel, tone` | Single KPI card |
| `SectorDonut.jsx` | `allocation[]` | Recharts `<PieChart>` with legend |
| `NavLineChart.jsx` | `series \| null` | Recharts `<LineChart>` — NAV vs Nifty (90 days); empty state if null |
| `TopMoversTable.jsx` | `movers[], variant` | Sortable rows: ticker, sector, return % (color-coded) |
| `MarketContextGrid.jsx` | `cards[]` | 4-card grid |
| `NextStepsCards.jsx` | `items[]` | 3 personalized cards |
| `LetterCard.jsx` | `text, isEditing, isStreaming, onChange` | Paragraph-split contentEditable; cursor while streaming |
| `ActionBar.jsx` | `reportId, isEditing, isDirty, onToggleEdit, onSave, onCancel, onDownload` | Sticky bottom bar |
| `report.css` | — | CSS grid layout + tile styles |

All components are pure presentation — no data fetching, no global state.

### Rewritten: `frontend/src/pages/ReportPage.jsx`

Layout (CSS grid):
```
Header (client name · month · QA badge)
KPI row (Portfolio Value | Return MTD | vs Nifty | Holdings)
2-col (NAV chart | Sector Donut)
2-col (Top Contributors | Top Detractors)
Market Context 4-card grid
What's Next 3 cards
Letter Card
Sticky Action Bar
```

Behavior:
- `isNew=true`: render skeleton dashboard from `GET /clients/:id`, `GET /clients/:id/portfolio`, `GET /clients/:id/holdings`. Start `POST /reports/generate-stream`. Letter card displays streaming text with typing cursor. On `[[META]]` parsed → fetch `GET /reports/:id/data` → swap to full data.
- `isNew=false`: fetch `GET /reports/:id/data` → render full dashboard.
- Edit toggle → paragraphs become contentEditable; Save calls `PATCH /reports/:id`; Cancel restores original text from a ref.
- Download PDF opens `/reports/:id/export-pdf?lang=english` in new tab.

### Modified: `frontend/src/pages/ClientDetail.jsx`

- Replace KPI block with `<KpiTile>` row.
- Replace `<SectorChart>` stub (lines 127–132) with `<SectorDonut>`.
- Add `<HoldingsTable>` (sortable) replacing current list.
- Add recent-trades strip (last 5 transactions, from existing endpoint).
- Keep "Past reports" section unchanged.

### Modified: `frontend/src/services/api.js`

**Fix streaming duplication.** Current `generateReportStream` uses a 10-char lookback that combined with React state batching causes chunk re-appending.

New approach:
1. Caller supplies `onChunk(chunk)` callback that uses functional setState (`setText(prev => prev + chunk)`).
2. Remove the 10-char lookback.
3. Inside `generateReportStream`, maintain a local accumulator string. When SSE chunks arrive, append to accumulator. If accumulator contains `[[META]]`, split: emit everything before `[[META]]` once, then parse the JSON between `[[META]]` and `[[END]]` for `report_id` and `qa_score`.
4. Add `streamEnded` boolean so `LetterCard` stops blinking on completion.

Plus two new helpers:
- `getReportData(reportId) → GET /reports/:id/data`
- `updateReport(reportId, { letter_text }) → PATCH /reports/:id`

## Out of Scope

- Multi-language editing (English only in UI; Hindi/Marathi PDF still works server-side).
- Rich text formatting (bold/italic) — paragraphs only.
- Undo/redo beyond a single Cancel.
- Real-time collaborative editing.
- Per-section letter regeneration ("rewrite Markets only").
- NAV historical series backfill — NavLineChart shows graceful empty state until data exists.

## Testing

**Backend (pytest):**
- `GET /reports/{id}/data` returns expected shape (assert all top-level keys).
- `PATCH /reports/{id}` updates letter_text and returns updated row.
- `PATCH` with empty body → 422.
- `PATCH` with non-existent id → 404.

**Frontend (manual smoke):**
- Create new report for each of 5 clients → skeleton renders instantly, letter streams without duplication, full dashboard swaps in on `[[META]]`.
- Open existing report → full dashboard renders.
- Toggle Edit → modify → Save → reload → change persists.
- Download PDF reflects the edits.
- ClientDetail sector donut matches report sector donut.

**Visual regression:** Chrome MCP screenshot after each task.

## Risks

| Risk | Mitigation |
|---|---|
| Recharts bundle size (~120KB) | Tree-shaken on build; already installed |
| contentEditable cross-browser quirks | Plain text only; strip HTML with regex on save |
| Streaming `[[META]]` split across chunks | Buffer-then-regex approach handles split markers |
| KPI drift between HTML and React | Single source: backend `build_report_data()` |
| Missing 90-day NAV series | NavLineChart renders empty state until data exists |
