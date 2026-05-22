import { useEffect, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import toast from 'react-hot-toast'

import ClientCard from '../components/client/ClientCard.jsx'
import Spinner from '../components/ui/Spinner.jsx'
import { api } from '../services/api.js'

export default function Dashboard() {
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')

  useEffect(() => {
    api
      .getClients()
      .then((res) => setClients(res))
      .catch((err) => toast.error(err.message || 'Failed to load clients'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return clients
    return clients.filter((c) => c.name.toLowerCase().includes(q))
  }, [clients, query])

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="font-serif text-2xl text-slate-900">HNI clients</h1>
          <p className="text-sm text-slate-500 mt-1">
            {clients.length} client{clients.length === 1 ? '' : 's'} under your management
          </p>
        </div>
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name…"
            className="text-sm border border-slate-300 rounded-lg pl-9 pr-3 py-2 w-64"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-primary-600">
          <Spinner size="lg" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-sm text-slate-500 italic">
          {clients.length === 0
            ? 'No clients yet — backend may not be wired or DB is empty.'
            : 'No clients match this search.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((c) => (
            <ClientCard key={c.id} client={c} />
          ))}
        </div>
      )}
    </div>
  )
}
