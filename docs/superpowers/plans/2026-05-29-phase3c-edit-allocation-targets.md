# Phase 3C — Edit Allocation Targets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Edit targets" modal to the RM Dashboard so the RM can change a client's allocation targets in-place using preset buttons + sliders.

**Architecture:** Three focused changes — two new API methods on the `api` object, one new `EditTargetsModal` component, and small additions to `DashboardPage.jsx` (one more `useAsync` fetch + modal state). On save, `drift.refetch()` triggers a live update of the donut and drift bars.

**Tech Stack:** React 18, Tailwind CSS, existing `api` object (`frontend/src/services/api.js`), existing `useAsync` hook in `DashboardPage.jsx`. No backend changes.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/services/api.js` | Modify | Add `getAllocationTarget` and `putAllocationTarget` to the `api` object |
| `frontend/src/components/dashboard/EditTargetsModal.jsx` | Create | Preset picker, 5 sliders, 5 band inputs, rationale, submit |
| `frontend/src/pages/DashboardPage.jsx` | Modify | Add target fetch, `showEditTargets` state, "Edit targets" button, render modal |

---

### Task 1: Add API methods

**Files:**
- Modify: `frontend/src/services/api.js` (after line 344, inside the `api` object)

- [ ] **Step 1: Read the end of the `api` object in `api.js`**

Run:
```bash
tail -20 frontend/src/services/api.js
```
Confirm the file ends with `}` closing the `api` object and an export.

- [ ] **Step 2: Add two new methods to the `api` object**

Find the closing `}` of the `// ─── RM Dashboard ───` section (after the `logRationaleEvent` method, around line 344) and add the two new methods before the closing `}` of the `api` object:

```js
  getAllocationTarget: async (clientId) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/clients/${clientId}/allocation-target`, { headers }),
    )
  },

  putAllocationTarget: async (clientId, body) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/clients/${clientId}/allocation-target`, {
        method: 'PUT',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    )
  },
```

- [ ] **Step 3: Verify no syntax errors**

```bash
node -e "require('fs').readFileSync('frontend/src/services/api.js','utf8')" && echo "OK"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat(phase3c): add getAllocationTarget and putAllocationTarget API methods"
```

---

### Task 2: Create EditTargetsModal

**Files:**
- Create: `frontend/src/components/dashboard/EditTargetsModal.jsx`

- [ ] **Step 1: Create the component**

