import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function BackLink({ to, label }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-primary-700"
    >
      <ArrowLeft className="w-4 h-4" />
      Back to {label}
    </Link>
  )
}
