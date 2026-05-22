import { LogOut, Settings, Sliders, Workflow } from 'lucide-react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth.js'

const TABS = [
  { to: '/dashboard', label: 'Workflow', icon: Workflow, match: ['/dashboard', '/clients'] },
  { to: '/config', label: 'Config', icon: Sliders, match: ['/config'] },
]

export default function TopBar() {
  const { session, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = async () => {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <header className="bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
        <Link to="/dashboard" className="flex items-center gap-3">
          <img src="/logo.svg" alt="" className="w-8 h-8" />
          <div>
            <div className="font-serif text-lg text-primary-700 leading-tight">
              PortfolioNarrator
            </div>
            <div className="text-xs text-slate-500 -mt-0.5">
              Private Wealth Reporting
            </div>
          </div>
        </Link>

        <nav className="flex items-center gap-1 text-sm">
          {TABS.map(({ to, label, icon: Icon, match }) => {
            const active = match.some((m) => location.pathname.startsWith(m))
            return (
              <NavLink
                key={to}
                to={to}
                className={`px-3 py-1.5 rounded-lg inline-flex items-center gap-1.5 ${
                  active
                    ? 'bg-primary-50 text-primary-700 font-medium'
                    : 'text-slate-600 hover:text-primary-700 hover:bg-slate-100'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </NavLink>
            )
          })}

          <Link
            to="/admin"
            className="px-3 py-1.5 text-slate-600 hover:text-primary-700 hover:bg-slate-100 rounded-lg inline-flex items-center gap-1.5"
          >
            <Settings className="w-4 h-4" /> Admin
          </Link>
          {session ? (
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 text-slate-600 hover:text-red-600 hover:bg-slate-100 rounded-lg inline-flex items-center gap-1.5"
            >
              <LogOut className="w-4 h-4" /> Sign out
            </button>
          ) : null}
        </nav>
      </div>
    </header>
  )
}
