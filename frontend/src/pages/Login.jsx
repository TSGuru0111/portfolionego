import { useState } from 'react'
import toast from 'react-hot-toast'
import { Navigate, useNavigate } from 'react-router-dom'

import Button from '../components/ui/Button.jsx'
import { useAuth } from '../hooks/useAuth.js'

export default function Login() {
  const { session, signIn, loading } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  if (loading) return null
  if (session) return <Navigate to="/dashboard" replace />

  const handleSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await signIn(email, password)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      toast.error(err.message || 'Invalid email or password')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm bg-white border border-slate-200 rounded-2xl p-8 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-6">
          <img src="/logo.svg" alt="" className="w-9 h-9" />
          <div>
            <div className="font-serif text-xl text-primary-700 leading-tight">
              PortfolioNarrator
            </div>
            <div className="text-xs text-slate-500">RM sign in</div>
          </div>
        </div>

        <label className="block text-xs font-medium text-slate-600 mb-1">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 mb-4"
        />

        <label className="block text-xs font-medium text-slate-600 mb-1">Password</label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 mb-6"
        />

        <Button type="submit" className="w-full" loading={busy}>
          Sign in
        </Button>
      </form>
    </div>
  )
}
