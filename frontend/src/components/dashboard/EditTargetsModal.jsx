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
