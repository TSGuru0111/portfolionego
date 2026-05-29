// frontend/src/pages/ClientSharePage.jsx
import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import DashboardKpiStrip from '../components/dashboard/DashboardKpiStrip';
import AllocationDonut from '../components/dashboard/AllocationDonut';
import DriftBars from '../components/dashboard/DriftBars';
import NetWorthSparkline from '../components/dashboard/NetWorthSparkline';
import RationaleTimeline from '../components/dashboard/RationaleTimeline';

const API = import.meta.env.VITE_API_URL ?? '';

async function publicFetch(path) {
  const res = await fetch(`${API}${path}`);
  if (res.status === 403) throw new Error('expired');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function usePublicAsync(path) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await publicFetch(path));
    } catch (e) {
      setError(e.message ?? 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => { run(); }, [run]);
  return { data, loading, error };
}

export default function ClientSharePage() {
  const { token } = useParams();

  const portfolio = usePublicAsync(`/share/${token}/portfolio`);
  const drift     = usePublicAsync(`/share/${token}/drift`);
  const snapshots = usePublicAsync(`/share/${token}/snapshots`);
  const events    = usePublicAsync(`/share/${token}/rationale-events`);

  const isExpired = [portfolio, drift, snapshots, events].some(
    (s) => s.error === 'expired'
  );

  if (isExpired) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          <p className="text-4xl mb-4">🔒</p>
          <h1 className="text-xl font-semibold text-gray-900 mb-2">Link expired</h1>
          <p className="text-gray-500 text-sm">
            This link has expired or is invalid. Please contact your advisor.
          </p>
        </div>
      </div>
    );
  }

  const clientName = portfolio.data?.client?.name ?? '';

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-700">Portfolionarator</span>
        {clientName && <span className="text-sm text-gray-500">{clientName}</span>}
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        <DashboardKpiStrip
          portfolio={portfolio.data}
          drift={drift.data}
          rationaleEvents={events.data}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-6">
            <AllocationDonut
              drift={drift.data}
              loading={drift.loading}
              error={drift.error}
            />
            <DriftBars
              drift={drift.data}
              loading={drift.loading}
              error={drift.error}
            />
          </div>

          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <NetWorthSparkline
              snapshots={snapshots.data}
              loading={snapshots.loading}
              error={snapshots.error}
            />
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <RationaleTimeline
            clientId={null}
            events={events.data}
            loading={events.loading}
            error={events.error}
            readOnly={true}
          />
        </div>
      </div>
    </div>
  );
}
