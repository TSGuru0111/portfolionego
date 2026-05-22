import { useState } from 'react'
import toast from 'react-hot-toast'

import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import { api } from '../../services/api.js'

export default function TriggerPanel() {
  const [secret, setSecret] = useState('')
  const [busy, setBusy] = useState(null)

  const run = async (label, fn) => {
    if (!secret) {
      toast.error('Enter the admin secret first.')
      return
    }
    setBusy(label)
    try {
      const res = await fn(secret)
      toast.success(`${label}: ${res.status ?? 'ok'}`)
    } catch (err) {
      toast.error(`${label} failed: ${err.message}`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold text-slate-900 mb-3">
        Manual triggers
      </h2>
      <input
        type="password"
        value={secret}
        onChange={(e) => setSecret(e.target.value)}
        placeholder="Admin secret"
        className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 mb-4"
      />
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          loading={busy === 'News'}
          onClick={() => run('News', api.triggerNewsCollection)}
        >
          Collect News Now
        </Button>
        <Button
          variant="secondary"
          loading={busy === 'Weekly'}
          onClick={() => run('Weekly', api.triggerWeeklySummary)}
        >
          Run Weekly Summary
        </Button>
        <Button
          variant="secondary"
          loading={busy === 'All Reports'}
          onClick={() => run('All Reports', api.triggerAllReports)}
        >
          Generate All Reports
        </Button>
      </div>
    </Card>
  )
}
