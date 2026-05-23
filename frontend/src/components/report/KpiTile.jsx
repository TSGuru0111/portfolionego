import './report.css'

export default function KpiTile({ label, value, sublabel, tone }) {
  const toneClass = tone ? `tone-${tone}` : ''
  return (
    <div className={`kpi-tile ${toneClass}`}>
      <div className="label">{label}</div>
      <div className="value">{value ?? '—'}</div>
      {sublabel ? <div className="sublabel">{sublabel}</div> : null}
    </div>
  )
}
