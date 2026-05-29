import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function formatMonth(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
}

function formatCr(v) {
  return `₹${(v / 1e7).toFixed(2)} Cr`;
}

export default function NetWorthSparkline({ snapshots, loading, error }) {
  if (loading) return <div className="h-48 flex items-center justify-center text-gray-400">Loading…</div>;
  if (error) return (
    <div className="text-red-500 text-sm py-4">
      ⚠ {error} <button className="ml-2 underline" onClick={() => window.location.reload()}>Retry</button>
    </div>
  );

  if (!Array.isArray(snapshots) || snapshots.length < 2) {
    return (
      <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
        Not enough data yet (need at least 2 snapshots)
      </div>
    );
  }

  const data = [...snapshots]
    .sort((a, b) => new Date(a.as_of) - new Date(b.as_of))
    .map((s) => ({ month: formatMonth(s.as_of), aum: Number(s.net_worth), date: s.as_of }));

  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-700 mb-2">Net Worth (12 months)</h2>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="aumGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#94a3b8' }} />
          <YAxis
            tickFormatter={(v) => `₹${(v / 1e7).toFixed(1)}Cr`}
            tick={{ fontSize: 10, fill: '#94a3b8' }}
            width={60}
          />
          <Tooltip
            formatter={(v) => [formatCr(v), 'Net Worth']}
            labelFormatter={(label, payload) => payload?.[0]?.payload?.date ?? label}
          />
          <Area
            type="monotone"
            dataKey="aum"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#aumGradient)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
