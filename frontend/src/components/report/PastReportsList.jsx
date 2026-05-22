import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText } from 'lucide-react'

import Card from '../ui/Card.jsx'
import QAScoreBadge from './QAScoreBadge.jsx'
import { api } from '../../services/api.js'
import { formatMonth, formatDateIN } from '../../utils/formatters.js'

export default function PastReportsList({ clientId }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!clientId) return
    let cancelled = false
    setLoading(true)
    api
      .getReports(clientId)
      .then((rows) => {
        if (!cancelled) setReports(Array.isArray(rows) ? rows : [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [clientId])

  return (
    <Card>
      <h2 className="text-base font-semibold text-slate-900 mb-3">
        Past reports
      </h2>

      {loading && (
        <div className="text-sm text-slate-400 italic">Loading…</div>
      )}

      {error && !loading && (
        <div className="text-sm text-red-600">Failed to load: {error}</div>
      )}

      {!loading && !error && reports.length === 0 && (
        <div className="text-sm text-slate-400 italic">
          No reports generated yet for this client.
        </div>
      )}

      {!loading && !error && reports.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {reports.map((r) => (
            <li key={r.id} className="py-2 flex items-center justify-between gap-2">
              <Link
                to={`/clients/${clientId}/report/${r.id}?month=${r.month}`}
                className="flex items-center gap-2 text-sm text-primary-700 hover:underline"
              >
                <FileText className="w-4 h-4" />
                <span>{formatMonth(r.month)}</span>
                <span className="text-xs text-slate-400">
                  {formatDateIN(r.created_at)}
                </span>
              </Link>
              <QAScoreBadge score={r.qa_score} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
