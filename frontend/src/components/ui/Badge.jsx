export default function Badge({ children, className = '', tone = 'slate' }) {
  const tones = {
    slate:   'bg-slate-100 text-slate-700 border-slate-200',
    primary: 'bg-primary-50 text-primary-700 border-primary-100',
    gold:    'bg-amber-50 text-amber-800 border-amber-200',
    success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    danger:  'bg-red-50 text-red-700 border-red-200',
  }
  return (
    <span
      className={
        'inline-flex items-center gap-1 text-xs font-medium ' +
        'px-2 py-0.5 rounded-full border ' +
        (tones[tone] || tones.slate) +
        ' ' + className
      }
    >
      {children}
    </span>
  )
}
