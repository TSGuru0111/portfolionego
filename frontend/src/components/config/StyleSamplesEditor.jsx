import { useEffect, useRef, useState } from 'react'
import { Eye, Trash2, Upload } from 'lucide-react'
import toast from 'react-hot-toast'

import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import Spinner from '../ui/Spinner.jsx'
import { api } from '../../services/api.js'

export default function StyleSamplesEditor() {
  const [samples, setSamples] = useState([])
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState(null) // { id, content }
  const fileInputRef = useRef(null)

  const refresh = async () => {
    setLoading(true)
    try {
      setSamples(await api.listStyleSamples())
    } catch (err) {
      toast.error(err.message || 'Failed to load samples')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const submit = async () => {
    if (!content.trim()) {
      toast.error('Paste or upload a letter first.')
      return
    }
    setUploading(true)
    try {
      await api.createStyleSample({ content, title: title.trim() || null })
      toast.success('Sample saved')
      setTitle('')
      setContent('')
      refresh()
    } catch (err) {
      toast.error(err.message || 'Save failed')
    } finally {
      setUploading(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('Delete this sample?')) return
    try {
      await api.deleteStyleSample(id)
      toast.success('Deleted')
      refresh()
      if (preview?.id === id) setPreview(null)
    } catch (err) {
      toast.error(err.message || 'Delete failed')
    }
  }

  const openPreview = async (id) => {
    try {
      const res = await api.getStyleSample(id)
      setPreview({ id, content: res.content })
    } catch (err) {
      toast.error(err.message || 'Preview failed')
    }
  }

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const text = await file.text()
    setContent(text)
    if (!title) setTitle(file.name.replace(/\.[^.]+$/, ''))
    e.target.value = ''
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <h3 className="text-sm font-semibold text-slate-900 mb-3">
          Add a sample letter
        </h3>
        <p className="text-xs text-slate-500 mb-3">
          Paste or upload a prior RM letter (strip out client names + PII first).
          Every uploaded sample is added to the prompt as a few-shot example so
          the generator mimics the writer's voice.
        </p>

        <label className="block text-xs font-medium text-slate-600 mb-1">
          Title (optional)
        </label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. priya-it-outperformer"
          className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 mb-3"
        />

        <label className="block text-xs font-medium text-slate-600 mb-1">
          Letter content
        </label>
        <textarea
          rows={14}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Dear Mr. Mehta…"
          className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 font-mono"
        />

        <div className="flex items-center gap-2 mt-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.txt"
            className="hidden"
            onChange={onFile}
          />
          <Button
            variant="secondary"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="w-4 h-4 mr-1" />
            Upload .md / .txt
          </Button>
          <Button onClick={submit} loading={uploading}>
            Save sample
          </Button>
        </div>
      </Card>

      <Card>
        <h3 className="text-sm font-semibold text-slate-900 mb-3">
          Saved samples ({samples.length})
        </h3>
        {loading ? (
          <Spinner size="sm" />
        ) : samples.length === 0 ? (
          <div className="text-sm text-slate-400 italic">
            No style samples uploaded yet.
          </div>
        ) : (
          <ul className="space-y-2">
            {samples.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between gap-2 border border-slate-200 rounded-lg px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="text-sm text-slate-800 truncate">{s.name}</div>
                  <div className="text-xs text-slate-400">
                    {Math.ceil(s.size / 1024)} KB · {s.updated_at?.slice(0, 10)}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => openPreview(s.id)}
                    className="text-slate-500 hover:text-primary-700 p-1"
                    title="Preview"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => remove(s.id)}
                    className="text-slate-400 hover:text-red-600 p-1"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {preview && (
          <div className="mt-4 border-t border-slate-200 pt-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-medium text-slate-600">
                Preview: {preview.id}
              </div>
              <button
                onClick={() => setPreview(null)}
                className="text-xs text-slate-500 hover:text-slate-800"
              >
                Close
              </button>
            </div>
            <pre className="text-xs whitespace-pre-wrap bg-slate-50 rounded-lg p-3 max-h-72 overflow-y-auto">
              {preview.content}
            </pre>
          </div>
        )}
      </Card>
    </div>
  )
}
