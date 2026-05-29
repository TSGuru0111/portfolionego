# Phase 3D — Client Share View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let RMs share a read-only, magic-link dashboard view with clients — no login required, token expires after 7/30/90 days.

**Architecture:** New `share_tokens` DB table + `share_tokens_db.py` layer + `routes/share.py` (public mirror endpoints + protected token CRUD). Frontend adds a public `/share/:token` route (`ClientSharePage.jsx`) that reuses all existing dashboard components, plus a `ShareModal.jsx` on the RM dashboard for link generation.

**Tech Stack:** FastAPI, Supabase (postgrest-py v2), React 18, Tailwind CSS. No new libraries.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/db_schema/migrations/005_share_tokens.sql` | Create | share_tokens table + indexes |
| `backend/db/share_tokens_db.py` | Create | create / get_latest / resolve DB functions |
| `backend/tests/test_share_tokens_db.py` | Create | Unit tests for DB layer (mocked Supabase) |
| `backend/routes/share.py` | Create | Protected token CRUD + 4 public mirror endpoints |
| `backend/tests/test_share_routes.py` | Create | Route tests (mocked DB) |
| `backend/main.py` | Modify | Register share router (protected + public) |
| `frontend/src/components/dashboard/RationaleTimeline.jsx` | Modify | Add `readOnly` prop — hides "+ Log change" button |
| `frontend/src/services/api.js` | Modify | Add `createShareToken`, `getShareToken` |
| `frontend/src/App.jsx` | Modify | Add public `/share/:token` route outside ProtectedRoute |
| `frontend/src/components/dashboard/ShareModal.jsx` | Create | Expiry picker + copy link UI |
| `frontend/src/pages/ClientSharePage.jsx` | Create | Public read-only dashboard page |
| `frontend/src/pages/DashboardPage.jsx` | Modify | Add "Share with client" button + ShareModal state |

---

### Task 1: DB layer — share_tokens

**Files:**
- Create: `backend/db_schema/migrations/005_share_tokens.sql`
- Create: `backend/db/share_tokens_db.py`
- Create: `backend/tests/test_share_tokens_db.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_share_tokens_db.py
"""Tests for backend.db.share_tokens_db (mocked Supabase)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from db.share_tokens_db import create_share_token, get_latest_share_token, resolve_token


def _chain(data):
    res = MagicMock()
    res.data = data
    c = MagicMock()
    for m in ("insert", "select", "eq", "gt", "order", "limit", "single", "is_"):
        getattr(c, m).return_value = c
    c.execute.return_value = res
    return c


def _sb(data):
    sb = MagicMock()
    sb.table.return_value = _chain(data)
    return sb


def test_create_share_token_returns_row():
    row = {"id": "tok-1", "token": "abc-uuid", "client_id": "c1", "expires_at": "2026-06-30T00:00:00+00:00"}
    chain = _chain([row])
    sb = MagicMock()
    sb.table.return_value = chain
    result = create_share_token(sb, client_id="c1", expires_in_days=30, rm_id="rm1")
    assert result["token"] == "abc-uuid"


def test_get_latest_share_token_returns_row():
    row = {"id": "tok-1", "token": "abc-uuid"}
    sb = _sb([row])
    result = get_latest_share_token(sb, "c1")
    assert result["token"] == "abc-uuid"


def test_get_latest_share_token_returns_none_when_empty():
    sb = _sb([])
    assert get_latest_share_token(sb, "c1") is None


def test_resolve_token_valid():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    row = {"id": "tok-1", "client_id": "c1", "token": "abc-uuid", "expires_at": future}
    sb = _sb([row])
    result = resolve_token(sb, "abc-uuid")
    assert result["client_id"] == "c1"


def test_resolve_token_expired_returns_none():
    sb = _sb([])  # expired tokens filtered out by the GT query
    result = resolve_token(sb, "abc-uuid")
    assert result is None


def test_resolve_token_unknown_returns_none():
    sb = _sb([])
    result = resolve_token(sb, "does-not-exist")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/python -m pytest tests/test_share_tokens_db.py -v 2>&1 | tail -10
```
Expected: `ModuleNotFoundError: No module named 'db.share_tokens_db'`

- [ ] **Step 3: Create the migration file**

```sql
-- backend/db_schema/migrations/005_share_tokens.sql
create table share_tokens (
  id               uuid primary key default gen_random_uuid(),
  client_id        uuid not null references clients(id) on delete cascade,
  token            uuid not null default gen_random_uuid() unique,
  expires_at       timestamptz not null,
  created_by_rm_id uuid not null references rms(id),
  created_at       timestamptz not null default now()
);
create index share_tokens_token_idx on share_tokens(token);
create index share_tokens_client_idx on share_tokens(client_id);
```

- [ ] **Step 4: Create the DB layer**

```python
# backend/db/share_tokens_db.py
"""CRUD for share_tokens."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from db.supabase_client import get_supabase

