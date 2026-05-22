import { supabase } from './supabase.js'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function authHeader() {
  const { data } = await supabase.auth.getSession()
  const token = data?.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function jsonOrThrow(res) {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // not JSON — keep statusText
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: async () => {
    const res = await fetch(`${API}/health`)
    return jsonOrThrow(res)
  },

  // ─── Clients ───
  getClients: async () => {
    const headers = await authHeader()
    return jsonOrThrow(await fetch(`${API}/clients`, { headers }))
  },

  getClientPortfolio: async (clientId) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/clients/${clientId}/portfolio`, { headers }),
    )
  },

  // ─── Reports ───
  getReports: async (clientId) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/reports?client_id=${clientId}`, { headers }),
    )
  },

  /**
   * Streaming report generation.
   * Caller passes onChunk(textDelta) — invoked for every streamed chunk.
   * Returns the final concatenated text once the stream closes.
   */
  generateReportStream: async ({ clientId, month, onChunk }) => {
    const headers = await authHeader()
    const res = await fetch(`${API}/reports/generate-stream`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: clientId, month }),
    })

    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch { /* ignore */ }
      throw new Error(detail)
    }

    const reader  = res.body.getReader()
    const decoder = new TextDecoder()
    let full = ''
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      full += chunk
      onChunk?.(chunk)
    }
    return full
  },

  exportPdf: async (reportId) => {
    const headers = await authHeader()
    const res = await fetch(
      `${API}/reports/${reportId}/export-pdf?lang=english`,
      { headers },
    )
    if (!res.ok) throw new Error('PDF download failed')
    return res.blob()
  },

  // ─── Admin ───
  triggerNewsCollection: async (secret) => {
    return jsonOrThrow(
      await fetch(
        `${API}/admin/trigger-news-collection?secret=${encodeURIComponent(secret)}`,
        { method: 'POST' },
      ),
    )
  },

  triggerWeeklySummary: async (secret) => {
    return jsonOrThrow(
      await fetch(
        `${API}/admin/trigger-weekly-summary?secret=${encodeURIComponent(secret)}`,
        { method: 'POST' },
      ),
    )
  },

  triggerAllReports: async (secret) => {
    return jsonOrThrow(
      await fetch(
        `${API}/admin/trigger-all-reports?secret=${encodeURIComponent(secret)}`,
        { method: 'POST' },
      ),
    )
  },

  getErrorLogs: async (secret) => {
    return jsonOrThrow(
      await fetch(
        `${API}/admin/errors?secret=${encodeURIComponent(secret)}&limit=20`,
      ),
    )
  },

  // ─── Config ───
  // Agents (system-context .md files)
  listAgents: async () => {
    const headers = await authHeader()
    return jsonOrThrow(await fetch(`${API}/config/agents`, { headers }))
  },
  getAgent: async (name) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/config/agents/${encodeURIComponent(name)}`, { headers }),
    )
  },
  saveAgent: async (name, content) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/config/agents/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      }),
    )
  },
  deleteAgent: async (name) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/config/agents/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers,
      }),
    )
  },

  // Feeds (RSS + NewsAPI + GNews)
  getFeeds: async () => {
    const headers = await authHeader()
    return jsonOrThrow(await fetch(`${API}/config/feeds`, { headers }))
  },
  saveFeeds: async (payload) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/config/feeds`, {
        method: 'PUT',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
    )
  },

  // Style samples (previous RM letters)
  listStyleSamples: async () => {
    const headers = await authHeader()
    return jsonOrThrow(await fetch(`${API}/config/style-samples`, { headers }))
  },
  getStyleSample: async (id) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/config/style-samples/${encodeURIComponent(id)}`, {
        headers,
      }),
    )
  },
  createStyleSample: async ({ content, title }) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/config/style-samples`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, title: title || null }),
      }),
    )
  },
  deleteStyleSample: async (id) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/config/style-samples/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers,
      }),
    )
  },
}
