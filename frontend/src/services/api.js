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

  getReport: async (reportId) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/reports/${reportId}`, { headers }),
    )
  },

  getReportData: async (reportId) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/reports/${reportId}/data`, { headers }),
    )
  },

  updateReport: async (reportId, { generated_text }) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/reports/${reportId}`, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ generated_text }),
      }),
    )
  },

  /**
   * Streaming report generation.
   *
   * Server appends a JSON meta trailer of the form
   *   \n\n[[META]]{"report_id":"...","qa_score":8}[[END]]
   * which we strip out of the visible stream and parse for the caller.
   *
   * Chunk handling: we keep a local accumulator string, and on every
   * frame we emit ONLY the new bytes since the previous emit — never
   * the whole accumulator. This avoids the duplication bug where the
   * caller's setState was reseeing earlier text on every chunk.
   *
   * Caller passes onChunk(textDelta) for live rendering. The delta
   * should be appended with functional setState: setText(p => p + d).
   *
   * Returns { text, report_id, qa_score } after the stream closes.
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

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    const META = '[[META]]'

    let full = ''      // entire stream so far
    let emitted = 0    // index up to which we've already called onChunk

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      full += decoder.decode(value, { stream: true })

      const metaIdx = full.indexOf(META)
      if (metaIdx !== -1) {
        // Stop emitting at META; keep reading until [[END]] for safety.
        if (metaIdx > emitted) {
          onChunk?.(full.slice(emitted, metaIdx))
          emitted = metaIdx
        }
        continue
      }

      // No META in buffer — emit everything except the last (META.length - 1)
      // chars, in case "[[META]]" is split across two frames.
      const safeEnd = full.length - (META.length - 1)
      if (safeEnd > emitted) {
        onChunk?.(full.slice(emitted, safeEnd))
        emitted = safeEnd
      }
    }

    // Final flush: parse META, emit any visible tail before it.
    const metaIdx = full.indexOf(META)
    let text = full
    let meta = {}
    if (metaIdx !== -1) {
      if (metaIdx > emitted) {
        onChunk?.(full.slice(emitted, metaIdx))
      }
      const endIdx = full.indexOf('[[END]]', metaIdx)
      const jsonStr = full.slice(
        metaIdx + META.length,
        endIdx === -1 ? undefined : endIdx,
      )
      try { meta = JSON.parse(jsonStr) } catch { /* ignore */ }
      text = full.slice(0, metaIdx).replace(/\s+$/, '')
    } else if (full.length > emitted) {
      onChunk?.(full.slice(emitted))
    }

    return {
      text,
      report_id: meta.report_id ?? null,
      qa_score: meta.qa_score ?? null,
    }
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

  // Opens the rich HTML report card in a new tab. Built as a URL helper
  // because the endpoint returns text/html and is meant to be navigated
  // to, not fetched.
  viewHtmlUrl: (reportId) => `${API}/reports/${reportId}/view-html`,

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

  getJobRuns: async (secret) => {
    return jsonOrThrow(
      await fetch(
        `${API}/admin/job-runs?secret=${encodeURIComponent(secret)}&limit=10`,
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

  // ─── RM Dashboard ───
  getDrift: async (clientId) => {
    const headers = await authHeader()
    return jsonOrThrow(await fetch(`${API}/clients/${clientId}/drift`, { headers }))
  },

  getSnapshots: async (clientId, limit = 12) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/clients/${clientId}/snapshots?limit=${limit}`, { headers }),
    )
  },

  getRationaleEvents: async (clientId) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/clients/${clientId}/rationale-events`, { headers }),
    )
  },

  logRationaleEvent: async (clientId, payload) => {
    const headers = await authHeader()
    return jsonOrThrow(
      await fetch(`${API}/clients/${clientId}/rationale-events`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
    )
  },
}
