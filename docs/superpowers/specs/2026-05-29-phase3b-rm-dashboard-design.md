# Phase 3B — RM Dashboard

**Status:** Approved for implementation
**Date:** 2026-05-29
**Depends on:** Phase 2 (`2026-05-27-phase2-change-tracking-design.md`), Phase 3A (`2026-05-29-phase3a-narrator-upgrade-design.md`)

---

## 1. Purpose

Phase 2 built the change-tracking model (rationale events, wealth snapshots, allocation targets, drift). Phase 3B surfaces all of it in a dedicated RM Dashboard — a single page where the RM sees allocation vs target, drift status, net worth trend, and a full rationale timeline, and can log a new change without leaving the page.

**Lead outcomes:**
- RM sees at a glance whether any asset class is out of band
- RM can log a rationale event directly from the drift view
- 12-month AUM sparkline shows wealth trajectory
- No new backend work — all APIs exist from Phase 2

---

## 2. Design Decisions

| # | Question | Decision |
|---|----------|----------|
| Q1 | Where does the dashboard live? | Separate `/clients/:id/dashboard` page |
| Q2 | Layout approach | Two-column grid (KPI strip + left/right columns + full-width timeline) |
| Q3 | Can RM log a change from the dashboard? | Yes — "+ Log change" button opens modal |
| Q4 | Sparkline window | 12 months of `wealth_snapshots` |
| Q5 | New backend needed? | None — all APIs exist |
| Q6 | Charting library | Recharts (already installed) |

---

## 3. Route & Navigation

**New route:** `/clients/:id/dashboard`

**Entry point:** `ClientDetail` page gets a **"Dashboard →"** button next to "Generate report".

**Exit:** Dashboard page has a **"← Back to client"** link in the top bar.

---

## 4. Page Layout

```
┌─────────────────────────────────────────────────┐
│  ← Rajesh Mehta              [Generate report →] │  TopBar
├──────────────┬──────────────┬────────────────────┤
│  ₹2.4 Cr AUM │  2 drifts    │  Last change: 3d   │  KPI strip
├──────────────┴──────────────┴────────────────────┤
│                     │                            │
│  Allocation         │  Net Worth (12 months)     │
│  [Donut chart]      │  [AreaChart sparkline]     │
│                     │                            │
│  Drift status       │                            │
│  Equity  ████ +10%↑ │                            │
│  Debt    ████  -5%↓ │                            │
│  Gold    ████   ok ✓│                            │
│  Cash    ████   ok ✓│                            │
│  Alt     ████   ok ✓│                            │
├─────────────────────┴────────────────────────────┤
│  Rationale Timeline              [+ Log change]  │
│  ● 2026-04-18  Equity rebalance — TCS trimmed…   │
│  ● 2026-04-03  Gold target raised — inflation…   │
└──────────────────────────────────────────────────┘
```

---

## 5. Components

### 5.1 File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/pages/DashboardPage.jsx` | Create | Page shell — parallel fetches, layout composition |
| `frontend/src/components/dashboard/DashboardKpiStrip.jsx` | Create | Three KPI tiles: AUM, drift-breach count, last event age |
| `frontend/src/components/dashboard/AllocationDonut.jsx` | Create | Recharts PieChart — actual % per class with target annotations |
| `frontend/src/components/dashboard/DriftBars.jsx` | Create | 5 coloured progress bars, one per asset class |
| `frontend/src/components/dashboard/NetWorthSparkline.jsx` | Create | Recharts AreaChart — 12 months of total_aum |
| `frontend/src/components/dashboard/RationaleTimeline.jsx` | Create | Scrollable event list, newest first |
| `frontend/src/components/dashboard/LogChangeModal.jsx` | Create | Modal form — POST /clients/{id}/rationale-events |
| `frontend/src/pages/ClientDetail.jsx` | Modify | Add "Dashboard →" button |
| `frontend/src/App.jsx` | Modify | Add `/clients/:id/dashboard` route |

### 5.2 DashboardPage data fetching

Four parallel `fetch` calls on mount:

```
Promise.all([
  GET /clients/{id}/portfolio        → { client, holdings, portfolio_return, … }
  GET /clients/{id}/drift            → { equity, debt, gold, cash, alternatives }
  GET /clients/{id}/snapshots        → [ { as_of, total_aum }, … ]  (last 12)
  GET /clients/{id}/rationale-events → [ { event_date, title, … }, … ]
])
```

