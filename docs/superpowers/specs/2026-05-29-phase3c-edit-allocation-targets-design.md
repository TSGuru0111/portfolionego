# Phase 3C — Edit Allocation Targets from RM Dashboard

**Status:** Approved for implementation
**Date:** 2026-05-29
**Depends on:** Phase 3B (`2026-05-29-phase3b-rm-dashboard-design.md`)

---

## 1. Purpose

Phase 3B built the RM Dashboard. Phase 3C lets the RM change a client's allocation targets directly from that dashboard — without leaving the page. The RM sees the current drift state, clicks "Edit targets", adjusts the sliders, and the donut + drift bars update immediately after saving.

**Lead outcomes:**
- RM can set a new target allocation in under 60 seconds from the dashboard
- Risk profile presets (Conservative / Moderate / Aggressive) reduce input errors
- Every target change automatically creates a rationale event + wealth snapshot (existing backend behaviour)
- No new backend work — `PUT /clients/{id}/allocation-target` already exists

---

## 2. Design Decisions

| # | Question | Decision |
|---|----------|----------|
| Q1 | Where does the edit flow live? | Modal on the RM Dashboard, triggered from the left panel |
| Q2 | UI for target %? | Sliders (0–100) with live sum counter |
| Q3 | UI for band tolerance? | Number inputs (step 0.5, max 20) |
| Q4 | Risk profile presets? | Yes — Conservative / Moderate / Aggressive auto-fill sliders |
| Q5 | New backend needed? | None — `PUT /clients/{id}/allocation-target` already handles event + target + snapshot atomically |
| Q6 | How does dashboard refresh? | `drift.refetch()` after successful PUT (drift and donut share one fetch) |

---

## 3. Risk Profile Presets

| Class | Conservative | Moderate | Aggressive |
|-------|-------------|---------|------------|
| Equity | 20% | 40% | 65% |
| Debt | 50% | 35% | 15% |
| Gold | 10% | 10% | 8% |
| Cash | 15% | 10% | 7% |
| Alternatives | 5% | 5% | 5% |
| **Total** | **100%** | **100%** | **100%** |

Default bands (pre-filled from current target, fallback to these defaults):

| Class | Default band |
|-------|-------------|
| Equity | 5% |
| Debt | 5% |
| Gold | 2% |
| Cash | 3% |
| Alternatives | 3% |

---

## 4. Component Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/components/dashboard/EditTargetsModal.jsx` | Create | Preset picker, 5 sliders, 5 band inputs, rationale textarea, submit |
| `frontend/src/pages/DashboardPage.jsx` | Modify | Add `getAllocationTarget` fetch; pass `target.data` + `drift.refetch` to left panel area |
| `frontend/src/services/api.js` | Modify | Add `getAllocationTarget(clientId)` and `putAllocationTarget(clientId, body)` to `api` object |

---

## 5. EditTargetsModal Specification

### 5.1 Props

| Prop | Type | Description |
|------|------|-------------|
| `clientId` | string | Client UUID |
| `currentTarget` | object\|null | Active target row from `GET /clients/{id}/allocation-target` |
| `onClose` | function | Called on Cancel or backdrop click |
| `onSuccess` | function | Called after successful PUT; DashboardPage calls `drift.refetch()` in response |

### 5.2 Initial State

When `currentTarget` is provided, pre-fill sliders and band inputs from it. When null (no target set yet), pre-fill from Moderate preset defaults.

### 5.3 Form Fields

**Preset buttons** — three buttons in a row: `Conservative`, `Moderate`, `Aggressive`. Clicking one sets all 5 slider values to the preset values from §3. Does not affect band inputs.

**Sliders** — one per asset class, range 0–100, step 1. Displayed with the class name, current % value, and a coloured dot (same colour map as AllocationDonut/DriftBars).

**Sum indicator** — shown below the sliders: `Total: XX%`. Red text + disabled submit when ≠ 100.

**Band inputs** — one per asset class, `<input type="number">` min=0 max=20 step=0.5. Label: `Equity band ±X%`. Highlighted red if value > 20.

**Rationale textarea** — required, max 500 chars, char count shown. Placeholder: `Why are you changing the targets?`

**Submit button** — label `Save targets`. Disabled when:
- Sum of sliders ≠ 100, OR
- Any band > 20, OR
- Rationale is empty, OR
- Submitting in progress

### 5.4 Submit Payload

```
PUT /clients/{id}/allocation-target
{
  risk_profile: "Conservative" | "Moderate" | "Aggressive",  // nearest preset or last selected
  target_pct: { equity, debt, gold, cash, alternatives },    // Decimal strings
  band_pct:   { equity, debt, gold, cash, alternatives },    // Decimal strings
  rationale_text: "..."
}
```

`risk_profile` is set to whichever preset button was last clicked, or `"Moderate"` if the RM adjusted sliders manually without clicking a preset.

### 5.5 Entry Point on Dashboard

Add an `"Edit targets"` button to the header of the left panel card (the card that contains `AllocationDonut` + `DriftBars`). Style: small outlined blue button, same pattern as the `"+ Log change"` button in `RationaleTimeline`.

---

## 6. DashboardPage Changes

Add a fifth `useAsync` call:

```js
const target = useAsync(() => api.getAllocationTarget(id), [id]);
```

Pass `target.data` as `currentTarget` prop to `EditTargetsModal`.
Pass `drift.refetch` as `onSuccess` (after the modal calls it, drift + donut re-render with new targets).

The "Edit targets" button lives in the left panel card header. `DashboardPage` manages `showEditTargets` boolean state to open/close the modal.

---

## 7. API Methods (api.js)

```js
async getAllocationTarget(clientId) {
  const res = await fetch(`/clients/${clientId}/allocation-target`, { headers: authHeader() });
  return jsonOrThrow(res);
},

async putAllocationTarget(clientId, body) {
  const res = await fetch(`/clients/${clientId}/allocation-target`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify(body),
  });
  return jsonOrThrow(res);
},
```

---

## 8. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| `GET allocation-target` fails | Modal opens with Moderate preset defaults; no error shown to RM |
| `PUT` fails | Inline error banner inside modal; modal stays open |
| Sum ≠ 100 | Submit disabled; sum shown in red |
| Band > 20% | Input border red; submit disabled |
| No rationale | Submit disabled |

---

## 9. Out of Scope (Deferred)

- Deleting / reverting to a previous target
- Viewing full target history from the dashboard (available via API; Phase 3D)
- Per-class risk profile customisation beyond the three presets
- Mobile-responsive layout for the sliders
