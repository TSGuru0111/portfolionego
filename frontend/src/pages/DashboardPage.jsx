// frontend/src/pages/DashboardPage.jsx
import { useParams, Link } from 'react-router-dom';

export default function DashboardPage() {
  const { id } = useParams();
  return (
    <div className="p-6">
      <Link to={`/clients/${id}`} className="text-blue-600 hover:underline text-sm">
        ← Back to client
      </Link>
      <h1 className="text-2xl font-bold mt-4">Dashboard (coming soon)</h1>
    </div>
  );
}
