import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Download, ExternalLink } from 'lucide-react'
import toast from 'react-hot-toast'

import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import ReportViewer from '../components/report/ReportViewer.jsx'
import QAScoreBadge from '../components/report/QAScoreBadge.jsx'
import { api } from '../services/api.js'
import { formatMonth } from '../utils/formatters.js'
import { useStreamReport } from '../hooks/useStreamReport.js'

function defaultMonth() {
  const d = new Date()
  d.setMonth(d.getMonth() - 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export default function ReportPage() {
  const { id, reportId } = useParams()
  const [params] = useSearchParams()
  const month = params.get('month') ?? defaultMonth()
  const isNew = reportId === 'new'

  const { reportText, isStreaming, error, generateReport } = useStreamReport()
  const [qaScore, setQaScore] = useState(null)
  const [resolvedReportId, setResolvedReportId] = useState(
    isNew ? null : reportId,
  )
  const [downloading, setDownloading] = useState(false)
  const [savedText, setSavedText] = useState('')

  useEffect(() => {
    if (!isNew) return
    generateReport({ clientId: id, month })
      .then((meta) => {
        if (meta?.qa_score != null) setQaScore(meta.qa_score)
        if (meta?.report_id) setResolvedReportId(meta.report_id)
      })
      .catch(() => { /* hook already surfaced the toast */ })
  }, [isNew, id, month])

  // When viewing a saved report, fetch the persisted text instead of
  // re-streaming through Cohere.
  useEffect(() => {
    if (isNew || !reportId) return
    let cancelled = false
    api.getReport(reportId)
      .then((row) => {
        if (cancelled || !row) return
        setSavedText(row.generated_text || '')
        if (row.qa_score != null) setQaScore(row.qa_score)
      })
      .catch(() => { /* surfaced below via error message */ })
    return () => { cancelled = true }
  }, [isNew, reportId])

  const displayText = isNew ? reportText : savedText

  const downloadPdf = async () => {
    if (!resolvedReportId) {
      toast.error('Report has not been saved yet.')
      return
    }
    setDownloading(true)
    try {
      const blob = await api.exportPdf(resolvedReportId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `portfolio-letter-${month}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(err.message || 'PDF download failed')
    } finally {
      setDownloading(false)
    }
  }

  const openHtmlView = () => {
    if (!resolvedReportId) {
      toast.error('Report has not been saved yet.')
      return
    }
    window.open(api.viewHtmlUrl(resolvedReportId), '_blank', 'noopener')
  }

  return (
    <div className="space-y-6">
      <Link
        to={`/clients/${id}`}
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-primary-700"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to client
      </Link>

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-serif text-2xl text-slate-900">
            Portfolio commentary
          </h1>
          <div className="text-sm text-slate-500 mt-1">
            {formatMonth(month)}
            {qaScore != null && (
              <span className="ml-3">
                <QAScoreBadge score={qaScore} />
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={openHtmlView}
            disabled={isStreaming || !resolvedReportId}
          >
            <ExternalLink className="w-4 h-4 mr-1" />
            View HTML report
          </Button>
          <Button
            variant="secondary"
            onClick={downloadPdf}
            loading={downloading}
            disabled={isStreaming || !resolvedReportId}
          >
            <Download className="w-4 h-4 mr-1" />
            Download PDF
          </Button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600">
          Generation error: {error}
        </div>
      )}

      <Card>
        <ReportViewer reportText={displayText} isStreaming={isStreaming} />
      </Card>
    </div>
  )
}
