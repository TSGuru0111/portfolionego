import { useState } from 'react'
import toast from 'react-hot-toast'

import { api } from '../services/api.js'

/**
 * Streaming report generation hook.
 *
 * Returns reportText, isStreaming, error, generateReport(clientId, month).
 */
export function useStreamReport() {
  const [reportText, setReportText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)

  const generateReport = async (clientId, month) => {
    setReportText('')
    setIsStreaming(true)
    setError(null)

    try {
      await api.generateReportStream({
        clientId,
        month,
        onChunk: (chunk) => setReportText((prev) => prev + chunk),
      })
    } catch (err) {
      setError(err.message)
      toast.error(err.message || 'Report generation failed')
    } finally {
      setIsStreaming(false)
    }
  }

  return { reportText, isStreaming, error, generateReport }
}
