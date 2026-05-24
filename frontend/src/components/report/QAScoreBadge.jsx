import { useState } from 'react'
import { Info } from 'lucide-react'

export default function QAScoreBadge({ score, reasons }) {
  const [open, setOpen] = useState(false)
  if (score == null) return null
  const tone = score >= 8 ? 'success' : score >= 7 ? 'gold' : 'danger'
  const reasonList = Array.isArray(reasons) ? reasons.slice(0, 3) : []

  return (
    <div
      className={`qa-badge-wrap qa-tone-${tone}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="qa-badge"
        onClick={() => setOpen((v) => !v)}
      >
        QA · {score}/10 <Info className="w-3 h-3 ml-1 inline" />
      </button>
      {open ? (
        <div className="qa-popover" role="tooltip">
          <div className="qa-popover-header">QA Score · {score}/10</div>
          <div className="qa-popover-sub">Graded by Cohere command-r</div>
          {reasonList.length ? (
            <ul className="qa-popover-reasons">
              {reasonList.map((r, i) => (<li key={i}>{r}</li>))}
            </ul>
          ) : (
            <div className="qa-popover-empty">No reasons recorded.</div>
          )}
          <div className="qa-popover-footer">Auto-regenerates if &lt; 7</div>
        </div>
      ) : null}
    </div>
  )
}
