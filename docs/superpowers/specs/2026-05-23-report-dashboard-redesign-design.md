# Report Dashboard v2 — KPI Redesign, Back-Nav, QA Transparency

**Date:** 2026-05-23
**Status:** Approved (awaiting user review of written spec)
**Builds on:** `2026-05-23-report-dashboard-redesign.md` (v1, already shipped)
**Owner:** PortfolioNarrator team

## Problem

The v1 dashboard shipped (commits `7cfd87c`, `75279fd`). Four issues surfaced in user testing:

1. **KPI tiles read `+0.00%` or `0`** rather than meaningful values, with no indication of whether the zero is real or a missing-data artefact.
2. **No Back navigation** on `/clients/:id/report/:reportId`, `/config`, `/admin`.
3. **QA `8/10` badge is opaque** — no indication of who/what generated the score or why.
4. **The KPI set is thin** — only Portfolio Value, Return MTD, Nifty MTD, vs Nifty. Missing the metrics Indian RMs actually present to HNI clients (XIRR, absolute gain, drift, concentration).

## Goals

- Show six RM-perspective KPIs that map to real client conversations.
- Make missing data honest (`—` with tooltip) and real zero distinguishable from missing.
- Add back-nav to Report, Config, and Admin pages.
- Make the QA badge explain itself via popover with model + reasons.

## Non-Goals (deferred to v3)

- Tax-loss harvesting tile (needs FY-aware STCG/LTCG logic).
- Per-client custom target allocation UI + `clients.target_allocation` column.
- Sharpe ratio / max drawdown tiles (data exists; not on the RM critical path).
- Hindi labels on new KPIs.

## Approach

**Hybrid A→B:** ship target-allocation derived from `clients.risk_profile` now, document `target_allocation` JSONB column as the v3 upgrade once RMs request custom models.

## KPI Set

Six tiles, ordered by RM-presentation value:

| # | KPI | Computation | Tone rules |
|---|-----|-------------|------------|
| 1 | Portfolio Value (₹ Cr) | `Σ qty × current_price / 1e7` | neutral |
| 2 | Absolute Gain since inception (₹) | `Σ qty × (current_price − buy_price)` | green ≥0, red <0 |
| 3 | XIRR (%) | scipy brentq root of NPV over cashflows | neutral; `—` if no transactions |
| 4 | vs Nifty (MTD) (%) | `return_mtd_pct − nifty_mtd_pct` | green ≥0, red <0 |
| 5 | Allocation drift (%) | `max\|actual[k] − target[k]\|` across equity/debt/cash buckets | green <5, gold 5–15, red >15 |
| 6 | Top-3 concentration (%) | top-3 holdings weight by market value | green <25, gold 25–40, red >40 |

Target allocation by risk profile:

```python
TARGET_ALLOCATION_BY_RISK = {
    "conservative": {"equity": 30, "debt": 60, "cash": 10},
    "moderate":     {"equity": 50, "debt": 40, "cash": 10},
    "aggressive":   {"equity": 70, "debt": 25, "cash":  5},
}
# Unknown / null risk_profile → "moderate" with tooltip note.
```

## Data Flow

```
Context Packet (context_builder.py)
    ↓
    holdings + transactions + market data + client.risk_profile
    ↓
build_report_data(packet)  ← html_renderer.py
    ↓
    kpis = {
        portfolio_value_cr,       # existing
        return_mtd_pct,           # existing
        nifty_mtd_pct,            # existing
        alpha_pct,                # existing (becomes "vs Nifty")
        absolute_gain,            # NEW
        xirr_pct,                 # NEW
        drift_pct,                # NEW
        concentration_pct,        # NEW
    }
    ↓
/reports/{id}/data response (routes/reports.py)
    ↓
ReportPage.jsx → KpiRow.jsx → 6 × KpiTile.jsx
```

## Component & File Changes

### Backend (`/backend/`)

