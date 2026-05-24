import './report.css'

export default function KpiTile({ label, value, sublabel, tone = 'neutral', tooltip }) {
  const toneClass = `tone-${tone}`
  const isMissing = value == null || value === '—'
  return (
    <div
      className={`kpi-tile ${toneClass}${isMissing ? ' is-missing' : ''}`}
      title={isMissing && tooltip ? tooltip : (tooltip || undefined)}
    >
      <div className="label">{label}</div>
      <div className="value">{value ?? '—'}</div>
      {sublabel ? <div className="sublabel">{sublabel}</div> : null}
    </div>
  )
}