```jsx
// frontend/src/components/dashboard/EditTargetsModal.jsx
import { useState } from 'react';
import { api } from '../../services/api';

const CLASSES = ['equity', 'debt', 'gold', 'cash', 'alternatives'];

const COLOURS = {
  equity: '#3b82f6',
  debt: '#22c55e',
  gold: '#f59e0b',
  cash: '#64748b',
  alternatives: '#a855f7',
};

const PRESETS = {
  Conservative: { equity: 20, debt: 50, gold: 10, cash: 15, alternatives: 5 },
  Moderate:     { equity: 40, debt: 35, gold: 10, cash: 10, alternatives: 5 },
  Aggressive:   { equity: 65, debt: 15, gold:  8, cash:  7, alternatives: 5 },
};

const DEFAULT_BANDS = { equity: 5, debt: 5, gold: 2, cash: 3, alternatives: 3 };

function initTargets(currentTarget) {
  if (!currentTarget) return { ...PRESETS.Moderate };
  return {
    equity:       Number(currentTarget.equity_pct)       || PRESETS.Moderate.equity,
    debt:         Number(currentTarget.debt_pct)         || PRESETS.Moderate.debt,
    gold:         Number(currentTarget.gold_pct)         || PRESETS.Moderate.gold,
    cash:         Number(currentTarget.cash_pct)         || PRESETS.Moderate.cash,
    alternatives: Number(currentTarget.alternatives_pct) || PRESETS.Moderate.alternatives,
  };
}

function initBands(currentTarget) {
  if (!currentTarget) return { ...DEFAULT_BANDS };
  return {
    equity:       Number(currentTarget.equity_band_pct)       || DEFAULT_BANDS.equity,
    debt:         Number(currentTarget.debt_band_pct)         || DEFAULT_BANDS.debt,
    gold:         Number(currentTarget.gold_band_pct)         || DEFAULT_BANDS.gold,
    cash:         Number(currentTarget.cash_band_pct)         || DEFAULT_BANDS.cash,
    alternatives: Number(currentTarget.alternatives_band_pct) || DEFAULT_BANDS.alternatives,
  };
}

export default function EditTargetsModal({ clientId, currentTarget, onClose, onSuccess }) {
  const [targets, setTargets]         = useState(() => initTargets(currentTarget));
  const [bands, setBands]             = useState(() => initBands(currentTarget));
  const [rationale, setRationale]     = useState('');
  const [riskProfile, setRiskProfile] = useState('Moderate');
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState(null);

  const total = CLASSES.reduce((s, c) => s + (Number(targets[c]) || 0), 0);
  const bandInvalid = CLASSES.some((c) => Number(bands[c]) > 20);
  const isValid = total === 100 && !bandInvalid && rationale.trim().length > 0;

  function applyPreset(name) {
    setRiskProfile(name);
    setTargets({ ...PRESETS[name] });
  }

  function setTarget(cls, val) {
    setTargets((t) => ({ ...t, [cls]: Number(val) }));
  }

  function setBand(cls, val) {
    setBands((b) => ({ ...b, [cls]: Number(val) }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!isValid) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.putAllocationTarget(clientId, {
        risk_profile: riskProfile,
        target_pct: Object.fromEntries(CLASSES.map((c) => [c, String(targets[c])])),
        band_pct:   Object.fromEntries(CLASSES.map((c) => [c, String(bands[c])])),
        rationale_text: rationale.trim(),
      });
      onSuccess();
    } catch (err) {
      setError(err.message ?? 'Failed to save targets. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Edit Allocation Targets</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-red-700 text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Preset buttons */}
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Risk profile preset</p>
            <div className="flex gap-2">
              {Object.keys(PRESETS).map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => applyPreset(name)}
                  className={`flex-1 py-1.5 text-sm rounded-lg border font-medium transition-colors ${
                    riskProfile === name
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>

          {/* Sliders */}
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Target allocation</p>
            <div className="space-y-3">
              {CLASSES.map((cls) => (
                <div key={cls}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="flex items-center gap-1.5 text-sm text-gray-700 capitalize">
                      <span
                        className="w-2.5 h-2.5 rounded-full inline-block"
                        style={{ backgroundColor: COLOURS[cls] }}
                      />
                      {cls}
                    </span>
                    <span className="text-sm font-semibold text-gray-900 w-10 text-right">{targets[cls]}%</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={1}
                    value={targets[cls]}
                    onChange={(e) => setTarget(cls, e.target.value)}
                    className="w-full accent-blue-600"
                  />
                </div>
              ))}
            </div>
            <p className={`text-right text-sm font-semibold mt-2 ${total === 100 ? 'text-green-600' : 'text-red-600'}`}>
              Total: {total}%{total !== 100 && ' (must be 100%)'}
            </p>
          </div>

          {/* Band inputs */}
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Band tolerance (±%)</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {CLASSES.map((cls) => (
                <div key={cls}>
                  <label className="block text-xs text-gray-600 capitalize mb-0.5">{cls}</label>
                  <input
                    type="number"
                    min={0}
                    max={20}
                    step={0.5}
                    value={bands[cls]}
                    onChange={(e) => setBand(cls, e.target.value)}
                    className={`w-full border rounded-lg px-2 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 ${
                      Number(bands[cls]) > 20 ? 'border-red-400' : 'border-gray-300'
                    }`}
                  />
                </div>
              ))}
            </div>
            {bandInvalid && (
              <p className="text-xs text-red-600 mt-1">Band values must be 20% or less.</p>
            )}
          </div>

          {/* Rationale */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rationale * <span className="text-gray-400 font-normal">(max 500 chars)</span>
            </label>
            <textarea
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              maxLength={500}
              required
              rows={3}
              placeholder="Why are you changing the targets?"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <p className="text-right text-xs text-gray-400 mt-0.5">{rationale.length}/500</p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isValid || submitting}
              className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Saving…' : 'Save targets'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the file was created**

```bash
wc -l frontend/src/components/dashboard/EditTargetsModal.jsx
```
Expected: ~160 lines.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/EditTargetsModal.jsx
git commit -m "feat(phase3c): add EditTargetsModal with presets, sliders, and band inputs"
```

---

### Task 3: Wire EditTargetsModal into DashboardPage

**Files:**
- Modify: `frontend/src/pages/DashboardPage.jsx`

- [ ] **Step 1: Replace the full contents of `DashboardPage.jsx`**

```jsx
// frontend/src/pages/DashboardPage.jsx
import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import DashboardKpiStrip from '../components/dashboard/DashboardKpiStrip';
import AllocationDonut from '../components/dashboard/AllocationDonut';
import DriftBars from '../components/dashboard/DriftBars';
import NetWorthSparkline from '../components/dashboard/NetWorthSparkline';
import RationaleTimeline from '../components/dashboard/RationaleTimeline';
import EditTargetsModal from '../components/dashboard/EditTargetsModal';

function useAsync(fn, deps) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fn();
      setData(result);
    } catch (e) {
      setError(e.message ?? 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { run(); }, [run]);
  return { data, loading, error, refetch: run };
}