| File | Change |
|------|--------|
| `services/portfolio_analytics.py` *(new)* | `compute_xirr(transactions, current_value)`, `compute_absolute_gain(holdings)`, `compute_drift(holdings, risk_profile)`, `compute_concentration(holdings)` |
| `services/risk_profile.py` *(new)* | `TARGET_ALLOCATION_BY_RISK` map + `target_for(risk_profile)` helper |
| `services/html_renderer.py` | Extend `build_report_data()` with the 4 new KPI fields |
| `routes/reports.py` | `/reports/{id}/data` returns new KPI fields + `qa_reasons` array |
| `services/report_generator.py` | `_qa_blocking` keeps `reasons`; `run_qa_check` returns `{score, reasons}`; pipeline persists both |
| `db/reports_db.py` | `save_report(..., qa_reasons=[])` persists `qa_reasons` JSONB |
| `db_schema/migrations/002_qa_reasons.sql` *(new)* | `alter table reports add column qa_reasons jsonb default '[]'` |
| `tests/test_portfolio_analytics.py` *(new)* | XIRR, gain, drift, concentration unit tests |
| `tests/test_html_renderer.py` | Assert new KPI keys present and typed |
| `tests/test_reports_db.py` | Assert `qa_reasons` persisted |

### Frontend (`/frontend/src/`)

| File | Change |
|------|--------|
| `components/layout/BackLink.jsx` *(new)* | Reusable `← Back to {label}` link |
| `components/report/KpiRow.jsx` *(new)* | 6-tile responsive row (6×1 desktop, 3×2 tablet, 2×3 mobile) |
| `components/report/KpiTile.jsx` | Add `tooltip` prop for `—` values, add `tone-neutral` style |
| `components/report/QAScoreBadge.jsx` | Hover/click popover showing model + `reasons[]` |
| `pages/ReportPage.jsx` | Replace inline KPI block with `<KpiRow>`, add `<BackLink>` |
| `pages/ConfigPage.jsx` | Add `<BackLink to="/dashboard" label="Dashboard" />` |
| `pages/AdminPage.jsx` | Add `<BackLink to="/dashboard" label="Dashboard" />` |
| `utils/formatters.js` | Add `fmtAbsoluteINR()`, `fmtSignedPct()` |
| `components/report/report.css` | Tone tokens + 6-tile grid + popover styles |

## Calculations

### XIRR

```python
def compute_xirr(transactions, current_value, today=None):
    if not transactions or current_value <= 0:
        return None
    cashflows = []
    for t in transactions:
        sign = -1 if t["txn_type"].upper() in ("BUY", "SIP") else +1
        cashflows.append((t["txn_date"], sign * float(t["total_value"])))
    cashflows.append((today or date.today(), float(current_value)))

    def npv(rate):
        t0 = cashflows[0][0]
        return sum(cf / (1 + rate) ** ((d - t0).days / 365.0) for d, cf in cashflows)

    try:
        return scipy.optimize.brentq(npv, -0.99, 10.0)
    except (ValueError, RuntimeError):
        error_logger.log_error("xirr", "no convergence", {"n": len(cashflows)})
        return None
```

Fallback chain: empty `transactions` → use `portfolios.inception_date` + `inception_return` if present → return `None`.

### Absolute Gain

```python
def compute_absolute_gain(holdings):
    gain = 0.0
    missing = []
    for h in holdings:
        cp = h.get("current_price")
        if cp is None:
            missing.append(h["ticker"])
            continue
        gain += float(h["qty"]) * (float(cp) - float(h["buy_price"]))
    return {
        "value": gain if (gain or not missing) else None,
        "partial": bool(missing),
        "missing_tickers": missing,
    }
```

### Drift

```python
EQUITY_SECTORS = {"Technology", "Financials", "Energy", "Healthcare", "Consumer", "Industrials", ...}
DEBT_SECTORS   = {"Debt", "Fixed Income", "Bonds"}

def compute_drift(holdings, risk_profile):
    actual = {"equity": 0.0, "debt": 0.0, "cash": 0.0}
    total_mv = sum((h.get("qty") or 0) * (h.get("current_price") or 0) for h in holdings)
    if total_mv <= 0:
        return None
    for h in holdings:
        mv = (h.get("qty") or 0) * (h.get("current_price") or 0)
        w  = mv / total_mv * 100
        if h["sector"] == "Cash":
            actual["cash"] += w
        elif h["sector"] in DEBT_SECTORS:
            actual["debt"] += w
        else:
            actual["equity"] += w
    target = target_for(risk_profile)
    return max(abs(actual[k] - target[k]) for k in target)
```

### Concentration

```python
def compute_concentration(holdings):
    if not holdings: return None
    mvs = [(h.get("qty") or 0) * (h.get("current_price") or 0) for h in holdings]
    total = sum(mvs)
    if total <= 0: return None
    top3 = sum(sorted(mvs, reverse=True)[:3])
    return top3 / total * 100
```

## Zero-Handling Rule

