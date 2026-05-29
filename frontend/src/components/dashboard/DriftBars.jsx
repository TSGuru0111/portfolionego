const COLOURS = {
  equity: '#3b82f6',
  debt: '#22c55e',
  gold: '#f59e0b',
  cash: '#64748b',
  alternatives: '#a855f7',
};

function barBgColour(delta, band) {
  const abs = Math.abs(delta);
  if (abs <= band) return 'bg-green-500';
  if (abs <= band * 2) return 'bg-amber-400';
  return 'bg-red-500';
}

function StatusLabel({ delta, band }) {
  const abs = Math.abs(delta);
  if (abs <= band) return <span className="text-green-600 text-xs font-medium">ok ✓</span>;
  const sign = delta > 0 ? '+' : '';
  const icon = abs > band * 2 ? ' ⚠' : '';
  const colour = abs > band * 2 ? 'text-red-600' : 'text-amber-600';
  return <span className={`text-xs font-medium ${colour}`}>{sign}{delta.toFixed(1)}%{icon}</span>;
}

export default function DriftBars({ drift, loading, error }) {
  if (loading) return <div className="h-48 flex items-center justify-center text-gray-400">Loading…</div>;
  if (error) return (
    <div className="text-red-500 text-sm py-4">
      ⚠ {error} <button className="ml-2 underline" onClick={() => window.location.reload()}>Retry</button>
    </div>
  );
  if (!Array.isArray(drift) || drift.length === 0) {
    return <div className="text-gray-400 text-sm py-4">No drift data available</div>;
  }

  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-700 mb-3">Drift Status</h2>
      <div className="space-y-3">
        {drift.map((d) => {
          const actual = Number(d.actual_pct);
          const target = Number(d.target_pct);
          const delta  = Number(d.delta_pct);
          const band   = Number(d.band_pct);
          return (
          <div key={d.asset_class}>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-gray-600 capitalize w-24">{d.asset_class}</span>
              <span className="text-xs text-gray-400">{actual.toFixed(0)}% / {target.toFixed(0)}%</span>
              <StatusLabel delta={delta} band={band} />
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full ${barBgColour(delta, band)}`}
                style={{ width: `${Math.min(Math.max(actual, 0), 100)}%`, backgroundColor: COLOURS[d.asset_class] }}
              />
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}
