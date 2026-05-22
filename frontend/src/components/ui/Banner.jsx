import { AlertTriangle } from 'lucide-react'

export default function Banner({ children, tone = 'warning', icon = true }) {
  const tones = {
    warning: 'bg-amber-50 border-amber-200 text-amber-800',
    info:    'bg-primary-50 border-primary-100 text-primary-700',
    danger:  'bg-red-50 border-red-200 text-red-700',
  }
  return (
    <div
      className={
        'flex items-start gap-3 border rounded-lg px-4 py-3 text-sm mb-4 ' +
        (tones[tone] || tones.warning)
      }
    >
      {icon ? <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> : null}
      <div>{children}</div>
    </div>
  )
}