Each panel receives its slice as a prop and renders its own loading/error state independently.

---

## 6. Component Specifications

### 6.1 DashboardKpiStrip

Three tiles in a horizontal row:

| Tile | Value | Source |
|------|-------|--------|
| **AUM** | ₹X.XX Cr | `portfolio.total_aum` |
| **Drifts** | N classes out of band | count of `drift[class].status !== "on_track"` |
| **Last change** | "X days ago" | most recent `rationale_events[0].event_date` |

### 6.2 AllocationDonut

- Recharts `PieChart` with two rings: outer = actual allocation, inner = target allocation
- 5 segments — equity / debt / gold / cash / alternatives
- Colour palette: equity=blue, debt=green, gold=amber, cash=slate, alternatives=purple
- Legend below the chart with % values

### 6.3 DriftBars

One row per asset class:

```
Equity   [████████████░░░░]  55% actual / 45% target  +10% OVER
Debt     [████████░░░░░░░░]  25% actual / 35% target   -5% UNDER
Gold     [███░░░░░░░░░░░░░]   8% actual /  8% target    ok ✓
```

Colour rules:
- `|delta| <= band` → green bar + "ok ✓"
- `band < |delta| <= band * 2` → amber bar + delta label
- `|delta| > band * 2` → red bar + delta label + ⚠ icon

### 6.4 NetWorthSparkline

- Recharts `AreaChart` — x-axis = month label (Apr, May…), y-axis = AUM in Cr
- Gradient fill (primary colour, 20% opacity)
- Tooltip on hover showing exact AUM + date
- Shows last 12 `wealth_snapshots` ordered by `as_of` ascending
- If fewer than 2 snapshots: shows "Not enough data yet" placeholder

### 6.5 RationaleTimeline

- Scrollable list, max-height 400px
- Each row: coloured dot (colour by event_type) + date + title + truncated rationale (80 chars)
- Event type colour map: rebalance=blue, new_buy=green, exit=red, target_change=amber, review_note=slate
- Empty state: "No changes logged yet"
- "+ Log change" button in the section header (top-right)

### 6.6 LogChangeModal

Fields:

| Field | Input type | Validation |
|-------|-----------|------------|
| Event type | `<select>` — rebalance / new_buy / exit / target_change / review_note | Required |
| Title | `<input type="text">` max 100 chars | Required |
| Rationale | `<textarea>` max 500 chars | Required |
| Date | `<input type="date">` default today | Required |

On submit:
1. `POST /clients/{id}/rationale-events` with `{ event_type, title, body, event_date, author_rm_id }`
2. On success → close modal → re-fetch rationale events → timeline updates inline
3. On error → show inline error message inside modal, keep it open

`author_rm_id` is read from the auth session (same pattern as existing report generation).

---

## 7. Error Handling

Each panel has its own error state — a small inline banner:
```
⚠ Could not load drift data. Retry
```

A failure in one panel does not affect others. The page is usable even if 1–2 fetches fail.

---

## 8. Testing

| Test | File | What it verifies |
|------|------|-----------------|
| `test_dashboard_kpi_strip` | `DashboardKpiStrip.test.jsx` | Renders AUM, drift count, last event age correctly |
| `test_drift_bars_colours` | `DriftBars.test.jsx` | Green/amber/red colour applied correctly per delta |
| `test_drift_bars_empty` | `DriftBars.test.jsx` | Shows placeholder when drift data is null |
| `test_sparkline_renders` | `NetWorthSparkline.test.jsx` | Renders with 12 data points |
| `test_sparkline_insufficient` | `NetWorthSparkline.test.jsx` | Shows placeholder with <2 snapshots |
| `test_timeline_events` | `RationaleTimeline.test.jsx` | Renders events newest-first |
| `test_timeline_empty` | `RationaleTimeline.test.jsx` | Shows empty-state message |
| `test_log_modal_submit` | `LogChangeModal.test.jsx` | POST called with correct payload on submit |
| `test_log_modal_validation` | `LogChangeModal.test.jsx` | Submit disabled when required fields empty |

---

## 9. Out of Scope (Deferred)

- Editing or deleting existing rationale events
- Linking a rationale event to specific transactions from the modal
- Setting / changing allocation targets from the dashboard (Phase 3C)
- Mobile-responsive layout optimisation
- Client-facing view of the dashboard (Phase 3D)
