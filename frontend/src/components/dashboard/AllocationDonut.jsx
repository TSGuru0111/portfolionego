// frontend/src/components/dashboard/AllocationDonut.jsx
import { PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer } from 'recharts';

const COLOURS = {
  equity: '#3b82f6',
  debt: '#22c55e',
  gold: '#f59e0b',
  cash: '#64748b',
  alternatives: '#a855f7',
};

function buildSlices(drift) {
  if (!Array.isArray(drift) || drift.length === 0) return { actual: [], target: [] };
  const actual = drift.map((d) => ({
    name: d.asset_class,
    value: Math.max(d.actual_pct, 0),
  }));
  const target = drift.map((d) => ({
    name: d.asset_class,
    value: Math.max(d.target_pct, 0),
  }));
  return { actual, target };
}

export default function AllocationDonut({ drift, loading, error }) {
  if (loading) return <div className="h-64 flex items-center justify-center text-gray-400">Loading…</div>;
  if (error) return (
    <div className="h-64 flex items-center justify-center text-red-500 text-sm">
      ⚠ {error} <button className="ml-2 underline" onClick={() => window.location.reload()}>Retry</button>
    </div>
  );

  const { actual, target } = buildSlices(drift);
  if (actual.length === 0) return <div className="h-64 flex items-center justify-center text-gray-400">No allocation data</div>;

  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-700 mb-2">Allocation</h2>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie data={target} dataKey="value" cx="50%" cy="50%" innerRadius={40} outerRadius={65} strokeWidth={0}>
            {target.map((entry) => (
              <Cell key={entry.name} fill={COLOURS[entry.name] ?? '#94a3b8'} opacity={0.35} />
            ))}
          </Pie>
          <Pie data={actual} dataKey="value" cx="50%" cy="50%" innerRadius={68} outerRadius={90} strokeWidth={0}>
            {actual.map((entry) => (
              <Cell key={entry.name} fill={COLOURS[entry.name] ?? '#94a3b8'} />
            ))}
          </Pie>
          <Tooltip formatter={(v) => `${v.toFixed(1)}%`} />
          <Legend
            formatter={(value, entry) => `${value} ${entry.payload.value.toFixed(0)}%`}
            iconType="circle"
            iconSize={10}
          />
        </PieChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-400 text-center mt-1">Outer ring = actual · Inner ring = target</p>
    </div>
  );
}