**Critical convention:** missing data returns `None` from backend → JSON `null` → formatter renders `—`. Real `0` stays `0`. The current bug where `+0.00%` appears for missing data is caused by upstream code coercing `None → 0.0`; we eliminate that coercion in the new analytics module.

Frontend formatters:
- `fmtPct(null)` → `'—'`
- `fmtPct(0)` → `'0.00%'`
- `fmtCr(null)` → `'—'`
- `fmtCr(0)` → `'₹0.00 Cr'`

## UI Layout

### KPI row (responsive)

```
Desktop (≥1024px): 6 tiles in one row, equal width
Tablet (640–1023): 3 × 2 grid
Mobile (<640):     2 × 3 grid, smaller font
```

### Tile anatomy

- `label` (small, muted) — e.g. "XIRR"
- `value` (large, bold) — e.g. "14.2%"
- `sublabel` (small, muted) — e.g. "p.a. since inception"
- `tone` border (left 3px) — green/gold/red/neutral
- `title=` tooltip on `—` values

### Report page header

```
← Back to {ClientName}
─────────────────────────────────────
{ClientName}                  [QA · 8/10 ⓘ]
Portfolio review · {month}
```

### QA popover

```
QA Score · 8/10
Graded by Cohere command-r

Reasons:
• Specific ticker attribution present
• Client name + ₹ amounts referenced
• Mild generic phrasing in section 4

Auto-regenerates if < 7
```

## Error Handling & Fallbacks

| Failure | Behavior | User-facing |
|---------|----------|-------------|
| `transactions` empty | XIRR `None` | `—`, tooltip "No transaction history" |
| All `current_price` null | Gain `None` | `—`, tooltip "Live prices unavailable" |
| Some `current_price` null | Compute from available, `partial: true` | Value + sublabel "(partial)" + tooltip lists missing tickers |
| `risk_profile` null/unknown | Default to `"moderate"` | Drift computes, tooltip "Using default 50:50 target" |
| Cohere QA fails | `qa_score=0, qa_reasons=[]` | Badge hidden (existing behavior) |
| `brentq` no convergence | Catch → `None`, log via `error_logger` | `—` |
| `/data` endpoint 500 | Existing error state in `ReportPage` | No change |

Validation threshold preserved: `validate_context` still aborts LLM call if >50% holdings have `current_price=None`. KPIs reuse the threshold for partial-vs-full tagging.

## Migration Safety

- `002_qa_reasons.sql` is additive with `default '[]'` — backfills safely.
- `portfolios.xirr` column already exists — populated going forward, no data migration.
- Old reports keep rendering — KPIs computed at render time from holdings, not snapshotted.

## Testing

| Test | File | Asserts |
|------|------|---------|
| `test_xirr_basic` | `test_portfolio_analytics.py` | Known cashflow matches Excel XIRR within 0.1% |
| `test_xirr_no_transactions` | same | Returns `None`, doesn't raise |
| `test_xirr_no_convergence` | same | Pathological cashflow → `None`, logs error |
| `test_absolute_gain_partial` | same | Missing prices on 1 of 3 → sum of 2 + `partial=True` |
| `test_drift_unknown_risk_profile` | same | `risk_profile=None` uses moderate, returns drift |
| `test_drift_zero_total_mv` | same | Empty/zero portfolio → `None` |
| `test_concentration_top3` | same | 5 holdings → top-3 weight % |
| `test_build_report_data_kpis` | `test_html_renderer.py` | All new KPI keys present and typed |
| `test_qa_reasons_persisted` | `test_reports_db.py` | QA call with reasons → row has `qa_reasons` populated |
| KPI row render (Playwright) | manual | All 6 tiles render with mock; `null` shows `—` |

## v3 Roadmap (not in this spec)

- `clients.target_allocation` JSONB column for per-client custom models.
- Tax-loss harvesting tile.
- Sharpe / max drawdown advanced-mode tiles.
- Hindi labels for new KPIs.

## Open Questions (resolved during brainstorm)

- Data vs UI fix for zeros? → **Both** (data + graceful fallback).
- QA badge fix? → **Tooltip with reasons** (reasons already returned by Cohere, currently discarded).
- KPI set? → **6 KPIs**: Value, Absolute Gain, XIRR, vs Nifty, Drift, Top-3 Concentration.
- Data gap handling? → **Wire up everything now** via risk-profile-derived targets (Hybrid A→B).
- Back-nav scope? → **Report + Config + Admin** pages.
