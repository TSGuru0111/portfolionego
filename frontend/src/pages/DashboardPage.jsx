// frontend/src/pages/DashboardPage.jsx
import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import DashboardKpiStrip from '../components/dashboard/DashboardKpiStrip';
import AllocationDonut from '../components/dashboard/AllocationDonut';
import DriftBars from '../components/dashboard/DriftBars';
import NetWorthSparkline from '../components/dashboard/NetWorthSparkline';
import RationaleTimeline from '../components/dashboard/RationaleTimeline';

function useAsync(fn, deps) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fn();
      setData(result);
    } catch (e) {
      setError(e.message ?? 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { run(); }, [run]);
  return { data, loading, error, refetch: run };
}

export default function DashboardPage() {
  const { id } = useParams();

  const portfolio  = useAsync(() => api.getPortfolio(id), [id]);
  const drift      = useAsync(() => api.getDrift(id), [id]);
  const snapshots  = useAsync(() => api.getSnapshots(id, 12), [id]);
  const events     = useAsync(() => api.getRationaleEvents(id), [id]);

  const clientName = portfolio.data?.client?.name ?? 'Client';

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <Link to={`/clients/${id}`} className="text-blue-600 hover:underline text-sm flex items-center gap-1">
          ← {clientName}
        </Link>
        <Link
          to={`/clients/${id}/report/new`}
          className="text-sm px-3 py-1.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700"
        >
          Generate report →
        </Link>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* KPI Strip */}
        <DashboardKpiStrip
          portfolio={portfolio.data}
          drift={drift.data}
          rationaleEvents={events.data}
        />

        {/* Two-column grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Left: Donut + Drift */}
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

          {/* Right: Sparkline */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <NetWorthSparkline
              snapshots={snapshots.data}
              loading={snapshots.loading}
              error={snapshots.error}
            />
          </div>
        </div>

        {/* Full-width Timeline */}
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <RationaleTimeline
            clientId={id}
            events={events.data}
            loading={events.loading}
            error={events.error}
            onEventLogged={events.refetch}
          />
        </div>
      </div>
    </div>
  );
}
