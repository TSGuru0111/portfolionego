import { useState } from 'react'
import toast from 'react-hot-toast'

import { api } from '../services/api.js'

/**
 * Streaming report generation hook.
 *
 * generateReport({ clientId, month }) → returns
 *   { text, report_id, qa_score } once the stream closes.
 *
 * Exposed state: reportText (live), isStreaming, error.
 */
export function useStreamReport() {
  const [reportText, setReportText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)

  const generateReport = async ({ clientId, month }) => {
    setReportText('')
    setIsStreaming(true)
    setError(null)

    try {
      const meta = await api.generateReportStream({
        clientId,
        month,
        onChunk: (chunk) => setReportText((prev) => prev + chunk),
      })
      return meta
    } catch (err) {
      setError(err.message)
      toast.error(err.message || 'Report generation failed')
      throw err
    } finally {
      setIsStreaming(false)
    }
  }

  return { reportText, isStreaming, error, generateReport }
}
