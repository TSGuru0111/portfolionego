import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import './report.css'

export default function NavLineChart({ series }) {
  if (!series || series.length === 0) {
    return <div className="empty-chart">90-day NAV chart — coming soon</div>
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={series}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="portfolio" stroke="#3b82f6" strokeWidth={2} dot={false} name="Portfolio" />
        <Line type="monotone" dataKey="nifty" stroke="#9ca3af" strokeWidth={2} dot={false} name="Nifty 50" />
      </LineChart>
    </ResponsiveContainer>
  )
}
