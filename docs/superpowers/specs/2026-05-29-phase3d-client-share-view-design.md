# Phase 3D — Client-Facing Read-Only Dashboard (Share Link)

**Status:** Approved for implementation
**Date:** 2026-05-29
**Depends on:** Phase 3B (`2026-05-29-phase3b-rm-dashboard-design.md`), Phase 3C (`2026-05-29-phase3c-edit-allocation-targets-design.md`)

---

## 1. Purpose

Phase 3D lets the RM share a read-only view of a client's dashboard via a magic link. The client opens the URL in any browser — no login required — and sees their AUM, allocation, drift status, net worth trend, and rationale timeline. The RM controls how long the link stays valid (7 / 30 / 90 days).

**Lead outcomes:**
- RM can share a live portfolio view with the client in one click
- Client sees the same dashboard panels as the RM (minus editing controls)
- Links expire automatically; RM can generate a fresh one at any time
- No client account or login required

---

## 2. Design Decisions

| # | Question | Decision |
|---|----------|----------|
| Q1 | How does client access the view? | Magic link with UUID token — no login |
| Q2 | What does client see? | Full dashboard panels minus "Edit targets" and "Log change" controls |
| Q3 | Token expiry | RM chooses 7 / 30 / 90 days when generating the link |
| Q4 | Backend pattern | Public mirror endpoints under `/share/{token}/...` — validate token, return same data as private routes |
| Q5 | New backend infra? | 1 migration, 1 route file, 1 DB layer file |
| Q6 | Frontend pattern | New public route `/share/:token` outside `ProtectedRoute` |

---

## 3. Backend

### 3.1 Migration — `005_share_tokens.sql`

```sql
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

One active token per client is not enforced at the DB level — the backend always creates a new one and the RM sees the latest.

### 3.2 DB Layer — `backend/db/share_tokens_db.py`

| Function | Description |
|----------|-------------|
| `create_share_token(sb, client_id, expires_in_days, rm_id)` | Insert new token row, return full row |
| `get_latest_share_token(sb, client_id)` | Return most recent non-expired token for this client, or None |
| `resolve_token(sb, token)` | Return row if token exists and `expires_at > now()`, else None |

### 3.3 Routes — `backend/routes/share.py`

**Protected (RM only):**

`POST /clients/{client_id}/share-token`
- Body: `{ "expires_in_days": 7 | 30 | 90 }`
- Creates new token row, returns `{ token, expires_at, share_url }`
- `share_url` = `{FRONTEND_BASE_URL}/share/{token}`

`GET /clients/{client_id}/share-token`
- Returns latest non-expired token for this client: `{ token, expires_at, share_url }` or 404

**Public (no auth):**

`GET /share/{token}/portfolio` → validates token → calls existing portfolio logic for `client_id`
`GET /share/{token}/drift`     → validates token → calls existing drift logic
`GET /share/{token}/snapshots` → validates token → calls existing snapshots logic (last 12)
`GET /share/{token}/rationale-events` → validates token → calls existing rationale events logic

All public endpoints return `403 { "detail": "link expired or invalid" }` if token is missing, expired, or malformed.

`FRONTEND_BASE_URL` is read from env var `FRONTEND_BASE_URL` (default: `http://localhost:5173`).

### 3.4 Register Routes

In `backend/main.py`, register the share router:
- Protected routes (`POST/GET /clients/{id}/share-token`) under the existing auth middleware
- Public routes (`GET /share/{token}/...`) without auth middleware, as a separate router prefix

---

## 4. Frontend

### 4.1 File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/pages/ClientSharePage.jsx` | Create | Public page — 4 fetches by token, full dashboard layout, read-only |
| `frontend/src/components/dashboard/ShareModal.jsx` | Create | Expiry picker + copy link UI |
| `frontend/src/components/dashboard/RationaleTimeline.jsx` | Modify | Add `readOnly` prop — hides "+ Log change" button when true |
| `frontend/src/pages/DashboardPage.jsx` | Modify | Add "Share with client" button + ShareModal state |
| `frontend/src/services/api.js` | Modify | Add `createShareToken`, `getShareToken` |
| `frontend/src/App.jsx` | Modify | Add public `/share/:token` route outside ProtectedRoute |

### 4.2 ClientSharePage

