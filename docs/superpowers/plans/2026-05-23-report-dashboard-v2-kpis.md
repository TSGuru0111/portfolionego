# Report Dashboard v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 4-KPI report header with 6 RM-perspective KPIs (Value, Absolute Gain, XIRR, vs Nifty, Drift, Top-3 Concentration), add Back-nav on Report/Config/Admin pages, make the QA badge transparent via popover with reasons, and stop showing `+0.00%` for missing data.

**Architecture:** New `services/portfolio_analytics.py` module computes the four new KPIs. `services/risk_profile.py` maps `clients.risk_profile` to target equity/debt/cash allocations. `build_report_data()` is extended with the new fields. An additive migration adds `reports.qa_reasons jsonb`. Frontend gains `<BackLink>` and `<KpiRow>` components plus a popover on `<QAScoreBadge>`. Strict rule: missing → `None` → `'—'`; real `0` stays `0`.

**Tech Stack:** Python 3.11 / FastAPI / Supabase / pytest / scipy / React 18 / Vite / Tailwind / Recharts

**Spec:** `docs/superpowers/specs/2026-05-23-report-dashboard-redesign-design.md`

---

## File Structure

**Backend — new files**
- `backend/services/portfolio_analytics.py` — pure functions: `compute_xirr`, `compute_absolute_gain`, `compute_drift`, `compute_concentration`. No DB access.
- `backend/services/risk_profile.py` — `TARGET_ALLOCATION_BY_RISK` constant + `target_for(risk_profile)` helper.
- `backend/db_schema/migrations/001_qa_reasons.sql` — additive column. The `migrations/` directory does not yet exist; Task 7 creates it (project currently keeps flat `schema.sql`/`rls.sql`/`seed.sql` and has no prior numbered migration).
- `backend/tests/test_portfolio_analytics.py` — unit tests for all four functions.
- `backend/tests/test_risk_profile.py` — unit tests for the map + helper.

**Backend — modified**
- `backend/services/html_renderer.py` — extend `build_report_data()` with 4 new KPI keys.
- `backend/services/report_generator.py` — `_qa_blocking` returns `{score, reasons}`; pipeline persists both.
- `backend/db/reports_db.py` — `save_report` accepts `qa_reasons`.
- `backend/routes/reports.py` — `/reports/{id}/data` returns `qa_reasons`.
- `backend/requirements.txt` — add `scipy>=1.11`.

**Frontend — new files**
- `frontend/src/components/layout/BackLink.jsx` — `<BackLink to={...} label={...} />`.
- `frontend/src/components/report/KpiRow.jsx` — 6-tile responsive grid.

**Frontend — modified**
- `frontend/src/components/report/KpiTile.jsx` — add `tone-neutral` + `tooltip` prop.
- `frontend/src/components/report/QAScoreBadge.jsx` — hover/click popover with `reasons[]`.
- `frontend/src/pages/ReportPage.jsx` — use `<KpiRow>` + `<BackLink>`.
- `frontend/src/pages/ConfigPage.jsx` — add `<BackLink>`.
- `frontend/src/pages/AdminPage.jsx` — add `<BackLink>`.
- `frontend/src/utils/formatters.js` — add `formatAbsoluteINR`; reuse existing `formatPct`/`formatCr` (already null-safe + signed).
- `frontend/src/components/report/report.css` — tone tokens + popover styles.

---

## Task 1: `risk_profile.py` — target allocation map

**Files:**
- Create: `backend/services/risk_profile.py`
- Test: `backend/tests/test_risk_profile.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_risk_profile.py
from services.risk_profile import target_for, TARGET_ALLOCATION_BY_RISK


def test_target_for_conservative():
    assert target_for("conservative") == {"equity": 30, "debt": 60, "cash": 10}


def test_target_for_moderate():
    assert target_for("moderate") == {"equity": 50, "debt": 40, "cash": 10}


def test_target_for_aggressive():
    assert target_for("aggressive") == {"equity": 70, "debt": 25, "cash": 5}


def test_target_for_case_insensitive():
    assert target_for("Aggressive") == target_for("aggressive")


def test_target_for_none_defaults_moderate():
    assert target_for(None) == TARGET_ALLOCATION_BY_RISK["moderate"]


def test_target_for_unknown_defaults_moderate():
    assert target_for("gambler") == TARGET_ALLOCATION_BY_RISK["moderate"]


def test_buckets_sum_to_100():
    for bucket in TARGET_ALLOCATION_BY_RISK.values():
        assert sum(bucket.values()) == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_risk_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.risk_profile'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/risk_profile.py
"""Maps client.risk_profile to a target equity/debt/cash allocation.

v2 stop-gap before clients.target_allocation JSONB column lands.
Adjust the percentages in TARGET_ALLOCATION_BY_RISK if firm policy changes.
"""
from __future__ import annotations

TARGET_ALLOCATION_BY_RISK: dict[str, dict[str, int]] = {
    "conservative": {"equity": 30, "debt": 60, "cash": 10},
    "moderate":     {"equity": 50, "debt": 40, "cash": 10},
    "aggressive":   {"equity": 70, "debt": 25, "cash":  5},
}

_DEFAULT_BUCKET = "moderate"


def target_for(risk_profile: str | None) -> dict[str, int]:
    """Return the target allocation dict for a risk profile.

    Unknown or null profiles default to 'moderate'. Case-insensitive lookup.
    """
    if not risk_profile:
        return TARGET_ALLOCATION_BY_RISK[_DEFAULT_BUCKET]
    return TARGET_ALLOCATION_BY_RISK.get(
        risk_profile.lower(),
        TARGET_ALLOCATION_BY_RISK[_DEFAULT_BUCKET],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_risk_profile.py -v`
Expected: PASS — 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/risk_profile.py backend/tests/test_risk_profile.py
git commit -m "feat(analytics): risk-profile to target allocation mapping"
```

---

## Task 2: `compute_concentration`

**Files:**
- Create: `backend/services/portfolio_analytics.py`
- Test: `backend/tests/test_portfolio_analytics.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_portfolio_analytics.py
import pytest
from services.portfolio_analytics import compute_concentration


def _h(ticker, qty, price, sector="Technology"):
    return {"ticker": ticker, "qty": qty, "current_price": price, "sector": sector, "buy_price": price}