export default function DashboardPage() {
  const { id } = useParams();

  const portfolio = useAsync(() => api.getPortfolio(id), [id]);
  const drift     = useAsync(() => api.getDrift(id), [id]);
  const snapshots = useAsync(() => api.getSnapshots(id, 12), [id]);
  const events    = useAsync(() => api.getRationaleEvents(id), [id]);
  const target    = useAsync(() => api.getAllocationTarget(id), [id]);

  const [showEditTargets, setShowEditTargets] = useState(false);

  const clientName = portfolio.data?.client?.name ?? 'Client';

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <Link to={`/clients/${id}`} className="text-blue-600 hover:underline text-sm flex items-center gap-1">
          ← {clientName}
        </Link>
        <Link
          to={`/clients/${id}/report/new`}
          className="text-sm px-3 py-1.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700"
        >
          Generate report →
        </Link>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* KPI Strip */}
        <DashboardKpiStrip
          portfolio={portfolio.data}
          drift={drift.data}
          rationaleEvents={events.data}
        />

        {/* Two-column grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Left: Donut + Drift + Edit targets button */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-6">
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-400">Allocation vs target</span>
              <button
                onClick={() => setShowEditTargets(true)}
                className="text-xs px-3 py-1.5 rounded-lg border border-blue-600 text-blue-600 font-medium hover:bg-blue-50"
              >
                Edit targets
              </button>
            </div>
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

          {/* Right: Sparkline */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <NetWorthSparkline
              snapshots={snapshots.data}
              loading={snapshots.loading}
              error={snapshots.error}
            />
          </div>
        </div>

        {/* Full-width Timeline */}
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <RationaleTimeline
            clientId={id}
            events={events.data}
            loading={events.loading}
            error={events.error}
            onEventLogged={events.refetch}
          />
        </div>
      </div>

      {/* Edit targets modal */}
      {showEditTargets && (
        <EditTargetsModal
          clientId={id}
          currentTarget={target.data}
          onClose={() => setShowEditTargets(false)}
          onSuccess={() => {
            setShowEditTargets(false);
            drift.refetch();
            target.refetch();
            events.refetch();
          }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Start the dev server and test manually**

```bash
cd frontend && npm run dev
```

1. Navigate to any client dashboard (`/clients/<id>/dashboard`)
2. Verify "Edit targets" button appears in the left panel header
3. Click it — modal opens pre-filled with the current target values
4. Click "Moderate" preset — sliders snap to 40/35/10/10/5, total shows 100% in green
5. Drag one slider so total ≠ 100 — "Save targets" becomes disabled, total shows red
6. Fix total back to 100, add rationale text — "Save targets" enables
7. Submit — modal closes; donut and drift bars refresh
8. Open modal again — pre-filled with the newly saved values
9. Open modal, click Cancel — nothing changes

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DashboardPage.jsx
git commit -m "feat(phase3c): wire EditTargetsModal into DashboardPage"
```

---

## Final verification

- [ ] "Edit targets" button visible in left panel on dashboard
- [ ] Modal opens with correct pre-filled values from current target
- [ ] Preset buttons auto-fill all 5 sliders; total shows 100% in green
- [ ] Submit disabled when total ≠ 100 or rationale empty or band > 20
- [ ] After save: donut + drift bars refresh, timeline gets new `target_change` event
- [ ] Cancel closes modal without saving
- [ ] Error shown inline if PUT fails

```bash
git log --oneline -5
```

Expected three commits: API methods → EditTargetsModal → DashboardPage wiring.
