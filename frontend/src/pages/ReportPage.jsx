import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'

import KpiTile from '../components/report/KpiTile'
import SectorDonut from '../components/report/SectorDonut'
import NavLineChart from '../components/report/NavLineChart'
import TopMoversTable from '../components/report/TopMoversTable'
import MarketContextGrid from '../components/report/MarketContextGrid'
import NextStepsCards from '../components/report/NextStepsCards'
import LetterCard from '../components/report/LetterCard'
import ActionBar from '../components/report/ActionBar'
import '../components/report/report.css'

function fmtCr(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return `₹${Number(v).toFixed(2)} Cr`
}
function fmtPct(v) {
  if (v == null || Number.isNaN(v)) return '—'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function toneFromPct(v) {
  if (v == null) return undefined
  return Number(v) >= 0 ? 'positive' : 'negative'
}

export default function ReportPage() {
  const { id, reportId: reportIdParam } = useParams()
  const [searchParams] = useSearchParams()
  const month = searchParams.get('month') || new Date().toISOString().slice(0, 7)
  const isNew = reportIdParam === 'new'

  const [data, setData] = useState(null)
  const [letterText, setLetterText] = useState('')
  const [reportId, setReportId] = useState(isNew ? null : reportIdParam)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [error, setError] = useState(null)

  const originalTextRef = useRef('')

  // Load existing report
  useEffect(() => {
    if (isNew) return
    let cancelled = false
    api.getReportData(reportIdParam).then(d => {
      if (cancelled) return
      setData(d)
      setLetterText(d.letter_text || '')
      originalTextRef.current = d.letter_text || ''
      setReportId(d.report_id)
    }).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [isNew, reportIdParam])

  // Stream new report — and immediately fetch skeleton data
  useEffect(() => {
    if (!isNew) return
    let cancelled = false

    // Skeleton data: we don't have a saved report yet, so we fetch the
    // client's portfolio + holdings via existing endpoints and build a
    // minimal data shape. The full /data swap happens once streaming
    // completes and we have a report_id.
    api.getClientPortfolio(id).then(p => {
      if (cancelled) return
      const holdings = p?.portfolio?.holdings || p?.holdings || []
      const skeleton = {
        client_name: p?.client?.name || '',
        month,
        currency: p?.client?.currency || 'INR',
        qa_score: null,
        kpis: {
          portfolio_value_cr: null,
          holdings_count: holdings.length,
          return_mtd_pct: null,
          nifty_mtd_pct: null,
          alpha_pct: null,
        },
        holdings,
        top_contributors: [],
        top_detractors: [],
        sector_allocation: [],
        nav_series: null,
        market_context: [],
        next_steps: [],
        letter_text: '',
      }
      setData(skeleton)
    }).catch(() => { /* skeleton optional */ })

    setIsStreaming(true)
    api.generateReportStream({
      clientId: id,
      month,
      onChunk: (delta) => {
        if (cancelled) return
        setLetterText(prev => prev + delta)
      },
    }).then(async (res) => {
      if (cancelled) return
      setIsStreaming(false)
      if (res.report_id) {
        setReportId(res.report_id)
        try {
          const full = await api.getReportData(res.report_id)
          if (cancelled) return
          setData(full)
          setLetterText(full.letter_text || res.text || '')
          originalTextRef.current = full.letter_text || res.text || ''
        } catch (e) {
          setError(e.message)
        }
      }
    }).catch(e => {
      if (cancelled) return
      setIsStreaming(false)
      setError(e.message)
    })

    return () => { cancelled = true }
  }, [isNew, id, month])

  const kpis = data?.kpis || {}
  const alphaTone = toneFromPct(kpis.alpha_pct)
  const returnTone = toneFromPct(kpis.return_mtd_pct)

  function handleLetterChange(next) {
    setLetterText(next)
    setIsDirty(next !== originalTextRef.current)
  }
  function handleToggleEdit() {
    setIsEditing(true)
    setIsDirty(false)
  }
  function handleCancel() {
    setLetterText(originalTextRef.current)
    setIsEditing(false)
    setIsDirty(false)
  }
  async function handleSave() {
    if (!reportId) return
    try {
      await api.updateReport(reportId, { generated_text: letterText })
      originalTextRef.current = letterText
      setIsEditing(false)
      setIsDirty(false)
    } catch (e) {
      setError(e.message)
    }
  }
  function handleDownload() {
    if (!reportId) return
    const headers = {}
    fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/reports/${reportId}/export-pdf?lang=english`, { headers })
      .then(r => r.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `portfolio-review-${data?.month || month}.pdf`
        document.body.appendChild(a); a.click(); a.remove()
        URL.revokeObjectURL(url)
      })
      .catch(e => setError(e.message))
  }

  if (error) {
    return <div className="report-dashboard"><div style={{ color: '#b91c1c' }}>Error: {error}</div></div>
  }
  if (!data) {
    return <div className="report-dashboard"><div>Loading…</div></div>
  }

  return (
    <div className="report-dashboard">
      <header className="report-header">
        <div>
          <h1>{data.client_name || 'Client'}</h1>
          <div className="month">Portfolio review · {data.month}</div>
        </div>
        {data.qa_score != null ? (
          <div className="qa-badge">QA · {data.qa_score}/10</div>
        ) : null}
      </header>

      <div className="kpi-row">
        <KpiTile label="Portfolio Value"
                 value={fmtCr(kpis.portfolio_value_cr)}
                 sublabel={`${kpis.holdings_count ?? 0} holdings`} />
        <KpiTile label="Return (MTD)"
                 value={fmtPct(kpis.return_mtd_pct)}
                 tone={returnTone} />
        <KpiTile label="Nifty 50 (MTD)"
                 value={fmtPct(kpis.nifty_mtd_pct)}
                 tone={toneFromPct(kpis.nifty_mtd_pct)} />
        <KpiTile label="vs Nifty"
                 value={fmtPct(kpis.alpha_pct)}
                 tone={alphaTone}
                 sublabel="Alpha" />
      </div>

      <div className="chart-row">
        <div className="chart-card">
          <h3>NAV vs Nifty 50 — last 90 days</h3>
          <NavLineChart series={data.nav_series} />
        </div>
        <div className="chart-card">
          <h3>Sector allocation</h3>
          <SectorDonut allocation={data.sector_allocation} />
        </div>
      </div>

      <div className="movers-row">
        <TopMoversTable title="Top contributors" movers={data.top_contributors} />
        <TopMoversTable title="Top detractors" movers={data.top_detractors} />
      </div>

      <MarketContextGrid cards={data.market_context} />
      <NextStepsCards items={data.next_steps} />

      <LetterCard
        text={letterText}
        isEditing={isEditing}
        isStreaming={isStreaming}
        onChange={handleLetterChange}
      />

      <ActionBar
        reportId={reportId}
        isEditing={isEditing}
        isDirty={isDirty}
        isStreaming={isStreaming}
        onToggleEdit={handleToggleEdit}
        onSave={handleSave}
        onCancel={handleCancel}
        onDownload={handleDownload}
      />
    </div>
  )
}
