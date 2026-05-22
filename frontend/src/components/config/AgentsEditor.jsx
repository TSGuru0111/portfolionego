import { useEffect, useState } from 'react'
import { FilePlus, Save, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'

import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import Spinner from '../ui/Spinner.jsx'
import { api } from '../../services/api.js'

export default function AgentsEditor() {
  const [files, setFiles] = useState([])
  const [active, setActive] = useState(null)
  const [content, setContent] = useState('')
  const [dirty, setDirty] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const list = await api.listAgents()
      setFiles(list)
      if (list.length && !active) {
        await load(list[0].name)
      }
    } catch (err) {
      toast.error(err.message || 'Failed to load agents')
    } finally {
      setLoading(false)
    }
  }

  const load = async (name) => {
    try {
      const res = await api.getAgent(name)
      setActive(name)
      setContent(res.content)
      setDirty(false)
    } catch (err) {
      toast.error(err.message || 'Load failed')
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const save = async () => {
    if (!active) return
    setSaving(true)
    try {
      await api.saveAgent(active, content)
      toast.success('Saved')
      setDirty(false)
      refresh()
    } catch (err) {
      toast.error(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const createNew = async () => {
    const name = window.prompt('New file name (e.g. RM_PROFILE.md)')
    if (!name) return
    try {
      await api.saveAgent(name, `# ${name.replace(/\.md$/, '')}\n\n`)
      toast.success('Created')
      await refresh()
      await load(name.endsWith('.md') ? name : `${name}.md`)
    } catch (err) {
      toast.error(err.message || 'Create failed')
    }
  }

  const remove = async (name) => {
    if (!window.confirm(`Delete ${name}?`)) return
    try {
      await api.deleteAgent(name)
      toast.success('Deleted')
      if (active === name) {
        setActive(null)
        setContent('')
      }
      refresh()
    } catch (err) {
      toast.error(err.message || 'Delete failed')
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-4">
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-900">Files</h3>
          <button
            onClick={createNew}
            className="text-xs text-primary-700 inline-flex items-center gap-1"
          >
            <FilePlus className="w-3.5 h-3.5" /> New
          </button>
        </div>
        {loading ? (
          <Spinner size="sm" />
        ) : files.length === 0 ? (
          <div className="text-xs text-slate-400 italic">No files yet.</div>
        ) : (
          <ul className="space-y-1">
            {files.map((f) => (
              <li key={f.name} className="flex items-center gap-1">
                <button
                  onClick={() => load(f.name)}
                  className={`flex-1 text-left text-sm rounded-md px-2 py-1.5 ${
                    active === f.name
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  {f.name}
                </button>
                <button
                  onClick={() => remove(f.name)}
                  className="text-slate-400 hover:text-red-600 p-1"
                  title="Delete"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        {!active ? (
          <div className="text-sm text-slate-400 italic">
            Select a file on the left, or click + New to create one.
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-900">
                {active}
                {dirty && <span className="ml-2 text-xs text-amber-600">• unsaved</span>}
              </h3>
              <Button onClick={save} loading={saving} disabled={!dirty}>
                <Save className="w-4 h-4 mr-1" /> Save
              </Button>
            </div>
            <textarea
              value={content}
              onChange={(e) => {
                setContent(e.target.value)
                setDirty(true)
              }}
              rows={22}
              className="w-full text-sm font-mono border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-300"
              spellCheck={false}
            />
            <p className="text-xs text-slate-400 mt-2">
              These files are loaded as system context every time a report is generated.
            </p>
          </>
        )}
      </Card>
    </div>
  )
}