_TABLE = "share_tokens"


def create_share_token(
    sb, *, client_id: str, expires_in_days: int, rm_id: str
) -> dict[str, Any]:
    """Insert a new share token and return the full row."""
    if sb is None:
        sb = get_supabase()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
    row = {
        "client_id": str(client_id),
        "expires_at": expires_at,
        "created_by_rm_id": str(rm_id),
    }
    res = sb.table(_TABLE).insert(row).execute()
    return res.data[0]


def get_latest_share_token(sb, client_id: str) -> dict[str, Any] | None:
    """Return the most recent non-expired token for a client, or None."""
    if sb is None:
        sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", str(client_id))
        .gt("expires_at", now)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def resolve_token(sb, token: str) -> dict[str, Any] | None:
    """Return the token row if it exists and has not expired, else None."""
    if sb is None:
        sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("token", str(token))
        .gt("expires_at", now)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_share_tokens_db.py -v 2>&1 | tail -10
```
Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/db_schema/migrations/005_share_tokens.sql \
        backend/db/share_tokens_db.py \
        backend/tests/test_share_tokens_db.py
git commit -m "feat(phase3d): add share_tokens DB layer and migration"
```

---

### Task 2: Backend share routes + register in main.py

**Files:**
- Create: `backend/routes/share.py`
- Create: `backend/tests/test_share_routes.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing route tests**

```python
# backend/tests/test_share_routes.py
"""Tests for share routes."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _make_client():
    from main import app
    return TestClient(app)


_VALID_TOKEN_ROW = {
    "id": "tok-1",
    "client_id": "c1-uuid",
    "token": "valid-token-uuid",
    "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
}

_PORTFOLIO_DATA = {
    "client": {"id": "c1-uuid", "name": "Test Client"},
    "holdings": [],
    "portfolio_return": None,
    "nifty_return": None,
    "has_stale_prices": False,
    "stale_tickers": [],
}


def test_public_portfolio_valid_token():
    c = _make_client()
    with patch("routes.share.resolve_token", return_value=_VALID_TOKEN_ROW), \
         patch("routes.share.get_client_portfolio", new=AsyncMock(return_value=_PORTFOLIO_DATA)):
        resp = c.get("/share/valid-token-uuid/portfolio")
    assert resp.status_code == 200


def test_public_portfolio_expired_token():
    c = _make_client()
    with patch("routes.share.resolve_token", return_value=None):
        resp = c.get("/share/expired-token/portfolio")
    assert resp.status_code == 403
    assert "expired" in resp.json()["detail"]


def test_public_portfolio_unknown_token():
    c = _make_client()
    with patch("routes.share.resolve_token", return_value=None):
        resp = c.get("/share/unknown-token/portfolio")
    assert resp.status_code == 403


def test_create_token_endpoint():
    c = _make_client()
    new_row = {**_VALID_TOKEN_ROW, "token": "new-token-uuid"}
    with patch("routes.share.create_share_token", return_value=new_row), \
         patch("routes.share.get_supabase", return_value=MagicMock()):
        resp = c.post(
            "/clients/c1-uuid/share-token",
            json={"expires_in_days": 30},
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "share_url" in body


def test_get_token_endpoint_404_when_none():
    c = _make_client()
    with patch("routes.share.get_latest_share_token", return_value=None), \
         patch("routes.share.get_supabase", return_value=MagicMock()):
        resp = c.get(
            "/clients/c1-uuid/share-token",
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_share_routes.py -v 2>&1 | tail -10
```
Expected: errors importing `routes.share`

- [ ] **Step 3: Create `routes/share.py`**

```python
# backend/routes/share.py
"""Share token CRUD (protected) + public mirror endpoints."""
from __future__ import annotations

import os
from datetime import date, datetime, timezone, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from db.share_tokens_db import create_share_token, get_latest_share_token, resolve_token
from db.supabase_client import get_supabase
from db.allocation_targets_db import get_active_target
from db.wealth_snapshots_db import get_latest_snapshot, get_snapshots_range
from db.rationale_events_db import list_rationale_events
from routes.clients import get_client_portfolio
from services.drift_service import compute_drift

_FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
_CLASSES = ("equity", "debt", "gold", "cash", "alternatives")

protected_router = APIRouter()
public_router = APIRouter()


def _current_rm_id(request: Request) -> UUID:
    _DEMO_RM = UUID("00000000-0000-0000-0000-000000000001")
    return _DEMO_RM


def _require_token(token: str) -> dict[str, Any]:
    sb = get_supabase()
    row = resolve_token(sb, token)
    if row is None:
        raise HTTPException(status_code=403, detail="link expired or invalid")
    return row


class ShareTokenBody(BaseModel):
    expires_in_days: int

    @field_validator("expires_in_days")
    @classmethod
    def valid_days(cls, v):
        if v not in (7, 30, 90):
            raise ValueError("expires_in_days must be 7, 30, or 90")
        return v


# ─── Protected ─────────────────────────────────────────────────────────────

@protected_router.post("/{client_id}/share-token")
async def create_token(client_id: UUID, body: ShareTokenBody, request: Request) -> dict[str, Any]:
    rm_id = _current_rm_id(request)
    sb = get_supabase()
    row = create_share_token(sb, client_id=str(client_id), expires_in_days=body.expires_in_days, rm_id=str(rm_id))
    token_val = row["token"]
    return {
        "token": token_val,
        "expires_at": row["expires_at"],
        "share_url": f"{_FRONTEND_BASE_URL}/share/{token_val}",
    }


@protected_router.get("/{client_id}/share-token")
def get_token(client_id: UUID, request: Request) -> dict[str, Any]:
    rm_id = _current_rm_id(request)
    sb = get_supabase()
    row = get_latest_share_token(sb, str(client_id))
    if row is None:
        raise HTTPException(status_code=404, detail="no active share token")
    token_val = row["token"]
    return {
        "token": token_val,
        "expires_at": row["expires_at"],
        "share_url": f"{_FRONTEND_BASE_URL}/share/{token_val}",
    }


# ─── Public ────────────────────────────────────────────────────────────────

@public_router.get("/{token}/portfolio")
async def share_portfolio(token: str) -> dict[str, Any]:
    row = _require_token(token)
    return await get_client_portfolio(row["client_id"])


@public_router.get("/{token}/drift")
def share_drift(token: str) -> list[dict[str, Any]]:
    row = _require_token(token)
    client_id = row["client_id"]
    sb = get_supabase()
    target = get_active_target(sb, client_id)
    if target is None:
        raise HTTPException(status_code=404, detail="no active allocation target")
    snap = get_latest_snapshot(sb, client_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="no snapshot")
    result = compute_drift(
        sb,
        client_id,
        target_pct={cls: str(target.get(f"{cls}_pct", 0)) for cls in _CLASSES},
        band_pct={cls: str(target.get(f"{cls}_band_pct", 5)) for cls in _CLASSES},
        actual_pct=snap.get("allocation_pct", {}),
    )
    return result or []


@public_router.get("/{token}/snapshots")
def share_snapshots(token: str) -> list[dict[str, Any]]:
    row = _require_token(token)
    sb = get_supabase()
    to_date = datetime.now(timezone.utc).date()
    from_date = (datetime.now(timezone.utc) - timedelta(days=365)).date()
    return get_snapshots_range(sb, row["client_id"], from_date, to_date)


@public_router.get("/{token}/rationale-events")
def share_events(token: str) -> list[dict[str, Any]]:
    row = _require_token(token)
    sb = get_supabase()
    return list_rationale_events(sb, row["client_id"], date(2020, 1, 1), date(2099, 1, 1))
```

- [ ] **Step 4: Register both routers in `main.py`**

In `backend/main.py`, find the `# ─── Routers ───` section. Change the import line from:
```python
from routes import admin, auth, clients, config, jobs, reports, wealth  # noqa: E402
```
to:
```python
from routes import admin, auth, clients, config, jobs, reports, wealth, share  # noqa: E402
```

Then add after the existing `app.include_router(wealth.router, ...)` line:
```python
app.include_router(share.protected_router, prefix="/clients", tags=["Share"])
app.include_router(share.public_router, prefix="/share", tags=["Share-Public"])
```

- [ ] **Step 5: Run all backend tests**

```bash
.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5
```
Expected: `186+ passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routes/share.py \
        backend/tests/test_share_routes.py \
        backend/main.py
git commit -m "feat(phase3d): add share routes and register in main.py"
```

---

### Task 3: Frontend foundation — readOnly prop + api methods + public route

**Files:**
- Modify: `frontend/src/components/dashboard/RationaleTimeline.jsx`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add `readOnly` prop to RationaleTimeline**

In `frontend/src/components/dashboard/RationaleTimeline.jsx`:

Change the function signature:
```jsx
export default function RationaleTimeline({ clientId, events, loading, error, onEventLogged, readOnly = false }) {
```

Wrap the `"+ Log change"` button (currently an unwrapped `<button>`):
```jsx
{!readOnly && (
  <button onClick={() => setShowModal(true)}
    className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700">
    + Log change
  </button>
)}
```

Wrap the `LogChangeModal` at the bottom:
```jsx
{!readOnly && showModal && (
  <LogChangeModal
    clientId={clientId}
    onClose={() => setShowModal(false)}
    onSuccess={() => {
      setShowModal(false);
      onEventLogged?.();
    }}
  />
)}
```

- [ ] **Step 2: Add two API methods to `api.js`**

Inside the `api` object, after `putAllocationTarget`, add:

```js
  createShareToken: async (clientId, expiresInDays) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/clients/${clientId}/share-token`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ expires_in_days: expiresInDays }),
      }),
    )
  },

  getShareToken: async (clientId) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/clients/${clientId}/share-token`, { headers }),
    )
  },
```

- [ ] **Step 3: Add public route to `App.jsx`**

Add import at the top of `frontend/src/App.jsx`:
```jsx
import ClientSharePage from './pages/ClientSharePage';
```

Add route **outside** the `<Route element={<ProtectedRoute />}>` wrapper, before the catch-all `*` route:
```jsx
<Route path="/share/:token" element={<ClientSharePage />} />
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/RationaleTimeline.jsx \
        frontend/src/services/api.js \
        frontend/src/App.jsx
git commit -m "feat(phase3d): readOnly prop on RationaleTimeline, share API methods, public route"
```

---

### Task 4: ShareModal component

**Files:**
- Create: `frontend/src/components/dashboard/ShareModal.jsx`

- [ ] **Step 1: Create the component**

```jsx
// frontend/src/components/dashboard/ShareModal.jsx
import { useState, useEffect } from 'react';
import { api } from '../../services/api';

const EXPIRY_OPTIONS = [7, 30, 90];

export default function ShareModal({ clientId, onClose }) {
  const [selectedDays, setSelectedDays] = useState(30);
  const [shareUrl, setShareUrl]         = useState(null);
  const [expiresAt, setExpiresAt]       = useState(null);
  const [generating, setGenerating]     = useState(false);
  const [copied, setCopied]             = useState(false);
  const [error, setError]               = useState(null);

  useEffect(() => {
    api.getShareToken(clientId)
      .then((data) => {
        setShareUrl(data.share_url);
        setExpiresAt(data.expires_at);
      })
      .catch(() => {
        // 404 = no existing token; stay on picker
      });
  }, [clientId]);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const data = await api.createShareToken(clientId, selectedDays);
      setShareUrl(data.share_url);
      setExpiresAt(data.expires_at);
    } catch (err) {
      setError(err.message ?? 'Failed to generate link. Please try again.');
    } finally {
      setGenerating(false);
    }
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function formatExpiry(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Share with client</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-red-700 text-sm">{error}</div>
        )}

        {shareUrl ? (
          <div>
            <p className="text-sm text-gray-600 mb-1">Active link — expires {formatExpiry(expiresAt)}</p>
            <div className="flex gap-2 mb-4">
              <input
                readOnly
                value={shareUrl}
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-700 truncate"
              />
              <button
                onClick={handleCopy}
                className="px-3 py-2 text-sm rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 whitespace-nowrap"
              >
                {copied ? 'Copied ✓' : 'Copy link'}
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-3">Generate a new link to change the expiry.</p>
          </div>
        ) : (
          <p className="text-sm text-gray-600 mb-4">No active link. Generate one below.</p>
        )}

        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Link validity</p>
          <div className="flex gap-2 mb-4">
            {EXPIRY_OPTIONS.map((days) => (
              <button
                key={days}
                type="button"
                onClick={() => setSelectedDays(days)}
                className={`flex-1 py-1.5 text-sm rounded-lg border font-medium transition-colors ${
                  selectedDays === days
                    ? 'bg-blue-600 border-blue-600 text-white'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                {days} days
              </button>
            ))}
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full py-2 text-sm rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {generating ? 'Generating…' : shareUrl ? 'Generate new link' : 'Generate link'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/dashboard/ShareModal.jsx
git commit -m "feat(phase3d): add ShareModal with expiry picker and copy link"
```

---

### Task 5: ClientSharePage — public read-only dashboard

**Files:**
- Create: `frontend/src/pages/ClientSharePage.jsx`

- [ ] **Step 1: Create the page**

```jsx
// frontend/src/pages/ClientSharePage.jsx
import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import DashboardKpiStrip from '../components/dashboard/DashboardKpiStrip';
import AllocationDonut from '../components/dashboard/AllocationDonut';
import DriftBars from '../components/dashboard/DriftBars';
import NetWorthSparkline from '../components/dashboard/NetWorthSparkline';
import RationaleTimeline from '../components/dashboard/RationaleTimeline';

const API = import.meta.env.VITE_API_URL ?? '';

async function publicFetch(path) {
  const res = await fetch(`${API}${path}`);
  if (res.status === 403) throw new Error('expired');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function usePublicAsync(path) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await publicFetch(path));
    } catch (e) {
      setError(e.message ?? 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => { run(); }, [run]);
  return { data, loading, error };
}

export default function ClientSharePage() {
  const { token } = useParams();

  const portfolio = usePublicAsync(`/share/${token}/portfolio`);
  const drift     = usePublicAsync(`/share/${token}/drift`);
  const snapshots = usePublicAsync(`/share/${token}/snapshots`);
  const events    = usePublicAsync(`/share/${token}/rationale-events`);

  const isExpired = [portfolio, drift, snapshots, events].some(
    (s) => s.error === 'expired'
  );

  if (isExpired) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          <p className="text-4xl mb-4">🔒</p>
          <h1 className="text-xl font-semibold text-gray-900 mb-2">Link expired</h1>
          <p className="text-gray-500 text-sm">
            This link has expired or is invalid. Please contact your advisor.
          </p>
        </div>
      </div>
    );
  }

  const clientName = portfolio.data?.client?.name ?? '';

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-700">Portfolionarator</span>
        {clientName && <span className="text-sm text-gray-500">{clientName}</span>}
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        <DashboardKpiStrip
          portfolio={portfolio.data}
          drift={drift.data}
          rationaleEvents={events.data}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-6">
            <AllocationDonut
              drift={drift.data}
              loading={drift.loading}
              error={drift.error}
            />
            <DriftBars
              drift={drift.data}
              loading={drift.loading}
              error={drift.error}
            />
          </div>

          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <NetWorthSparkline
              snapshots={snapshots.data}
              loading={snapshots.loading}
              error={snapshots.error}
            />
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <RationaleTimeline
            clientId={null}
            events={events.data}
            loading={events.loading}
            error={events.error}
            readOnly={true}
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ClientSharePage.jsx
git commit -m "feat(phase3d): add ClientSharePage public read-only dashboard"
```

---

### Task 6: Wire ShareModal into DashboardPage

**Files:**
- Modify: `frontend/src/pages/DashboardPage.jsx`

- [ ] **Step 1: Add ShareModal import and state**

Make four targeted changes to `frontend/src/pages/DashboardPage.jsx`:

**1. Add import** after the `EditTargetsModal` import line:
```jsx
import ShareModal from '../components/dashboard/ShareModal';
```

**2. Add state** after the `showEditTargets` line:
```jsx
const [showShare, setShowShare] = useState(false);
```

**3. Add "Share with client" button** in the top bar div, between the `← {clientName}` Link and the `"Generate report →"` Link:
```jsx
<button
  onClick={() => setShowShare(true)}
  className="text-sm px-3 py-1.5 rounded-lg border border-blue-600 text-blue-600 font-medium hover:bg-blue-50"
>
  Share with client
</button>
```

**4. Add ShareModal render** after the `EditTargetsModal` block at the bottom of the JSX:
```jsx
{showShare && (
  <ShareModal
    clientId={id}
    onClose={() => setShowShare(false)}
  />
)}
```

- [ ] **Step 2: Verify end-to-end in browser**

```bash
cd frontend && npm run dev
```

1. Go to any client dashboard → "Share with client" button appears in top bar
2. Click it → modal opens; if no token exists shows "No active link"
3. Select 30 days → "Generate link" → share URL appears with Copy button
4. Click "Copy link" → button shows "Copied ✓" for 2 seconds
5. Open the copied URL in an incognito tab → `/share/<token>` loads the read-only dashboard
6. Confirm: no "Edit targets" button, no "+ Log change" button in timeline
7. All 4 panels (KPI, donut/drift, sparkline, timeline) load correctly

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DashboardPage.jsx
git commit -m "feat(phase3d): wire ShareModal into DashboardPage top bar"
```

---

## Final verification

- [ ] All backend tests pass: `cd backend && .venv/bin/python -m pytest --tb=short -q`
- [ ] Share URL opens without login and shows read-only dashboard
- [ ] No "Edit targets" or "+ Log change" buttons on share page
- [ ] Expired/unknown token URL shows full-page "Link expired" message
- [ ] "Share with client" button generates and copies the link correctly

```bash
git log --oneline -8
```
Expected: 6 commits covering tasks 1–6.
