// Indian-locale formatters. Mirror of backend/utils/formatters.py.

const INR_FMT = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export const formatINR = (amount) =>
  amount == null ? '—' : INR_FMT.format(amount)

export const formatPct = (value, decimals = 2) => {
  if (value == null) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

export const formatCr = (crores) =>
  crores == null ? '—' : `₹${Number(crores).toFixed(2)} Cr`

export const formatMonth = (monthStr) => {
  if (!monthStr) return '—'
  const [year, month] = monthStr.split('-')
  const idx = Number(month) - 1
  if (Number.isNaN(idx) || idx < 0 || idx > 11) return monthStr
  return new Date(Number(year), idx).toLocaleDateString('en-IN', {
    month: 'long',
    year:  'numeric',
  })
}

export const formatDateIN = (value) => {
  if (!value) return '—'
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-IN', {
    day:   '2-digit',
    month: 'long',
    year:  'numeric',
  })
}

export const returnColor = (value) =>
  value == null ? 'text-slate-500'
  : value >= 0   ? 'text-emerald-600'
  :                'text-red-600'
