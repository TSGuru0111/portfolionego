import './report.css'

export default function TopMoversTable({ title, movers }) {
  return (
    <div className="movers-card">
      <h3>{title}</h3>
      {(!movers || movers.length === 0) ? (
        <div style={{ fontSize: 13, color: '#9ca3af' }}>No data</div>
      ) : (
        <table className="movers-table">
          <thead>
            <tr><th>Ticker</th><th>Sector</th><th style={{ textAlign: 'right' }}>Return</th></tr>
          </thead>
          <tbody>
            {movers.map((m, i) => {
              const pct = Number(m.month_return_pct ?? 0)
              const cls = pct >= 0 ? 'ret-pos' : 'ret-neg'
              return (
                <tr key={i}>
                  <td>{m.ticker}</td>
                  <td>{m.sector || '—'}</td>
                  <td className={cls} style={{ textAlign: 'right' }}>
                    {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
