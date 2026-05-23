import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './report.css'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
                '#06b6d4', '#a855f7', '#eab308', '#22c55e']

export default function SectorDonut({ allocation }) {
  if (!allocation || allocation.length === 0) {
    return <div className="empty-chart">No allocation data</div>
  }
  const data = allocation.map(a => ({ name: a.sector, value: a.weight_pct }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name"
             innerRadius={55} outerRadius={90} paddingAngle={1}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip formatter={(v) => `${v.toFixed(1)}%`} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
