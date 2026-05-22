import { useEffect, useState } from 'react'

import { api } from '../services/api.js'

export function usePortfolio(clientId) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!clientId) return
    let cancelled = false
    setLoading(true)

    api
      .getClientPortfolio(clientId)
      .then((res) => {
        if (cancelled) return
        setData(res)
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [clientId])

  return { data, loading, error }
}
