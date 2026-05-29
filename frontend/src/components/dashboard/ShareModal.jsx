// frontend/src/components/dashboard/ShareModal.jsx
import { useState, useEffect } from 'react';
import { api } from '../../services/api';

const EXPIRY_OPTIONS = [7, 30, 90];

export default function ShareModal({ clientId, onClose }) {
  const [selectedDays, setSelectedDays] = useState(30);
  const [shareUrl, setShareUrl]         = useState(null);
  const [expiresAt, setExpiresAt]       = useState(null);
  const [generating, setGenerating]     = useState(false);
  const [copied, setCopied]             = useState(false);
  const [error, setError]               = useState(null);

  useEffect(() => {
    api.getShareToken(clientId)
      .then((data) => {
        setShareUrl(data.share_url);
        setExpiresAt(data.expires_at);
      })
      .catch(() => {
        // 404 = no existing token; stay on picker
      });
  }, [clientId]);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const data = await api.createShareToken(clientId, selectedDays);
      setShareUrl(data.share_url);
      setExpiresAt(data.expires_at);
    } catch (err) {
      setError(err.message ?? 'Failed to generate link. Please try again.');
    } finally {
      setGenerating(false);
    }
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function formatExpiry(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Share with client</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-red-700 text-sm">{error}</div>
        )}

        {shareUrl ? (
          <div>
            <p className="text-sm text-gray-600 mb-1">Active link — expires {formatExpiry(expiresAt)}</p>
            <div className="flex gap-2 mb-4">
              <input
                readOnly
                value={shareUrl}
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-700 truncate"
              />
              <button
                onClick={handleCopy}
                className="px-3 py-2 text-sm rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 whitespace-nowrap"
              >
                {copied ? 'Copied ✓' : 'Copy link'}
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-3">Generate a new link to change the expiry.</p>
          </div>
        ) : (
          <p className="text-sm text-gray-600 mb-4">No active link. Generate one below.</p>
        )}

        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Link validity</p>
          <div className="flex gap-2 mb-4">
            {EXPIRY_OPTIONS.map((days) => (
              <button
                key={days}
                type="button"
                onClick={() => setSelectedDays(days)}
                className={`flex-1 py-1.5 text-sm rounded-lg border font-medium transition-colors ${
                  selectedDays === days
                    ? 'bg-blue-600 border-blue-600 text-white'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                {days} days
              </button>
            ))}
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full py-2 text-sm rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {generating ? 'Generating…' : shareUrl ? 'Generate new link' : 'Generate link'}
          </button>
        </div>
      </div>
    </div>
  );
}