- Route: `/share/:token` — outside `ProtectedRoute`, accessible without login
- Reads `token` from `useParams()`
- Makes 4 parallel fetches using plain `fetch` with no auth header:
  - `GET /share/{token}/portfolio`
  - `GET /share/{token}/drift`
  - `GET /share/{token}/snapshots`
  - `GET /share/{token}/rationale-events`
- If any fetch returns 403: entire page shows full-screen error message — `"This link has expired or is invalid. Please contact your advisor."`
- Otherwise renders the same two-column layout as `DashboardPage`:
  - `DashboardKpiStrip` (portfolio, drift, events data)
  - `AllocationDonut` + `DriftBars` (drift data, left column)
  - `NetWorthSparkline` (snapshots data, right column)
  - `RationaleTimeline` with `readOnly={true}` (events data, full width)
- Top bar: `"Portfolionarator"` text on left, client name on right — no navigation links, no edit buttons
- No `EditTargetsModal`, no "Edit targets" button

### 4.3 RationaleTimeline — readOnly prop

Add `readOnly = false` default prop. When `readOnly` is `true`, do not render the `"+ Log change"` button and do not render `LogChangeModal`. Existing `DashboardPage` usage is unaffected (no prop passed → defaults to false).

### 4.4 ShareModal

Props: `clientId` (string), `onClose` (function)

Behaviour:
1. On mount: `GET /clients/{id}/share-token` → if valid token exists, display the share URL with expiry date and Copy button immediately
2. Shows 3 expiry option buttons: **7 days**, **30 days**, **90 days** (default: 30 days selected)
3. "Generate new link" button → `POST /clients/{id}/share-token` with selected days → displays full URL + Copy button
4. Copy button: `navigator.clipboard.writeText(url)` → button text changes to `"Copied ✓"` for 2 seconds, then reverts
5. On POST error: inline error message inside modal

### 4.5 DashboardPage changes

- Add `"Share with client"` button in the top bar between the `"← clientName"` link and the `"Generate report →"` button
- Add `showShare` boolean state (`useState(false)`)
- Render `<ShareModal clientId={id} onClose={() => setShowShare(false)} />` when `showShare` is true

### 4.6 API methods (api.js)

```js
createShareToken: async (clientId, expiresInDays) => {
  const headers = await authHeader()
  return jsonOrThrow(await fetch(`${API}/clients/${clientId}/share-token`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ expires_in_days: expiresInDays }),
  }))
},

getShareToken: async (clientId) => {
  const headers = await authHeader()
  return jsonOrThrow(await fetch(`${API}/clients/${clientId}/share-token`, { headers }))
},
```

Public fetches in `ClientSharePage` use plain `fetch` with no auth header — no api object method needed.

---

## 5. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Token expired or not found | Full-page error: "This link has expired or is invalid. Please contact your advisor." |
| Individual panel fetch fails (non-403) | Per-panel error with Retry (same as RM dashboard) |
| POST share-token fails | Inline error in ShareModal |
| GET share-token returns 404 (no existing token) | ShareModal shows expiry picker only — no pre-filled URL |

---

## 6. Backend Tests

| Test | File | What it verifies |
|------|------|-----------------|
| `test_create_share_token_returns_row` | `tests/test_share_tokens_db.py` | Inserts row, returns token + expiry |
| `test_resolve_token_valid` | `tests/test_share_tokens_db.py` | Returns row when token exists and not expired |
| `test_resolve_token_expired` | `tests/test_share_tokens_db.py` | Returns None when expires_at is in the past |
| `test_resolve_token_unknown` | `tests/test_share_tokens_db.py` | Returns None when token not found |
| `test_public_portfolio_valid_token` | `tests/test_share_routes.py` | 200 when token valid |
| `test_public_portfolio_expired_token` | `tests/test_share_routes.py` | 403 when token expired |
| `test_public_portfolio_unknown_token` | `tests/test_share_routes.py` | 403 when token not found |
| `test_create_token_endpoint` | `tests/test_share_routes.py` | POST returns token + share_url with correct expiry |
| `test_get_token_endpoint_404_when_none` | `tests/test_share_routes.py` | 404 when no active token exists |

---

## 7. Out of Scope (Deferred)

- Revoking a share token from the dashboard
- Listing all active share tokens for a client
- Client-facing annotations or comments on the timeline
- Email delivery of the share link (RM copies and sends manually)
- Mobile-responsive layout for the share page
