import KpiTile from './KpiTile'
import { formatCr, formatPct, formatAbsoluteINR } from '../../utils/formatters'

function driftTone(d) {
  if (d == null) return 'neutral'
  if (d < 5) return 'success'
  if (d < 15) return 'gold'
  return 'danger'
}

function concTone(c) {
  if (c == null) return 'neutral'
  if (c < 25) return 'success'
  if (c < 40) return 'gold'
  return 'danger'
}

function gainTone(g) {
  if (g == null) return 'neutral'
  return g >= 0 ? 'success' : 'danger'
}

function vsNiftyTone(a) {
  if (a == null) return 'neutral'
  return a >= 0 ? 'success' : 'danger'
}

export default function KpiRow({ kpis }) {
  const k = kpis || {}
  const gain = k.absolute_gain || {}
  const gainValue = gain.value
  const gainSublabel = gain.partial
    ? `partial (${(gain.missing_tickers || []).length} missing)`
    : 'since inception'

  return (
    <div className="kpi-row-v2">
      <KpiTile
        label="Portfolio Value"
        value={formatCr(k.portfolio_value_cr)}
        sublabel={k.holdings_count != null ? `${k.holdings_count} holdings` : null}
        tone="neutral"
        tooltip="Sum of qty x current price for all holdings."
      />
      <KpiTile
        label="Absolute Gain"
        value={formatAbsoluteINR(gainValue)}
        sublabel={gainSublabel}
        tone={gainTone(gainValue)}
        tooltip={
          gainValue == null
            ? 'Live prices unavailable for all holdings.'
            : (gain.missing_tickers || []).length
              ? `Excludes: ${gain.missing_tickers.join(', ')}`
              : null
        }
      />
      <KpiTile
        label="XIRR"
        value={formatPct(k.xirr_pct)}
        sublabel="p.a."
        tone="neutral"
        tooltip="Annualised return from your transaction history. Requires at least one buy transaction."
      />
      <KpiTile
        label="vs Nifty (MTD)"
        value={formatPct(k.alpha_pct)}
        sublabel={k.nifty_mtd_pct != null ? `Nifty ${formatPct(k.nifty_mtd_pct)}` : null}
        tone={vsNiftyTone(k.alpha_pct)}
        tooltip="Portfolio MTD return minus Nifty 50 MTD return."
      />
      <KpiTile
        label="Drift"
        value={k.drift_pct != null ? `${k.drift_pct.toFixed(1)}%` : null}
        sublabel="off target"
        tone={driftTone(k.drift_pct)}
        tooltip="Max deviation from target equity/debt/cash allocation for the client's risk profile."
      />
      <KpiTile
        label="Top-3 Concentration"
        value={k.concentration_pct != null ? `${k.concentration_pct.toFixed(1)}%` : null}
        sublabel="of portfolio"
        tone={concTone(k.concentration_pct)}
        tooltip="Weight of the three largest holdings by market value."
      />
    </div>
  )
}
