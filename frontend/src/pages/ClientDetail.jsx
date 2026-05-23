import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, FileText } from 'lucide-react'
import toast from 'react-hot-toast'

import Banner from '../components/ui/Banner.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import Spinner from '../components/ui/Spinner.jsx'
import HoldingsTable from '../components/client/HoldingsTable.jsx'
import ReturnSummary from '../components/client/ReturnSummary.jsx'
import PastReportsList from '../components/report/PastReportsList.jsx'
import SectorDonut from '../components/report/SectorDonut'
import KpiTile from '../components/report/KpiTile'
import '../components/report/report.css'
import { formatCr, formatDateIN } from '../utils/formatters.js'
import { RISK_LABELS } from '../utils/constants.js'
import { usePortfolio } from '../hooks/usePortfolio.js'

function defaultMonth() {
  const d = new Date()
  d.setMonth(d.getMonth() - 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export default function ClientDetail() {
  const { id } = useParams()
  const { data: portfolio, loading, error } = usePortfolio(id)
  const [month, setMonth] = useState(defaultMonth())

  const newReportHref = useMemo(
    () => `/clients/${id}/report/new?month=${month}`,
    [id, month],
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-primary-600">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-sm text-red-600">
        Failed to load portfolio: {error}
      </div>
    )
  }

  if (!portfolio) {
    return <div className="text-sm text-slate-500 italic">No portfolio data.</div>
  }

  const client = portfolio.client ?? {}
  const holdings = portfolio.holdings ?? []

  const sectorAllocation = (() => {
    const totals = {}
    let grand = 0
    for (const h of holdings || []) {
      const mv = Number(h.qty || 0) * Number(h.current_price || h.avg_price || 0)
      if (!mv) continue
      const s = h.sector || 'Other'
      totals[s] = (totals[s] || 0) + mv
      grand += mv
    }
    if (!grand) return []
    return Object.entries(totals)
      .map(([sector, mv]) => ({ sector, weight_pct: (mv / grand) * 100 }))
      .sort((a, b) => b.weight_pct - a.weight_pct)
  })()

  const portfolioValueCr = (() => {
    let total = 0
    for (const h of holdings || []) {
      total += Number(h.qty || 0) * Number(h.current_price || h.avg_price || 0)
    }
    return total / 1e7
  })()

  return (
    <div className="space-y-6">
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-primary-700"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to clients
      </Link>

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-serif text-2xl text-slate-900">{client.name}</h1>
          <div className="text-sm text-slate-500 mt-1">
            {client.city ? `${client.city} · ` : ''}
            {client.profession ? `${client.profession} · ` : ''}
            AUM {formatCr(client.aum)}
            {client.risk_profile && (
              <span className="ml-2 text-xs uppercase tracking-wide text-slate-400">
                {RISK_LABELS[client.risk_profile]?.label ?? client.risk_profile}
              </span>
            )}
          </div>
          {client.onboarded_at && (
            <div className="text-xs text-slate-400 mt-1">
              Onboarded {formatDateIN(client.onboarded_at)}
            </div>
          )}
        </div>

        <div className="flex items-end gap-2">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Report month
            </label>
            <input
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="text-sm border border-slate-300 rounded-lg px-3 py-2"
            />
          </div>
          <Link to={newReportHref}>
            <Button>
              <FileText className="w-4 h-4 mr-1" />
              Generate report
            </Button>
          </Link>
        </div>
      </div>

      <div className="kpi-row">
        <KpiTile label="Portfolio value"
                 value={`₹${portfolioValueCr.toFixed(2)} Cr`}
                 sublabel={`${(holdings || []).length} holdings`} />
        <KpiTile label="Risk profile"
                 value={client?.risk_profile || '—'} />
        <KpiTile label="Tax bracket"
                 value={client?.tax_bracket ? `${client.tax_bracket}%` : '—'} />
        <KpiTile label="Liquidity need"
                 value={client?.liquidity_need_pct != null ? `${client.liquidity_need_pct}%` : '—'} />
      </div>

      {portfolio.has_stale_prices && (
        <Banner tone="warning">
          Some prices could not be refreshed from NSE/BSE and are shown from the
          last cached value. The report will flag this to the client.
        </Banner>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <h2 className="text-base font-semibold text-slate-900 mb-3">Holdings</h2>
            <HoldingsTable holdings={holdings} />
          </Card>
        </div>
        <div className="space-y-4">
          <ReturnSummary
            portfolioReturn={portfolio.portfolio_return}
            niftyReturn={portfolio.nifty_return}
          />
          <Card>
            <h2 className="text-base font-semibold text-slate-900 mb-3">
              Sector mix
            </h2>
            <SectorDonut allocation={sectorAllocation} />
          </Card>
          <PastReportsList clientId={id} />
        </div>
      </div>
    </div>
  )
}
