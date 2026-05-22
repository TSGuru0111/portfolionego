import { useEffect, useState } from 'react'
import { Plus, Save, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'

import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import Spinner from '../ui/Spinner.jsx'
import { api } from '../../services/api.js'

const EMPTY = {
  rss: [],
  newsapi: { enabled: true, queries: [], language: 'en' },
  gnews: { enabled: true, sectors: [] },
}

export default function FeedsEditor() {
  const [data, setData] = useState(EMPTY)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    api
      .getFeeds()
      .then((res) => setData({ ...EMPTY, ...res }))
      .catch((err) => toast.error(err.message || 'Failed to load feeds'))
      .finally(() => setLoading(false))
  }, [])

  const mark = (next) => {
    setData(next)
    setDirty(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const res = await api.saveFeeds(data)
      setData(res)
      setDirty(false)
      toast.success('Feeds saved')
    } catch (err) {
      toast.error(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  // ─── RSS row helpers ───
  const updateRssRow = (idx, patch) => {
    const next = { ...data, rss: data.rss.map((r, i) => (i === idx ? { ...r, ...patch } : r)) }
    mark(next)
  }
  const addRssRow = () =>
    mark({
      ...data,
      rss: [
        ...data.rss,
        { id: `rss-${Date.now()}`, label: '', url: '', category: 'general', enabled: true },
      ],
    })
  const removeRssRow = (idx) =>
    mark({ ...data, rss: data.rss.filter((_, i) => i !== idx) })

  // ─── NewsAPI queries / GNews sectors helpers ───
  const setQueries = (text) =>
    mark({
      ...data,
      newsapi: {
        ...data.newsapi,
        queries: text.split('\n').map((s) => s.trim()).filter(Boolean),
      },
    })
  const setSectors = (text) =>
    mark({
      ...data,
      gnews: {
        ...data.gnews,
        sectors: text.split('\n').map((s) => s.trim()).filter(Boolean),
      },
    })

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-primary-600">
        <Spinner />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <Button onClick={save} loading={saving} disabled={!dirty}>
          <Save className="w-4 h-4 mr-1" /> Save feeds
        </Button>
      </div>

      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-900">RSS feeds</h3>
          <button
            onClick={addRssRow}
            className="text-xs text-primary-700 inline-flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" /> Add feed
          </button>
        </div>
        {data.rss.length === 0 ? (
          <div className="text-xs text-slate-400 italic">
            No RSS feeds configured.
          </div>
        ) : (
          <div className="space-y-2">
            {data.rss.map((r, idx) => (
              <div
                key={r.id || idx}
                className="grid grid-cols-1 md:grid-cols-[1.2fr_2fr_1fr_auto_auto] gap-2 items-center"
              >
                <input
                  value={r.label}
                  onChange={(e) => updateRssRow(idx, { label: e.target.value })}
                  placeholder="Label"
                  className="text-sm border border-slate-300 rounded-lg px-2 py-1.5"
                />
                <input
                  value={r.url}
                  onChange={(e) => updateRssRow(idx, { url: e.target.value })}
                  placeholder="https://…"
                  className="text-sm border border-slate-300 rounded-lg px-2 py-1.5 font-mono"
                />
                <input
                  value={r.category}
                  onChange={(e) => updateRssRow(idx, { category: e.target.value })}
                  placeholder="category"
                  className="text-sm border border-slate-300 rounded-lg px-2 py-1.5"
                />
                <label className="text-xs text-slate-600 inline-flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={!!r.enabled}
                    onChange={(e) => updateRssRow(idx, { enabled: e.target.checked })}
                  />
                  on
                </label>
                <button
                  onClick={() => removeRssRow(idx)}
                  className="text-slate-400 hover:text-red-600 p-1"
                  title="Remove"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="text-sm font-semibold text-slate-900 mb-3">NewsAPI</h3>
        <label className="text-xs text-slate-600 inline-flex items-center gap-2 mb-2">
          <input
            type="checkbox"
            checked={!!data.newsapi.enabled}
            onChange={(e) =>
              mark({ ...data, newsapi: { ...data.newsapi, enabled: e.target.checked } })
            }
          />
          Enabled
        </label>
        <label className="block text-xs font-medium text-slate-600 mb-1 mt-2">
          Queries (one per line)
        </label>
        <textarea
          rows={4}
          value={data.newsapi.queries.join('\n')}
          onChange={(e) => setQueries(e.target.value)}
          className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 font-mono"
        />
        <label className="block text-xs font-medium text-slate-600 mb-1 mt-3">
          Language
        </label>
        <input
          value={data.newsapi.language}
          onChange={(e) =>
            mark({ ...data, newsapi: { ...data.newsapi, language: e.target.value } })
          }
          className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 w-24"
        />
      </Card>

      <Card>
        <h3 className="text-sm font-semibold text-slate-900 mb-3">GNews</h3>
        <label className="text-xs text-slate-600 inline-flex items-center gap-2 mb-2">
          <input
            type="checkbox"
            checked={!!data.gnews.enabled}
            onChange={(e) =>
              mark({ ...data, gnews: { ...data.gnews, enabled: e.target.checked } })
            }
          />
          Enabled
        </label>
        <label className="block text-xs font-medium text-slate-600 mb-1 mt-2">
          Sectors (one per line)
        </label>
        <textarea
          rows={4}
          value={data.gnews.sectors.join('\n')}
          onChange={(e) => setSectors(e.target.value)}
          className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 font-mono"
        />
      </Card>
    </div>
  )
}
