import { useState } from 'react';
import { api } from '../../services/api';

const EVENT_TYPES = [
  { value: 'rebalance', label: 'Rebalance' },
  { value: 'cash_deployment', label: 'Cash Deployment' },
  { value: 'tax_harvest', label: 'Tax Harvest' },
  { value: 'liquidity_event', label: 'Liquidity Event' },
  { value: 'external_change', label: 'External Change' },
  { value: 'market_commentary', label: 'Market Commentary' },
];

export default function LogChangeModal({ clientId, onClose, onSuccess }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ event_type: '', title: '', body: '', event_date: today });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  const isValid = form.event_type && form.title.trim() && form.body.trim() && form.event_date;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!isValid) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.logRationaleEvent(clientId, {
        event_type: form.event_type,
        title: form.title.trim(),
        body: form.body.trim(),
        event_date: form.event_date,
      });
      onSuccess();
    } catch (err) {
      setError(err.message ?? 'Failed to log change. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Log a Change</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-red-700 text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Event type *</label>
            <select value={form.event_type} onChange={update('event_type')} required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
              <option value="">Select type…</option>
              {EVENT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Title * <span className="text-gray-400 font-normal">(max 100 chars)</span></label>
            <input type="text" value={form.title} onChange={update('title')} maxLength={100} required
              placeholder="e.g. Equity rebalance — trimmed TCS"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rationale * <span className="text-gray-400 font-normal">(max 500 chars)</span></label>
            <textarea value={form.body} onChange={update('body')} maxLength={500} required rows={4}
              placeholder="Why was this change made?"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none" />
            <p className="text-right text-xs text-gray-400 mt-0.5">{form.body.length}/500</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date *</label>
            <input type="date" value={form.event_date} onChange={update('event_date')} required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50">
              Cancel
            </button>
            <button type="submit" disabled={!isValid || submitting}
              className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">
              {submitting ? 'Saving…' : 'Save change'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
