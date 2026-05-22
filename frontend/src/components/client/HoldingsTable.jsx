// Day 3-4 ships the full implementation with live prices + colours.
// This stub renders the table shell so Dashboard/ClientDetail compile.
import Badge from '../ui/Badge.jsx'
import { formatINR, formatPct, returnColor } from '../../utils/formatters.js'

export default function HoldingsTable({ holdings = [] }) {
  if (!holdings.length) {
    return (
      <div className="text-sm text-slate-500 italic">
        No holdings recorded for this client.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-xl bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="text-left px-4 py-2">Stock</th>
            <th className="text-left px-4 py-2">Sector</th>
            <th className="text-right px-4 py-2">Qty</th>
            <th className="text-right px-4 py-2">Buy Price</th>
            <th className="text-right px-4 py-2">Current</th>
            <th className="text-right px-4 py-2">Return %</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {holdings.map((h) => {
            const ret =
              h.current_price != null
                ? ((h.current_price - h.buy_price) / h.buy_price) * 100
                : null
            return (
              <tr key={h.ticker} className="hover:bg-slate-50">
                <td className="px-4 py-2 font-mono text-slate-800">
                  {h.ticker}
                  {h.source === 'cached' && (
                    <Badge tone="gold" className="ml-2">cached</Badge>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-600">{h.sector}</td>
                <td className="px-4 py-2 text-right text-slate-800">{h.qty}</td>
                <td className="px-4 py-2 text-right text-slate-600">
                  {formatINR(h.buy_price)}
                </td>
                <td className="px-4 py-2 text-right text-slate-800">
                  {h.current_price != null ? formatINR(h.current_price) : '—'}
                </td>
                <td className={`px-4 py-2 text-right font-medium ${returnColor(ret)}`}>
                  {formatPct(ret)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
