function formatAum(aum) {
  if (!aum && aum !== 0) return '—';
  const cr = aum / 1e7;
  return `₹${cr.toFixed(2)} Cr`;
}

function daysAgo(dateStr) {
  if (!dateStr) return '—';
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
  if (diff === 0) return 'Today';
  if (diff === 1) return '1 day ago';
  return `${diff} days ago`;
}

export default function DashboardKpiStrip({ portfolio, drift, rationaleEvents }) {
  const aum = portfolio?.total_aum;

  const driftBreaches = Array.isArray(drift)
    ? drift.filter((d) => d.status !== 'on_track').length
    : null;

  const lastEvent = Array.isArray(rationaleEvents) && rationaleEvents.length > 0
    ? rationaleEvents[0]
    : null;

  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">AUM</p>
        <p className="text-2xl font-bold text-gray-900">{formatAum(aum)}</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Drift Breaches</p>
        <p className={`text-2xl font-bold ${driftBreaches > 0 ? 'text-red-600' : 'text-green-600'}`}>
          {driftBreaches === null ? '—' : driftBreaches === 0 ? 'All clear ✓' : `${driftBreaches} out of band`}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Last Change</p>
        <p className="text-2xl font-bold text-gray-900">
          {lastEvent ? daysAgo(lastEvent.event_date) : 'None logged'}
        </p>
      </div>
    </div>
  );
}
