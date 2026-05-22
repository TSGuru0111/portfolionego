# PortfolioNarrator — Frontend Guidelines
**Version:** 1.0 | **Date:** May 2026

---

## 1. Design Philosophy

PortfolioNarrator is a **premium B2B tool** used by professional wealth managers. The UI must communicate trust, precision, and sophistication — not startup-y playfulness. Think private banking dashboard, not fintech consumer app.

**Three design principles:**
1. **Clarity over cleverness** — RM should never be confused about what to click
2. **Data first** — numbers and content are heroes; chrome and decoration are secondary
3. **Premium but fast** — looks expensive, loads instantly

---

## 2. Folder Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/                    # Reusable primitives
│   │   │   ├── Button.jsx
│   │   │   ├── Card.jsx
│   │   │   ├── Badge.jsx
│   │   │   ├── Toast.jsx
│   │   │   ├── Spinner.jsx
│   │   │   ├── Banner.jsx         # Yellow warning banner (stale price)
│   │   │   └── Table.jsx
│   │   ├── layout/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── TopBar.jsx
│   │   │   └── PageWrapper.jsx
│   │   ├── client/
│   │   │   ├── ClientCard.jsx     # Dashboard client card
│   │   │   ├── HoldingsTable.jsx  # Portfolio holdings table
│   │   │   ├── ReturnSummary.jsx  # Portfolio vs Nifty summary
│   │   │   └── SectorChart.jsx    # Donut chart
│   │   ├── report/
│   │   │   ├── ReportViewer.jsx   # Streaming letter display
│   │   │   ├── SectionBlock.jsx   # Individual letter section
│   │   │   ├── LanguageToggle.jsx # EN/HI switch
│   │   │   └── QAScoreBadge.jsx   # QA score display
│   │   └── admin/
│   │       ├── TriggerPanel.jsx   # Manual job triggers
│   │       └── ErrorLogTable.jsx  # Error log viewer
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx
│   │   ├── ClientDetail.jsx
│   │   ├── ReportPage.jsx
│   │   └── AdminPage.jsx
│   ├── hooks/
│   │   ├── useAuth.js             # Supabase auth hook
│   │   ├── useStreamReport.js     # Streaming fetch hook
│   │   └── usePortfolio.js        # Portfolio data hook
│   ├── services/
│   │   ├── api.js                 # All FastAPI calls
│   │   └── supabase.js            # Supabase client init
│   ├── utils/
│   │   ├── formatters.js          # INR formatting, date formatting
│   │   └── constants.js           # API URL, sector colors, etc.
│   ├── App.jsx
│   └── main.jsx
├── public/
│   └── logo.svg                   # Firm logo placeholder
├── index.html
├── vite.config.js
├── tailwind.config.js
└── .env
```

---

## 3. Design System

### 3.1 Color Palette

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        // Primary — deep navy (wealth management feel)
        primary: {
          50:  '#f0f4ff',
          100: '#e0eaff',
          500: '#3b5bdb',
          600: '#2f4ac8',
          700: '#1e3a8a',
          900: '#0f1f5c',
        },
        // Gold accent — premium feel
        gold: {
          400: '#e6b800',
          500: '#d4af37',
          600: '#b8960c',
        },
        // Surface — dark backgrounds
        surface: {
          50:  '#f8fafc',
          100: '#f1f5f9',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
        // Semantic
        success: '#10b981',
        warning: '#f59e0b',
        danger:  '#ef4444',
        info:    '#3b82f6',
      },
    },
  },
}
```

### 3.2 Typography

```css
/* Use Inter for body text — downloaded locally to avoid Google Fonts issues */
@font-face {
  font-family: 'Inter';
  src: url('/fonts/Inter-Regular.woff2') format('woff2');
  font-weight: 400;
}
@font-face {
  font-family: 'Inter';
  src: url('/fonts/Inter-Bold.woff2') format('woff2');
  font-weight: 700;
}

/* Use Playfair Display for headings — wealth management feel */
@font-face {
  font-family: 'Playfair Display';
  src: url('/fonts/PlayfairDisplay-Bold.woff2') format('woff2');
  font-weight: 700;
}

/* Scale */
/* Display: Playfair Display Bold 32px — page titles */
/* Heading: Inter Bold 20px — section headers */
/* Body: Inter Regular 14px — content */
/* Caption: Inter Regular 12px — metadata, labels */
/* Mono: Roboto Mono 12px — numbers, tickers, codes */
```

