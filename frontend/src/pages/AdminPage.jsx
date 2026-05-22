import TriggerPanel from '../components/admin/TriggerPanel.jsx'
import ErrorLogTable from '../components/admin/ErrorLogTable.jsx'

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-2xl text-slate-900">Admin console</h1>
        <p className="text-sm text-slate-500 mt-1">
          Manually trigger background jobs and inspect recent failures.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TriggerPanel />
        <ErrorLogTable />
      </div>
    </div>
  )
}
