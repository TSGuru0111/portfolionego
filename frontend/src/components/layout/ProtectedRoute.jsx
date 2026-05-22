import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth.js'
import PageWrapper from './PageWrapper.jsx'
import Spinner from '../ui/Spinner.jsx'

export default function ProtectedRoute() {
  const { session, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-primary-600">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!session) return <Navigate to="/login" replace />

  return (
    <PageWrapper>
      <Outlet />
    </PageWrapper>
  )
}
