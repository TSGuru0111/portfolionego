import { useState } from 'react'
import { BookOpen, FileText, Rss } from 'lucide-react'

import AgentsEditor from '../components/config/AgentsEditor.jsx'
import FeedsEditor from '../components/config/FeedsEditor.jsx'
import StyleSamplesEditor from '../components/config/StyleSamplesEditor.jsx'
import BackLink from '../components/layout/BackLink'

const SUBTABS = [
  {
    id: 'agents',
    label: 'Agents & instructions',
    icon: BookOpen,
    blurb:
      'Markdown files loaded as system context for every report. House view, persona, structural rules.',
  },
  {
    id: 'samples',
    label: 'Style samples',
    icon: FileText,
    blurb:
      'Prior RM letters used as few-shot examples so the generator mimics the writer\u2019s voice.',
  },
  {
    id: 'feeds',
    label: 'News feeds',
    icon: Rss,
    blurb:
      'RSS sources, NewsAPI queries, and GNews sectors used during daily collection and per-client news lookup.',
  },
]

export default function ConfigPage() {
  const [active, setActive] = useState('agents')
  const current = SUBTABS.find((t) => t.id === active) ?? SUBTABS[0]

  return (
    <div className="space-y-6">
      <BackLink to="/dashboard" label="dashboard" />
      <div>
        <h1 className="font-serif text-2xl text-slate-900">Configuration</h1>
        <p className="text-sm text-slate-500 mt-1">
          Live-edit what the generator sees. Changes take effect on the next
          report.
        </p>
      </div>

      <div className="border-b border-slate-200 flex gap-1">
        {SUBTABS.map(({ id, label, icon: Icon }) => {
          const isActive = id === active
          return (
            <button
              key={id}
              onClick={() => setActive(id)}
              className={`px-4 py-2 -mb-px border-b-2 text-sm inline-flex items-center gap-2 ${
                isActive
                  ? 'border-primary-600 text-primary-700 font-medium'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          )
        })}
      </div>

      <p className="text-xs text-slate-500 -mt-3">{current.blurb}</p>

      {active === 'agents' && <AgentsEditor />}
      {active === 'samples' && <StyleSamplesEditor />}
      {active === 'feeds' && <FeedsEditor />}
    </div>
  )
}