### 3.3 Spacing

Use Tailwind's default spacing scale. No custom spacing. Stick to: `p-4`, `p-6`, `p-8`, `gap-4`, `gap-6`, `mb-4`, `mb-8`.

### 3.4 Shadows

```
Card: shadow-sm (subtle — no heavy shadows)
Modal: shadow-xl
Hover: shadow-md (transition-shadow duration-200)
```

### 3.5 Border Radius

- Cards: `rounded-xl`
- Buttons: `rounded-lg`
- Badges: `rounded-full`
- Tables: `rounded-none` (flat, clean)
- Inputs: `rounded-lg`

---

## 4. Component Patterns

### 4.1 Button Variants

```jsx
// Primary — main action (Generate Report, Download PDF)
<button className="bg-primary-600 hover:bg-primary-700 text-white
  font-semibold px-6 py-2.5 rounded-lg transition-colors duration-200
  disabled:opacity-50 disabled:cursor-not-allowed">
  Generate Report
</button>

// Secondary — supporting action (View Past Reports)
<button className="border border-slate-300 hover:border-primary-500
  text-slate-700 hover:text-primary-600 font-medium px-4 py-2
  rounded-lg transition-colors duration-200">
  View Past Reports
</button>

// Ghost — low emphasis (Cancel, Back)
<button className="text-slate-500 hover:text-slate-700
  font-medium px-4 py-2 rounded-lg hover:bg-slate-100
  transition-colors duration-200">
  Back
</button>

// Danger — destructive action
<button className="bg-red-50 hover:bg-red-100 text-red-600
  font-medium px-4 py-2 rounded-lg transition-colors duration-200">
  Delete
</button>
```

### 4.2 Card Pattern

```jsx
<div className="bg-white border border-slate-200 rounded-xl p-6
  hover:border-primary-300 hover:shadow-md transition-all duration-200
  cursor-pointer">
  {/* content */}
</div>
```

### 4.3 Stale Price Warning Banner

```jsx
// Show this when any holding price comes from cache
{hasStalePrices && (
  <div className="flex items-center gap-3 bg-amber-50 border border-amber-200
    rounded-lg px-4 py-3 text-sm text-amber-800 mb-4">
    <span>⚠️</span>
    <span>
      Some prices are as of <strong>{stalePriceDate}</strong> —
      live market data temporarily unavailable.
      Report will include a disclaimer.
    </span>
  </div>
)}
```

### 4.4 Streaming Report Viewer

```jsx
// ReportViewer.jsx
export function ReportViewer({ reportText, isStreaming }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-8
      max-w-3xl mx-auto font-serif leading-relaxed text-slate-800">

      {/* Sections render as they arrive */}
      {reportText.split('\n\n').map((para, i) => (
        <p key={i} className="mb-4 text-[15px] leading-8">
          {para}
        </p>
      ))}

      {/* Blinking cursor while streaming */}
      {isStreaming && (
        <span className="inline-block w-0.5 h-5 bg-primary-500
          animate-pulse ml-0.5" />
      )}
    </div>
  )
}
```

### 4.5 Loading States

Every async action must have a loading state. Never leave user staring at unchanged UI.

```jsx
// Generate report button with loading state
<button
  onClick={handleGenerate}
  disabled={isGenerating}
  className="...">
  {isGenerating ? (
    <span className="flex items-center gap-2">
      <Spinner size="sm" />
      Generating report...
    </span>
  ) : (
    'Generate Report'
  )}
</button>
```

---

## 5. Streaming Implementation

This is the most critical frontend pattern — do not use useState + setTimeout polling.

```javascript
// hooks/useStreamReport.js
export function useStreamReport() {
  const [reportText, setReportText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)

  const generateReport = async (clientId, month) => {
    setReportText('')
    setIsStreaming(true)
    setError(null)

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/reports/generate-stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${supabase.auth.getSession().access_token}`
          },
          body: JSON.stringify({ client_id: clientId, month }),
        }
      )

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Report generation failed')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        setReportText(prev => prev + chunk)
      }

    } catch (err) {
      setError(err.message)
      toast.error(err.message)
    } finally {
      setIsStreaming(false)
    }
  }

  return { reportText, isStreaming, error, generateReport }
}
```

---

## 6. API Service Layer

All FastAPI calls go through `services/api.js`. Never call fetch directly from components.

```javascript
// services/api.js
const API = import.meta.env.VITE_API_URL

