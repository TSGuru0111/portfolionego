import { useState } from 'react'
import toast from 'react-hot-toast'

import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import { api } from '../../services/api.js'

export default function ErrorLogTable() {
  const [secret, setSecret] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    if (!secret) {
      toast.error('Enter the admin secret first.')
      return
    }
    setLoading(true)
    try {
      const res = await api.getErrorLogs(secret)
      setRows(Array.isArray(res) ? res : res.errors ?? [])
    } catch (err) {
      toast.error(`Error log fetch failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold text-slate-900 mb-3">
        Recent errors
      </h2>
      <div className="flex gap-2 mb-3">
        <input
          type="password"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="Admin secret"
          className="flex-1 text-sm border border-slate-300 rounded-lg px-3 py-2"
        />
        <Button variant="secondary" loading={loading} onClick={refresh}>
          Refresh
        </Button>
      </div>

      {rows.length === 0 ? (
        <div className="text-sm text-slate-400 italic">
          {loading ? 'Loading…' : 'No errors loaded yet.'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="text-left py-2">Job</th>
                <th className="text-left py-2">Error</th>
                <th className="text-left py-2">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="py-2 font-mono text-xs text-slate-700">{row.job}</td>
                  <td className="py-2 text-slate-800">{row.error}</td>
                  <td className="py-2 text-slate-500">{row.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
