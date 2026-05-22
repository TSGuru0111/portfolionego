import { ArrowDownRight, ArrowUpRight } from 'lucide-react'

import Card from '../ui/Card.jsx'
import { formatPct, returnColor } from '../../utils/formatters.js'

export default function ReturnSummary({ portfolio_return, benchmark_return, alpha }) {
  const positive = (alpha ?? 0) >= 0
  return (
    <Card className="flex flex-col gap-2">
      <div className="text-xs uppercase tracking-wide text-slate-500">
        Portfolio vs Nifty 50
      </div>
      <div className="flex items-baseline gap-4">
        <div className={`text-3xl font-semibold ${returnColor(portfolio_return)}`}>
          {formatPct(portfolio_return)}
        </div>
        <div className="text-sm text-slate-500">
          Nifty {formatPct(benchmark_return)}
        </div>
      </div>
      <div
        className={`text-sm inline-flex items-center gap-1 ${returnColor(alpha)}`}
      >
        {positive ? (
          <ArrowUpRight className="w-4 h-4" />
        ) : (
          <ArrowDownRight className="w-4 h-4" />
        )}
        {formatPct(alpha)} over benchmark
      </div>
    </Card>
  )
}
