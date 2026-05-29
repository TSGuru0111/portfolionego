import { useState } from 'react';
import LogChangeModal from './LogChangeModal';

const TYPE_COLOURS = {
  rebalance: 'bg-blue-500',
  cash_deployment: 'bg-green-500',
  tax_harvest: 'bg-emerald-500',
  liquidity_event: 'bg-red-500',
  external_change: 'bg-amber-400',
  market_commentary: 'bg-slate-400',
};

function truncate(str, n) {
  if (!str) return '';
  return str.length > n ? str.slice(0, n) + '…' : str;
}

export default function RationaleTimeline({ clientId, events, loading, error, onEventLogged }) {
  const [showModal, setShowModal] = useState(false);

  const sorted = Array.isArray(events)
    ? [...events].sort((a, b) => new Date(b.event_date) - new Date(a.event_date))
    : [];

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-sm font-semibold text-gray-700">Rationale Timeline</h2>
        <button onClick={() => setShowModal(true)}
          className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700">
          + Log change
        </button>
      </div>

      {loading && <div className="text-gray-400 text-sm py-4">Loading…</div>}
      {error && (
        <div className="text-red-500 text-sm py-4">
          ⚠ {error} <button className="ml-2 underline" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {!loading && !error && sorted.length === 0 && (
        <div className="text-gray-400 text-sm py-4">No changes logged yet</div>
      )}

      {!loading && !error && sorted.length > 0 && (
        <div className="max-h-96 overflow-y-auto space-y-3 pr-1">
          {sorted.map((ev) => (
            <div key={ev.id} className="flex gap-3 items-start">
              <span className={`mt-1.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${TYPE_COLOURS[ev.event_type] ?? 'bg-gray-400'}`} />
              <div>
                <p className="text-xs text-gray-400">
                  {ev.event_date} · <span className="capitalize">{(ev.event_type ?? '').replace(/_/g, ' ')}</span>
                </p>
                <p className="text-sm font-medium text-gray-800">{ev.title}</p>
                {ev.body && <p className="text-xs text-gray-500 mt-0.5">{truncate(ev.body, 80)}</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <LogChangeModal
          clientId={clientId}
          onClose={() => setShowModal(false)}
          onSuccess={() => {
            setShowModal(false);
            onEventLogged?.();
          }}
        />
      )}
    </div>
  );
}