const getAuthHeader = async () => {
  const { data } = await supabase.auth.getSession()
  return { 'Authorization': `Bearer ${data.session?.access_token}` }
}

export const api = {
  // Clients
  getClients: async () => {
    const headers = await getAuthHeader()
    const res = await fetch(`${API}/clients`, { headers })
    if (!res.ok) throw new Error('Failed to fetch clients')
    return res.json()
  },

  getClientPortfolio: async (clientId) => {
    const headers = await getAuthHeader()
    const res = await fetch(`${API}/clients/${clientId}/portfolio`, { headers })
    if (!res.ok) throw new Error('Failed to fetch portfolio')
    return res.json()
  },

  // Reports
  getReports: async (clientId) => {
    const headers = await getAuthHeader()
    const res = await fetch(`${API}/reports?client_id=${clientId}`, { headers })
    return res.json()
  },

  translateReport: async (reportId, language) => {
    const headers = await getAuthHeader()
    const res = await fetch(`${API}/reports/${reportId}/translate`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ language }),
    })
    return res.json()
  },

  exportPdf: async (reportId, lang = 'english') => {
    const headers = await getAuthHeader()
    const res = await fetch(
      `${API}/reports/${reportId}/export-pdf?lang=${lang}`,
      { headers }
    )
    const blob = await res.blob()
    return blob
  },

  // Admin
  triggerNewsCollection: async (adminSecret) => {
    const res = await fetch(
      `${API}/admin/trigger-news-collection?secret=${adminSecret}`,
      { method: 'POST' }
    )
    return res.json()
  },

  getErrorLogs: async (adminSecret) => {
    const res = await fetch(`${API}/admin/errors?secret=${adminSecret}`)
    return res.json()
  },
}
```

---

## 7. Number Formatting

All Indian number formatting must use Indian locale — not Western thousand separators.

```javascript
// utils/formatters.js

// ₹1,23,456.78 — Indian format
export const formatINR = (amount, decimals = 2) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount)
}

// 4.23% — return percentage
export const formatPct = (value, decimals = 2) => {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

// ₹2.47 Cr — crore shorthand for AUM
export const formatCr = (crores) => {
  return `₹${crores.toFixed(2)} Cr`
}

// April 2026
export const formatMonth = (monthStr) => {
  const [year, month] = monthStr.split('-')
  return new Date(year, month - 1).toLocaleDateString('en-IN', {
    month: 'long', year: 'numeric'
  })
}

// Green for positive, red for negative
export const returnColor = (value) =>
  value >= 0 ? 'text-emerald-600' : 'text-red-600'
```

---

## 8. Error Handling Standards

```javascript
// Every API call follows this pattern in components
const handleGenerate = async () => {
  try {
    await generateReport(clientId, selectedMonth)
    toast.success('Report generated successfully')
  } catch (err) {
    // User-friendly messages — never expose raw errors
    const message = err.message.includes('Portfolio has no holdings')
      ? 'This client has no portfolio data. Please add holdings first.'
      : err.message.includes('Could not compute')
      ? 'Market data temporarily unavailable. Please try again in a few minutes.'
      : 'Something went wrong. Please try again.'

    toast.error(message)
  }
}
```

---

## 9. Accessibility

- All interactive elements have `aria-label`
- Color is never the only signal (red/green always has icon + text)
- Loading states announced to screen readers via `aria-live="polite"`
- Tab order follows logical reading order
- Minimum contrast ratio 4.5:1 for all text

---

## 10. Do Not Do

- ❌ Never use `alert()` or `confirm()` — use Toast or Modal
- ❌ Never fetch directly in components — always use `services/api.js`
- ❌ Never hardcode the API URL — always `import.meta.env.VITE_API_URL`
- ❌ Never store JWT token manually — Supabase handles this
- ❌ Never show raw error messages from backend to users
- ❌ Never use inline styles — Tailwind classes only
- ❌ Never leave a button without a loading state for async actions
- ❌ Never use Axios — use native fetch (streaming support required)
