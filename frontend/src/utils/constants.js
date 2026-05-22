export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const SECTOR_COLORS = {
  IT:        '#3b5bdb',
  BFSI:      '#1e3a8a',
  Pharma:    '#10b981',
  FMCG:      '#d4af37',
  Energy:    '#f59e0b',
  Telecom:   '#8b5cf6',
  Materials: '#ef4444',
  Fintech:   '#06b6d4',
  Other:     '#64748b',
}

export const RISK_LABELS = {
  conservative: { label: 'Conservative', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  moderate:     { label: 'Moderate',     color: 'bg-amber-50 text-amber-700 border-amber-200' },
  aggressive:   { label: 'Aggressive',   color: 'bg-red-50 text-red-700 border-red-200' },
}
