import { Navigate, Route, Routes } from 'react-router-dom'

import AdminPage from './pages/AdminPage.jsx'
import ClientDetail from './pages/ClientDetail.jsx'
import ConfigPage from './pages/ConfigPage.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Login from './pages/Login.jsx'
import ReportPage from './pages/ReportPage.jsx'
import ProtectedRoute from './components/layout/ProtectedRoute.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/clients/:id" element={<ClientDetail />} />
        <Route path="/clients/:id/report/:reportId" element={<ReportPage />} />
        <Route path="/config" element={<ConfigPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