def test_concentration_top3_of_5():
    holdings = [
        _h("A", 100, 1000),   # 100k — top 1
        _h("B", 100,  800),   # 80k  — top 2
        _h("C", 100,  600),   # 60k  — top 3
        _h("D", 100,  400),   # 40k
        _h("E", 100,  100),   # 10k
    ]
    # top-3 total = 240k, grand total = 290k → 82.76%
    assert compute_concentration(holdings) == pytest.approx(82.7586, abs=0.01)


def test_concentration_empty_returns_none():
    assert compute_concentration([]) is None


def test_concentration_zero_mv_returns_none():
    holdings = [_h("A", 0, 0), _h("B", 0, 0)]
    assert compute_concentration(holdings) is None


def test_concentration_two_holdings_returns_100():
    holdings = [_h("A", 100, 1000), _h("B", 100, 500)]
    assert compute_concentration(holdings) == pytest.approx(100.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_portfolio_analytics.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/portfolio_analytics.py
"""Pure analytics functions for KPI tiles.

Every function returns None when its inputs are insufficient so the frontend
can render an em-dash instead of a misleading 0. Never coerce None to 0 here.
"""
from __future__ import annotations

from typing import Any


def _mv(holding: dict[str, Any]) -> float:
    qty = holding.get("qty") or 0
    price = holding.get("current_price") or 0
    try:
        return float(qty) * float(price)
    except (TypeError, ValueError):
        return 0.0


def compute_concentration(holdings: list[dict[str, Any]]) -> float | None:
    """Return top-3 holdings as a percent of total market value."""
    if not holdings:
        return None
    mvs = [_mv(h) for h in holdings]
    total = sum(mvs)
    if total <= 0:
        return None
    top3 = sum(sorted(mvs, reverse=True)[:3])
    return top3 / total * 100.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_portfolio_analytics.py -v`
Expected: PASS — 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/portfolio_analytics.py backend/tests/test_portfolio_analytics.py
git commit -m "feat(analytics): top-3 concentration KPI"
```

---

## Task 3: `compute_absolute_gain`

**Files:**
- Modify: `backend/services/portfolio_analytics.py`
- Modify: `backend/tests/test_portfolio_analytics.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_portfolio_analytics.py`:

```python
from services.portfolio_analytics import compute_absolute_gain


def test_absolute_gain_full_data():
    holdings = [
        {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": 1000},
        {"ticker": "B", "qty":  50, "buy_price": 200, "current_price":  300},
    ]
    result = compute_absolute_gain(holdings)
    assert result["value"] == pytest.approx(25000.0)
    assert result["partial"] is False
    assert result["missing_tickers"] == []


def test_absolute_gain_partial_missing_price():
    holdings = [
        {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": 1000},
        {"ticker": "B", "qty":  50, "buy_price": 200, "current_price": None},
    ]
    result = compute_absolute_gain(holdings)
    assert result["value"] == pytest.approx(20000.0)
    assert result["partial"] is True
    assert result["missing_tickers"] == ["B"]


def test_absolute_gain_all_missing_returns_none_value():
    holdings = [
        {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": None},
        {"ticker": "B", "qty":  50, "buy_price": 200, "current_price": None},
    ]
    result = compute_absolute_gain(holdings)
    assert result["value"] is None
    assert result["partial"] is True
    assert sorted(result["missing_tickers"]) == ["A", "B"]


def test_absolute_gain_empty_holdings():
    result = compute_absolute_gain([])
    assert result == {"value": None, "partial": False, "missing_tickers": []}


def test_absolute_gain_negative_when_loss():
    holdings = [{"ticker": "A", "qty": 100, "buy_price": 1000, "current_price": 800}]
    result = compute_absolute_gain(holdings)
    assert result["value"] == pytest.approx(-20000.0)
    assert result["partial"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_portfolio_analytics.py -k absolute_gain -v`
Expected: FAIL with `ImportError: cannot import name 'compute_absolute_gain'`.

- [ ] **Step 3: Append implementation**

Append to `backend/services/portfolio_analytics.py`:

```python
def compute_absolute_gain(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Return {value, partial, missing_tickers}.

    value is None when ALL holdings are missing current_price OR holdings is empty.
    partial is True when at least one holding was skipped.
    """
    if not holdings:
        return {"value": None, "partial": False, "missing_tickers": []}

    gain = 0.0
    missing: list[str] = []
    counted = 0
    for h in holdings:
        cp = h.get("current_price")
        if cp is None:
            missing.append(h.get("ticker", "?"))
            continue
        try:
            qty = float(h.get("qty") or 0)
            bp = float(h.get("buy_price") or 0)
            cp_f = float(cp)
        except (TypeError, ValueError):
            missing.append(h.get("ticker", "?"))
            continue
        gain += qty * (cp_f - bp)
        counted += 1

    return {
        "value": gain if counted > 0 else None,
        "partial": bool(missing),
        "missing_tickers": missing,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_portfolio_analytics.py -k absolute_gain -v`
Expected: PASS — 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/portfolio_analytics.py backend/tests/test_portfolio_analytics.py
git commit -m "feat(analytics): absolute gain with partial-data tracking"
```

---

## Task 4: `compute_drift`

**Files:**
- Modify: `backend/services/portfolio_analytics.py`
- Modify: `backend/tests/test_portfolio_analytics.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_portfolio_analytics.py`:

```python
from services.portfolio_analytics import compute_drift


def test_drift_perfect_match_aggressive():
    holdings = [
        {"qty": 700, "current_price": 1, "sector": "Technology"},
        {"qty": 250, "current_price": 1, "sector": "Debt"},
        {"qty":  50, "current_price": 1, "sector": "Cash"},
    ]
    assert compute_drift(holdings, "aggressive") == pytest.approx(0.0, abs=0.01)


def test_drift_all_equity_vs_moderate():
    holdings = [{"qty": 100, "current_price": 100, "sector": "Technology"}]
    assert compute_drift(holdings, "moderate") == pytest.approx(50.0, abs=0.01)


def test_drift_unknown_risk_profile_uses_moderate():
    holdings = [{"qty": 100, "current_price": 100, "sector": "Technology"}]
    assert compute_drift(holdings, "gambler") == pytest.approx(50.0, abs=0.01)


def test_drift_none_risk_profile_uses_moderate():
    holdings = [{"qty": 100, "current_price": 100, "sector": "Technology"}]
    assert compute_drift(holdings, None) == pytest.approx(50.0, abs=0.01)


def test_drift_zero_total_mv_returns_none():
    holdings = [{"qty": 0, "current_price": 0, "sector": "Technology"}]
    assert compute_drift(holdings, "moderate") is None


def test_drift_empty_holdings_returns_none():
    assert compute_drift([], "moderate") is None


def test_drift_debt_sector_recognized():
    holdings = [
        {"qty": 100, "current_price": 100, "sector": "Technology"},
        {"qty": 100, "current_price": 100, "sector": "Fixed Income"},
    ]
    # 50/50 vs aggressive (70/25/5) → equity drift = 20, debt drift = 25, cash = 5
    assert compute_drift(holdings, "aggressive") == pytest.approx(25.0, abs=0.01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_portfolio_analytics.py -k drift -v`
Expected: FAIL with `ImportError: cannot import name 'compute_drift'`.

- [ ] **Step 3: Append implementation**

Append to `backend/services/portfolio_analytics.py`:

```python
from services.risk_profile import target_for

DEBT_SECTORS: set[str] = {
    "Debt", "Fixed Income", "Bonds", "Government Securities", "Corporate Bonds",
}
CASH_SECTORS: set[str] = {"Cash", "Liquid", "Money Market"}


def _bucket_for(sector: str | None) -> str:
    if not sector:
        return "equity"
    s = sector.strip()
    if s in CASH_SECTORS:
        return "cash"
    if s in DEBT_SECTORS:
        return "debt"
    return "equity"


def compute_drift(
    holdings: list[dict[str, Any]],
    risk_profile: str | None,
) -> float | None:
    """Max absolute % deviation of actual vs target equity/debt/cash allocation.

    Returns None for empty or zero-value portfolios.
    """
    if not holdings:
        return None
    actual = {"equity": 0.0, "debt": 0.0, "cash": 0.0}
    total = sum(_mv(h) for h in holdings)
    if total <= 0:
        return None
    for h in holdings:
        bucket = _bucket_for(h.get("sector"))
        actual[bucket] += _mv(h) / total * 100.0
    target = target_for(risk_profile)
    return max(abs(actual[k] - target[k]) for k in target)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_portfolio_analytics.py -k drift -v`
Expected: PASS — 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/portfolio_analytics.py backend/tests/test_portfolio_analytics.py
git commit -m "feat(analytics): allocation drift vs risk-profile target"
```

---

## Task 5: `compute_xirr`

**Files:**
- Modify: `backend/services/portfolio_analytics.py`
- Modify: `backend/tests/test_portfolio_analytics.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add scipy dependency**

Open `backend/requirements.txt`. If `scipy` is absent, append:

```
scipy>=1.11
```

Run: `cd backend && pip install scipy`
Expected: scipy installs cleanly.

- [ ] **Step 2: Write the failing test**

Append to `backend/tests/test_portfolio_analytics.py`:

```python
from datetime import date
from services.portfolio_analytics import compute_xirr


def test_xirr_simple_doubling_in_one_year():
    txns = [{"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 100}]
    result = compute_xirr(txns, current_value=200, today=date(2025, 1, 1))
    assert result == pytest.approx(1.0, abs=0.001)


def test_xirr_flat_returns_zero():
    txns = [{"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 100}]
    result = compute_xirr(txns, current_value=100, today=date(2025, 1, 1))
    assert result == pytest.approx(0.0, abs=0.001)


def test_xirr_empty_transactions_returns_none():
    assert compute_xirr([], current_value=100) is None


def test_xirr_zero_current_value_returns_none():
    txns = [{"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 100}]
    assert compute_xirr(txns, current_value=0) is None


def test_xirr_handles_sell_transactions():
    txns = [
        {"txn_type": "BUY",  "txn_date": date(2024, 1, 1), "total_value": 100},
        {"txn_type": "SELL", "txn_date": date(2024, 7, 1), "total_value":  50},
    ]
    result = compute_xirr(txns, current_value=60, today=date(2025, 1, 1))
    assert result is not None
    assert -0.5 < result < 0.5


def test_xirr_non_convergent_returns_none():
    # All cashflows same sign — no root exists in [-0.99, 10.0]
    txns = [
        {"txn_type": "SELL", "txn_date": date(2024, 1, 1), "total_value": 100},
        {"txn_type": "SELL", "txn_date": date(2024, 7, 1), "total_value": 100},
    ]
    result = compute_xirr(txns, current_value=100, today=date(2025, 1, 1))
    assert result is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_portfolio_analytics.py -k xirr -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Append implementation**

Append to `backend/services/portfolio_analytics.py`:

```python
from datetime import date as _date
from scipy.optimize import brentq

_BUY_TYPES = {"BUY", "SIP", "PURCHASE"}


def _npv(rate: float, cashflows: list[tuple[_date, float]]) -> float:
    t0 = cashflows[0][0]
    total = 0.0
    for d, cf in cashflows:
        years = (d - t0).days / 365.0
        total += cf / ((1 + rate) ** years)
    return total


def compute_xirr(
    transactions: list[dict[str, Any]],
    current_value: float,
    today: _date | None = None,
) -> float | None:
    """Return XIRR as a decimal (0.14 == 14% p.a.).

    BUY/SIP/PURCHASE cashflows are outflows (negative); everything else is an
    inflow. The terminal current_value is added as a positive cashflow at
    `today`. Returns None when inputs are insufficient or root-finder fails.
    """
    if not transactions:
        return None
    if current_value is None or current_value <= 0:
        return None

    cashflows: list[tuple[_date, float]] = []
    for t in transactions:
        try:
            amt = float(t["total_value"])
        except (KeyError, TypeError, ValueError):
            continue
        sign = -1 if (t.get("txn_type") or "").upper() in _BUY_TYPES else +1
        cashflows.append((t["txn_date"], sign * amt))

    cashflows.append((today or _date.today(), float(current_value)))
    cashflows.sort(key=lambda x: x[0])

    try:
        return brentq(_npv, -0.99, 10.0, args=(cashflows,), maxiter=200)
    except (ValueError, RuntimeError):
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_portfolio_analytics.py -k xirr -v`
Expected: PASS — 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/services/portfolio_analytics.py backend/tests/test_portfolio_analytics.py
git commit -m "feat(analytics): XIRR via scipy brentq with graceful no-convergence"
```

---

## Task 6: Extend `build_report_data` with 4 new KPIs

**Files:**
- Modify: `backend/services/html_renderer.py`
- Possibly modify: `backend/services/context_builder.py` (if transactions not in packet)
- Modify: `backend/tests/test_html_renderer.py` (or create)

- [ ] **Step 1: Confirm transactions are available in the packet**

Run: `grep -n "transactions" backend/services/context_builder.py | head -20`

If `packet["transactions"]` is already populated, skip Step 2.

- [ ] **Step 2: Add transactions to packet if missing**

Inside `build_context_packet()` (after holdings load), add:

```python
from db.supabase_client import get_supabase
sb = get_supabase()
txn_rows = (
    sb.table("transactions")
    .select("txn_type, ticker, total_value, txn_date")
    .eq("client_id", client_id)
    .order("txn_date")
    .execute()
).data or []
packet["transactions"] = txn_rows
```

- [ ] **Step 3: Write the failing test**

Open or create `backend/tests/test_html_renderer.py`. Append:

```python
from datetime import date
from services.html_renderer import build_report_data


def _packet(**overrides):
    base = {
        "client": {"name": "Test", "risk_profile": "moderate"},
        "holdings": [
            {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": 1000, "sector": "Technology"},
            {"ticker": "B", "qty":  50, "buy_price": 200, "current_price":  300, "sector": "Debt"},
        ],
        "transactions": [
            {"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 80000},
            {"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 10000},
        ],
        "market": {"nifty_mtd_pct": 1.0, "usdinr_change_pct": 0.0, "crude_change_pct": 0.0},
        "month": "2025-11",
    }
    base.update(overrides)
    return base


def test_report_data_has_new_kpis():
    data = build_report_data(_packet())
    k = data["kpis"]
    assert "absolute_gain" in k
    assert "xirr_pct" in k
    assert "drift_pct" in k
    assert "concentration_pct" in k


def test_report_data_absolute_gain_shape():
    data = build_report_data(_packet())
    g = data["kpis"]["absolute_gain"]
    assert g is None or set(g.keys()) >= {"value", "partial", "missing_tickers"}


def test_report_data_drift_is_number_or_none():
    data = build_report_data(_packet())
    d = data["kpis"]["drift_pct"]
    assert d is None or isinstance(d, (int, float))


def test_report_data_concentration_is_number_or_none():
    data = build_report_data(_packet())
    c = data["kpis"]["concentration_pct"]
    assert c is None or isinstance(c, (int, float))


def test_report_data_missing_prices_yield_none_not_zero():
    packet = _packet(holdings=[
        {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": None, "sector": "Technology"},
    ])
    data = build_report_data(packet)
    assert data["kpis"]["absolute_gain"]["value"] is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && pytest tests/test_html_renderer.py -k new_kpis -v`
Expected: FAIL with `KeyError: 'absolute_gain'` or similar.

- [ ] **Step 5: Extend `build_report_data`**

Open `backend/services/html_renderer.py`. Add imports near the top:

```python
from services.portfolio_analytics import (
    compute_absolute_gain,
    compute_concentration,
    compute_drift,
    compute_xirr,
)
```

Find the `kpis = { ... }` dict inside `build_report_data` (around lines 417-477). After the existing keys, add:

```python
    abs_gain = compute_absolute_gain(holdings)
    holdings_mv = sum(
        (h.get("qty") or 0) * (h.get("current_price") or 0)
        for h in holdings
    )
    xirr = compute_xirr(
        packet.get("transactions", []),
        current_value=holdings_mv,
    )
    risk = (packet.get("client") or {}).get("risk_profile")

    kpis["absolute_gain"] = abs_gain
    kpis["xirr_pct"] = (xirr * 100.0) if xirr is not None else None
    kpis["drift_pct"] = compute_drift(holdings, risk)
    kpis["concentration_pct"] = compute_concentration(holdings)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_html_renderer.py -v`
Expected: PASS — 5 new tests + existing tests green.

- [ ] **Step 7: Commit**

```bash
git add backend/services/html_renderer.py backend/services/context_builder.py backend/tests/test_html_renderer.py
git commit -m "feat(report-data): wire 4 new KPIs into build_report_data"
```

---

## Task 7: Migration — `reports.qa_reasons jsonb`

**Files:**
- Create: `backend/db_schema/migrations/` (directory does not yet exist — `backend/db_schema/` currently holds flat `schema.sql`, `rls.sql`, `seed.sql` with no prior numbered migration)
- Create: `backend/db_schema/migrations/001_qa_reasons.sql`

- [ ] **Step 1: Create the migrations directory and write the migration**

```bash
mkdir -p backend/db_schema/migrations
```

```sql
-- backend/db_schema/migrations/001_qa_reasons.sql
-- Adds qa_reasons JSONB column to reports for QA-badge transparency.
-- Additive only — safe on existing data.

alter table reports
  add column if not exists qa_reasons jsonb default '[]'::jsonb;

comment on column reports.qa_reasons is
  'Array of short strings from the Cohere QA grader explaining the score.';
```

- [ ] **Step 2: Apply in Supabase SQL Editor**

Paste the file contents and run. Expected: `ALTER TABLE` succeeds.

- [ ] **Step 3: Verify**

In SQL Editor:

```sql
select column_name, data_type, column_default
from information_schema.columns
where table_name = 'reports' and column_name = 'qa_reasons';
```

Expected: one row, `data_type = jsonb`, `column_default = '[]'::jsonb`.

- [ ] **Step 4: Commit**

```bash
git add backend/db_schema/migrations/001_qa_reasons.sql
git commit -m "chore(db): migration 001 - reports.qa_reasons jsonb"
```

---

## Task 8: Persist QA reasons through the pipeline

**Files:**
- Modify: `backend/services/report_generator.py`
- Modify: `backend/db/reports_db.py`
- Modify: `backend/tests/test_report_generator.py` (or create)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_report_generator.py`:

```python
from services.report_generator import _extract_score_and_reasons


def test_extract_returns_score_and_reasons():
    raw = '{"score": 8, "reasons": ["good ticker mentions", "client name used"]}'
    result = _extract_score_and_reasons(raw)
    assert result == {"score": 8, "reasons": ["good ticker mentions", "client name used"]}


def test_extract_missing_reasons_defaults_empty():
    raw = '{"score": 7}'
    assert _extract_score_and_reasons(raw) == {"score": 7, "reasons": []}


def test_extract_malformed_returns_zero():
    assert _extract_score_and_reasons("garbage") == {"score": 0, "reasons": []}


def test_extract_clamps_score_range():
    high = '{"score": 99, "reasons": []}'
    assert _extract_score_and_reasons(high)["score"] == 10
    low = '{"score": -3, "reasons": []}'
    assert _extract_score_and_reasons(low)["score"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_report_generator.py -k extract -v`
Expected: FAIL with `ImportError: cannot import name '_extract_score_and_reasons'`.

- [ ] **Step 3: Replace `_extract_score`**

Open `backend/services/report_generator.py`. Find the `_extract_score` function (around lines 93-106) and replace with:

```python
def _extract_score_and_reasons(raw: str) -> dict[str, Any]:
    """Parse {score, reasons} from Cohere's QA JSON response.

    Returns {"score": 0, "reasons": []} on any parse failure.
    """
    if not raw:
        return {"score": 0, "reasons": []}
    try:
        payload = json.loads(raw)
        score = int(payload.get("score", 0))
        score = max(0, min(10, score))
        reasons = payload.get("reasons") or []
        if not isinstance(reasons, list):
            reasons = []
        reasons = [str(r)[:200] for r in reasons[:5]]
        return {"score": score, "reasons": reasons}
    except (ValueError, TypeError, json.JSONDecodeError):
        m = re.search(r"\b(10|[1-9])\b", raw)
        score = int(m.group(1)) if m else 0
        return {"score": score, "reasons": []}
```

- [ ] **Step 4: Update `_qa_blocking` and `run_qa_check`**

In the same file, replace the existing functions:

```python
def _qa_blocking(client: cohere.Client, letter_text: str) -> dict[str, Any]:
    resp = client.chat(
        model=QA_MODEL,
        message=_QA_PROMPT + letter_text[:8000],
        temperature=0.1,
        max_tokens=160,
    )
    return _extract_score_and_reasons(getattr(resp, "text", "") or "")


async def run_qa_check(letter_text: str) -> dict[str, Any]:
    """Score the letter. Returns {"score": int, "reasons": list[str]}."""
    client = _cohere_client()
    if client is None or not letter_text.strip():
        return {"score": 0, "reasons": []}
    try:
        return await _with_retry("qa_check", lambda: _qa_blocking(client, letter_text))
    except Exception:
        return {"score": 0, "reasons": []}
```

- [ ] **Step 5: Update pipeline call sites**

Find every `await run_qa_check(...)` in `report_generator.py`. Replace pattern:

```python
qa_score = await run_qa_check(final_text)
```

with:

```python
qa = await run_qa_check(final_text)
qa_score = qa["score"]
qa_reasons = qa["reasons"]
```

Do the same in the regen branch and in `generate_report_batch`.

- [ ] **Step 6: Update `save_report` call**

Find the `save_report(...)` invocation. It is `async` — preserve the `await` — and add `qa_reasons=qa_reasons` alongside the existing kwargs:

```python
report_id = await save_report(
    client_id=context["client"]["id"],
    month=context["month"],
    generated_text=text,
    qa_score=qa_score,
    qa_reasons=qa_reasons,
)
```

- [ ] **Step 7: Update `save_report` signature**

Open `backend/db/reports_db.py`. The current signature is async with `qa_score: int | None = None` default and a `pdf_url` kwarg — keep all of those — only insert `qa_reasons` as a new optional kwarg, and write it into the payload:

```python
async def save_report(
    client_id: str,
    month: str,
    generated_text: str,
    qa_score: int | None = None,
    qa_reasons: list[str] | None = None,
    hindi_text: str | None = None,
    pdf_url: str | None = None,
) -> str | None:
    supabase = _require_supabase()
    payload: dict[str, Any] = {
        "client_id": client_id,
        "month": month,
        "generated_text": generated_text,
        "qa_score": qa_score,
        "qa_reasons": qa_reasons or [],
    }
    if hindi_text is not None:
        payload["hindi_text"] = hindi_text
    if pdf_url is not None:
        payload["pdf_url"] = pdf_url
    res = supabase.table("reports").insert(payload).execute()
    rows = res.data or []
    return rows[0].get("id") if rows else None
```

(Only the `qa_reasons` parameter + payload line are new — async, `pdf_url`, and `_require_supabase()` are already present.)

- [ ] **Step 8: Run tests**

Run: `cd backend && pytest tests/test_report_generator.py -v`
Expected: PASS — 4 new tests + existing tests green.

- [ ] **Step 9: Commit**

```bash
git add backend/services/report_generator.py backend/db/reports_db.py backend/tests/test_report_generator.py
git commit -m "feat(qa): persist Cohere QA reasons alongside score"
```

---

## Task 9: `/reports/{id}/data` returns `qa_reasons`

**Files:**
- Modify: `backend/routes/reports.py`

- [ ] **Step 1: Update the endpoint**

Open `backend/routes/reports.py`. Find the `get_report_data` (or equivalent) handler for `GET /reports/{id}/data`. Where it loads the report row, ensure the `select(...)` includes `qa_reasons`, and where the response dict is assembled, add:

```python
response["qa_reasons"] = row.get("qa_reasons") or []
```

- [ ] **Step 2: Manual verification**

Start backend: `cd backend && uvicorn main:app --reload`
Run: `curl http://localhost:8000/reports/<any-existing-report-id>/data | jq .qa_reasons`
Expected: `[]` for old reports, populated list for newly-generated ones.

- [ ] **Step 3: Commit**

```bash
git add backend/routes/reports.py
git commit -m "feat(api): /reports/{id}/data returns qa_reasons array"
```

---

## Task 10: `BackLink` component

**Files:**
- Create: `frontend/src/components/layout/BackLink.jsx`

- [ ] **Step 1: Write the component**

```jsx
// frontend/src/components/layout/BackLink.jsx
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function BackLink({ to, label }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-primary-700"
    >
      <ArrowLeft className="w-4 h-4" />
      Back to {label}
    </Link>
  )
}
```

- [ ] **Step 2: Verify it lints**

Run: `cd frontend && npm run lint`
Expected: no errors on the new file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/BackLink.jsx
git commit -m "feat(layout): reusable BackLink component"
```

---

## Task 11: Add `<BackLink>` to Report, Config, Admin pages

**Files:**
- Modify: `frontend/src/pages/ReportPage.jsx`
- Modify: `frontend/src/pages/ConfigPage.jsx`
- Modify: `frontend/src/pages/AdminPage.jsx`
- Modify: `frontend/src/components/report/report.css`

- [ ] **Step 1: ReportPage — add BackLink**

Open `frontend/src/pages/ReportPage.jsx`. Import:

```jsx
import BackLink from '../components/layout/BackLink'
```

Find the `<header className="report-header">` block (around line 180). Precede it with:

```jsx
<div className="report-page-nav">
  <BackLink
    to={`/clients/${data?.client_id || id}`}
    label={data?.client_name || 'client'}
  />
</div>
```

The component already destructures `id` from `useParams()` at the top — `const { id, reportId: reportIdParam } = useParams()` (ReportPage.jsx:30). `id` IS the clientId per the route `/clients/:id/report/:reportId` — do not rename it or invent a `clientId` alias.

- [ ] **Step 2: ConfigPage — add BackLink**

Open `frontend/src/pages/ConfigPage.jsx`. Import:

```jsx
import BackLink from '../components/layout/BackLink'
```

At the top of the page JSX (above the page title):

```jsx
<div className="mb-4">
  <BackLink to="/dashboard" label="Dashboard" />
</div>
```

- [ ] **Step 3: AdminPage — add BackLink**

Same as Step 2 for `frontend/src/pages/AdminPage.jsx`.

- [ ] **Step 4: CSS**

Append to `frontend/src/components/report/report.css`:

```css
.report-page-nav {
  margin: 12px 0 8px 0;
}
```

- [ ] **Step 5: Manual verification**

Run: `cd frontend && npm run dev`
- `/clients/:id/report/:reportId` → back link shows "Back to {clientName}", click goes to client detail.
- `/config` → "Back to Dashboard".
- `/admin` → "Back to Dashboard".

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ReportPage.jsx frontend/src/pages/ConfigPage.jsx frontend/src/pages/AdminPage.jsx frontend/src/components/report/report.css
git commit -m "feat(nav): BackLink on Report, Config, Admin pages"
```

---

## Task 12: Formatter helpers + null discipline

**Files:**
- Modify: `frontend/src/utils/formatters.js`

- [ ] **Step 1: Audit existing formatters**

Run: `grep -n "export function" frontend/src/utils/formatters.js`

Existing exports (verified, do not duplicate): `formatINR`, `formatPct(value, decimals=2)` — always signed, returns `'—'` for null/NaN — `formatCr(value, decimals=2)` — returns `'—'` for null/NaN, format `'₹X.XX Cr'` — `formatMonth`, `formatDateIN`, `returnColor`.

Plan-wide naming reconciliation: the plan originally referenced `fmtPct`/`fmtCr`/`fmtSignedPct` but the project uses `formatPct`/`formatCr`. Because `formatPct` is already always-signed, a separate `formatSignedPct` is redundant. Use `formatPct` everywhere a signed percentage is needed.

Confirm with a one-liner in the browser console on `/dashboard`:

```
formatPct(null) === '—'   // true
formatPct(0)              // '+0.00%'
formatPct(-1.5)           // '-1.50%'
formatCr(null) === '—'    // true
formatCr(0)               // '₹0.00 Cr'
```

If any of those fail, fix the existing function in-place — do not introduce a new name.

- [ ] **Step 2: Add `formatAbsoluteINR` (the only new helper)**

Append to `frontend/src/utils/formatters.js`:

```js
/** Format an INR amount in lakhs/crores, always signed. Returns '—' for null/NaN. */
export function formatAbsoluteINR(v) {
  if (v == null || Number.isNaN(v)) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : '+'
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(2)} Cr`
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(2)} L`
  return `${sign}₹${abs.toFixed(0)}`
}
```

- [ ] **Step 3: Manual verification**

In the browser dev console on `/dashboard` (or any page that imports formatters), verify:

```
formatAbsoluteINR(null)      → '—'
formatAbsoluteINR(0)         → '+₹0'
formatAbsoluteINR(2_500_000) → '+₹25.00 L'
formatAbsoluteINR(-3.2e7)    → '-₹3.20 Cr'
formatPct(null)              → '—'
formatPct(0)                 → '+0.00%'
formatPct(-1.5)              → '-1.50%'
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/formatters.js
git commit -m "feat(formatters): formatAbsoluteINR helper for KPI tiles"
```

---

## Task 13: `KpiTile` — `tone-neutral` + `tooltip`

**Files:**
- Modify: `frontend/src/components/report/KpiTile.jsx`
- Modify: `frontend/src/components/report/report.css`

- [ ] **Step 1: Update KpiTile**

Open `frontend/src/components/report/KpiTile.jsx`. Replace contents with:

```jsx
export default function KpiTile({ label, value, sublabel, tone = 'neutral', tooltip }) {
  const toneClass = `tone-${tone}`
  const isMissing = value == null || value === '—'
  return (
    <div
      className={`kpi-tile ${toneClass}${isMissing ? ' is-missing' : ''}`}
      title={isMissing && tooltip ? tooltip : (tooltip || undefined)}
    >
      <div className="label">{label}</div>
      <div className="value">{value ?? '—'}</div>
      {sublabel ? <div className="sublabel">{sublabel}</div> : null}
    </div>
  )
}
```

- [ ] **Step 2: CSS**

Open `frontend/src/components/report/report.css`. Append:

```css
.kpi-tile { border-left: 3px solid transparent; }
.kpi-tile.tone-success { border-left-color: #10b981; }
.kpi-tile.tone-gold    { border-left-color: #f59e0b; }
.kpi-tile.tone-danger  { border-left-color: #ef4444; }
.kpi-tile.tone-neutral { border-left-color: #94a3b8; }
.kpi-tile.is-missing .value { color: #94a3b8; font-weight: 500; }
```

- [ ] **Step 3: Manual verification**

Hovering a tile with `value=null` shows the browser tooltip text from the `tooltip` prop.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/report/KpiTile.jsx frontend/src/components/report/report.css
git commit -m "feat(kpi): tone-neutral + tooltip on missing values"
```

---

## Task 14: `KpiRow` — 6-tile responsive grid

**Files:**
- Create: `frontend/src/components/report/KpiRow.jsx`
- Modify: `frontend/src/components/report/report.css`

- [ ] **Step 1: Create KpiRow**

```jsx
// frontend/src/components/report/KpiRow.jsx
import KpiTile from './KpiTile'
import { formatCr, formatPct, formatAbsoluteINR } from '../../utils/formatters'

function driftTone(d) {
  if (d == null) return 'neutral'
  if (d < 5) return 'success'
  if (d < 15) return 'gold'
  return 'danger'
}

function concTone(c) {
  if (c == null) return 'neutral'
  if (c < 25) return 'success'
  if (c < 40) return 'gold'
  return 'danger'
}

function gainTone(g) {
  if (g == null) return 'neutral'
  return g >= 0 ? 'success' : 'danger'
}

function vsNiftyTone(a) {
  if (a == null) return 'neutral'
  return a >= 0 ? 'success' : 'danger'
}

export default function KpiRow({ kpis }) {
  const k = kpis || {}
  const gain = k.absolute_gain || {}
  const gainValue = gain.value
  const gainSublabel = gain.partial
    ? `partial (${(gain.missing_tickers || []).length} missing)`
    : 'since inception'

  return (
    <div className="kpi-row-v2">
      <KpiTile
        label="Portfolio Value"
        value={formatCr(k.portfolio_value_cr)}
        sublabel={k.holdings_count != null ? `${k.holdings_count} holdings` : null}
        tone="neutral"
        tooltip="Sum of qty x current price for all holdings."
      />
      <KpiTile
        label="Absolute Gain"
        value={formatAbsoluteINR(gainValue)}
        sublabel={gainSublabel}
        tone={gainTone(gainValue)}
        tooltip={
          gainValue == null
            ? 'Live prices unavailable for all holdings.'
            : (gain.missing_tickers || []).length
              ? `Excludes: ${gain.missing_tickers.join(', ')}`
              : null
        }
      />
      <KpiTile
        label="XIRR"
        value={formatPct(k.xirr_pct)}
        sublabel="p.a."
        tone="neutral"
        tooltip="Annualised return from your transaction history. Requires at least one buy transaction."
      />
      <KpiTile
        label="vs Nifty (MTD)"
        value={formatPct(k.alpha_pct)}
        sublabel={k.nifty_mtd_pct != null ? `Nifty ${formatPct(k.nifty_mtd_pct)}` : null}
        tone={vsNiftyTone(k.alpha_pct)}
        tooltip="Portfolio MTD return minus Nifty 50 MTD return."
      />
      <KpiTile
        label="Drift"
        value={k.drift_pct != null ? `${k.drift_pct.toFixed(1)}%` : null}
        sublabel="off target"
        tone={driftTone(k.drift_pct)}
        tooltip="Max deviation from target equity/debt/cash allocation for the client's risk profile."
      />
      <KpiTile
        label="Top-3 Concentration"
        value={k.concentration_pct != null ? `${k.concentration_pct.toFixed(1)}%` : null}
        sublabel="of portfolio"
        tone={concTone(k.concentration_pct)}
        tooltip="Weight of the three largest holdings by market value."
      />
    </div>
  )
}
```

- [ ] **Step 2: Grid CSS**

Append to `frontend/src/components/report/report.css`:

```css
.kpi-row-v2 {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin: 16px 0 24px 0;
}

@media (max-width: 1023px) {
  .kpi-row-v2 { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 639px) {
  .kpi-row-v2 { grid-template-columns: repeat(2, 1fr); gap: 8px; }
  .kpi-row-v2 .kpi-tile .value { font-size: 18px; }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/report/KpiRow.jsx frontend/src/components/report/report.css
git commit -m "feat(kpi): 6-tile responsive KpiRow"
```

---

## Task 15: Wire `<KpiRow>` into `ReportPage`

**Files:**
- Modify: `frontend/src/pages/ReportPage.jsx`

- [ ] **Step 1: Replace inline 4-tile block + drop dead local formatters**

Open `frontend/src/pages/ReportPage.jsx`. Import:

```jsx
import KpiRow from '../components/report/KpiRow'
```

Then make three deletions/replacements:

1. **Delete the local formatter helpers at lines 15-27** (`fmtCr`, `fmtPct`, `toneFromPct`) — they are duplicated by `formatPct`/`formatCr` in `frontend/src/utils/formatters.js` and become dead code once `<KpiRow>` owns formatting.
2. **Delete the now-unused KpiTile import on line 5** (`import KpiTile from '../components/report/KpiTile'`) — `KpiRow` imports it itself.
3. **Replace the four-`<KpiTile>` block inside `<div className="kpi-row">…</div>` (lines 190-204)** with:

```jsx
<KpiRow kpis={data?.kpis} />
```

Also delete the local `kpis`, `alphaTone`, `returnTone` derivations at lines 127-129 since `KpiRow` owns all KPI formatting + tone logic.

- [ ] **Step 2: Update skeleton data shape**

The current skeleton (ReportPage.jsx:71-91) puts KPIs under a nested `kpis: {...}` key. Preserve that nesting and add the new keys as `null` inside it:

```jsx
kpis: {
  portfolio_value_cr: null,
  holdings_count: holdings.length,
  return_mtd_pct: null,
  nifty_mtd_pct: null,
  alpha_pct: null,
  absolute_gain: null,
  xirr_pct: null,
  drift_pct: null,
  concentration_pct: null,
},
```

(`<KpiRow>` reads `data?.kpis`, not `data` directly — keep the wrapper.)

- [ ] **Step 3: Manual verification**

Run: `cd frontend && npm run dev`. Open an existing report — six tiles render. Missing-value tiles show `—` with a tooltip on hover.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ReportPage.jsx
git commit -m "feat(report): KpiRow on ReportPage, drop inline 4-tile block"
```

---

## Task 16: `QAScoreBadge` popover with reasons

**Files:**
- Modify: `frontend/src/components/report/QAScoreBadge.jsx`
- Modify: `frontend/src/pages/ReportPage.jsx`
- Modify: `frontend/src/components/report/report.css`

- [ ] **Step 1: Replace QAScoreBadge**

Open `frontend/src/components/report/QAScoreBadge.jsx`. Replace contents with:

```jsx
import { useState } from 'react'
import { Info } from 'lucide-react'

export default function QAScoreBadge({ score, reasons }) {
  const [open, setOpen] = useState(false)
  if (score == null) return null
  const tone = score >= 8 ? 'success' : score >= 7 ? 'gold' : 'danger'
  const reasonList = Array.isArray(reasons) ? reasons.slice(0, 3) : []

  return (
    <div
      className={`qa-badge-wrap qa-tone-${tone}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="qa-badge"
        onClick={() => setOpen((v) => !v)}
      >
        QA · {score}/10 <Info className="w-3 h-3 ml-1 inline" />
      </button>
      {open ? (
        <div className="qa-popover" role="tooltip">
          <div className="qa-popover-header">QA Score · {score}/10</div>
          <div className="qa-popover-sub">Graded by Cohere command-r</div>
          {reasonList.length ? (
            <ul className="qa-popover-reasons">
              {reasonList.map((r, i) => (<li key={i}>{r}</li>))}
            </ul>
          ) : (
            <div className="qa-popover-empty">No reasons recorded.</div>
          )}
          <div className="qa-popover-footer">Auto-regenerates if &lt; 7</div>
        </div>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 2: Use new badge in ReportPage**

Open `frontend/src/pages/ReportPage.jsx`. Import:

```jsx
import QAScoreBadge from '../components/report/QAScoreBadge'
```

Find the inline badge in the header:

```jsx
{data.qa_score != null ? (
  <div className="qa-badge">QA · {data.qa_score}/10</div>
) : null}
```

Replace with:

```jsx
<QAScoreBadge score={data?.qa_score} reasons={data?.qa_reasons} />
```

- [ ] **Step 3: CSS**

Append to `frontend/src/components/report/report.css`:

```css
.qa-badge-wrap { position: relative; display: inline-block; }
.qa-badge {
  background: #ecfdf5; color: #047857; padding: 4px 12px;
  border-radius: 999px; font-size: 13px; font-weight: 600;
  border: none; cursor: pointer;
}
.qa-tone-gold   .qa-badge { background: #fffbeb; color: #b45309; }
.qa-tone-danger .qa-badge { background: #fef2f2; color: #b91c1c; }

.qa-popover {
  position: absolute; top: calc(100% + 8px); right: 0;
  background: white; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 12px 16px; min-width: 280px; max-width: 360px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.08); z-index: 50;
  font-size: 13px; color: #334155;
}
.qa-popover-header { font-weight: 600; color: #0f172a; }
.qa-popover-sub { color: #64748b; font-size: 12px; margin-bottom: 8px; }
.qa-popover-reasons { padding-left: 18px; margin: 8px 0; }
.qa-popover-reasons li { margin: 4px 0; }
.qa-popover-empty { color: #94a3b8; font-style: italic; margin: 8px 0; }
.qa-popover-footer {
  border-top: 1px solid #e2e8f0; padding-top: 8px; margin-top: 8px;
  font-size: 12px; color: #94a3b8;
}
```

- [ ] **Step 4: Manual verification**

Open a report whose `qa_reasons` is populated (generate a fresh one). Hover the badge — popover shows model name and up to 3 reasons.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/report/QAScoreBadge.jsx frontend/src/pages/ReportPage.jsx frontend/src/components/report/report.css
git commit -m "feat(qa): QAScoreBadge popover with Cohere reasons"
```

---

## Task 17: End-to-end smoke check

**Files:** none modified.

- [ ] **Step 1: Backend tests green**

Run: `cd backend && pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Frontend lint green**

Run: `cd frontend && npm run lint`
Expected: no errors.

- [ ] **Step 3: Frontend build green**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Manual smoke**

1. `cd backend && uvicorn main:app --reload`
2. `cd frontend && npm run dev` (separate terminal)
3. Open `http://localhost:5173`, pick any seeded client.
4. Generate a new monthly report.
5. Verify:
   - Six KPI tiles render. Missing data shows `—` with tooltip; not `+0.00%`.
   - Back link "← Back to {ClientName}" appears above the report header.
   - QA badge popover shows model name + reasons on hover.
   - `/config` and `/admin` show "← Back to Dashboard".
   - PDF download still works.

- [ ] **Step 5: Final commit if any polish needed**

```bash
git add -A
git commit -m "fix(report): smoke-test polish"
```

---

## Self-Review

**Spec coverage:**
- ✅ 6 KPIs → Tasks 2-6, 14, 15
- ✅ Back-nav on Report/Config/Admin → Tasks 10, 11
- ✅ QA tooltip with reasons → Tasks 8, 9, 16
- ✅ Zero handling (`None → '—'`) → Tasks 12, 3, 4
- ✅ Risk-profile-derived target → Task 1
- ✅ Migration 001 → Task 7
- ✅ Tests for every analytics function → Tasks 1-5

**Type consistency:**
- `compute_xirr` returns decimal (0.14); `build_report_data` multiplies by 100 → `kpis.xirr_pct` is percent. ✅
- `compute_absolute_gain` returns `{value, partial, missing_tickers}` — `KpiRow` reads all three. ✅
- `compute_drift`/`compute_concentration` return percentage floats — `KpiRow` formats with `.toFixed(1)`. ✅
- `run_qa_check` now returns `{score, reasons}` dict — every call site updated in Task 8. ✅

**Out of scope (v3):**
- `clients.target_allocation` column
- Tax-loss harvesting tile
- Sharpe / max drawdown tiles
- Hindi labels on new KPIs
