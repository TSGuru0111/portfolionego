import TopBar from './TopBar.jsx'

export default function PageWrapper({ children }) {
  return (
    <div className="min-h-screen bg-surface-50">
      <TopBar />
      <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
    </div>
  )
}
