import { useCallback, useEffect, useState } from 'react';
import { getApiBase } from '../config';

interface ProviderConnectionResponse {
  provider: string;
  status: 'connected' | 'error' | 'not_implemented';
  latency_ms: number | null;
  message: string | null;
  error: string | null;
  timestamp: string;
}

interface ProvidersListResponse {
  providers: string[];
  count: number;
  timestamp: string;
}

type ProviderStatus = ProviderConnectionResponse & {
  loading?: boolean;
};

const STATUS_COLORS = {
  connected: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-200',
    dot: 'bg-green-500',
  },
  error: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    border: 'border-red-200',
    dot: 'bg-red-500',
  },
  not_implemented: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-800',
    border: 'border-yellow-200',
    dot: 'bg-yellow-500',
  },
  loading: {
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    border: 'border-gray-200',
    dot: 'bg-gray-400',
  },
};

function StatusBadge({ status, loading }: { status: string; loading?: boolean }) {
  const colors = loading
    ? STATUS_COLORS.loading
    : STATUS_COLORS[status as keyof typeof STATUS_COLORS] || STATUS_COLORS.error;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
    >
      <span className={`w-2 h-2 rounded-full ${colors.dot} ${loading ? 'animate-pulse' : ''}`} />
      {loading ? 'Checking...' : status.replace('_', ' ')}
    </span>
  );
}

function ProviderCard({
  provider,
  onRefresh,
}: {
  provider: ProviderStatus;
  onRefresh: () => void;
}) {
  const colors = provider.loading
    ? STATUS_COLORS.loading
    : STATUS_COLORS[provider.status as keyof typeof STATUS_COLORS] || STATUS_COLORS.error;

  return (
    <div
      className={`bg-white rounded-lg shadow-sm border ${colors.border} p-4 hover:shadow-md transition-shadow`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">{provider.provider}</h3>
          <StatusBadge status={provider.status} loading={provider.loading} />
        </div>
        <button
          onClick={onRefresh}
          disabled={provider.loading}
          className="text-gray-400 hover:text-gray-600 disabled:opacity-50 p-1"
          title="Refresh"
        >
          <svg
            className={`w-4 h-4 ${provider.loading ? 'animate-spin' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>

      {provider.latency_ms !== null && (
        <div className="text-xs text-gray-500 mb-2">
          Latency: <span className="font-mono">{provider.latency_ms.toFixed(2)}ms</span>
        </div>
      )}

      {provider.message && <p className="text-sm text-gray-700 mb-2">{provider.message}</p>}

      {provider.error && (
        <p className="text-sm text-red-600 bg-red-50 rounded px-2 py-1 mt-2">{provider.error}</p>
      )}

      <div className="text-xs text-gray-400 mt-3 font-mono">
        {new Date(provider.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}

function SummaryStats({ providers }: { providers: ProviderStatus[] }) {
  const connected = providers.filter((p) => p.status === 'connected').length;
  const errors = providers.filter((p) => p.status === 'error').length;
  const notImplemented = providers.filter((p) => p.status === 'not_implemented').length;
  const loading = providers.filter((p) => p.loading).length;
  const total = providers.length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
      <div className="bg-white rounded-lg shadow-sm p-4 text-center">
        <div className="text-2xl font-bold text-gray-900">{total}</div>
        <div className="text-sm text-gray-500">Total</div>
      </div>
      <div className="bg-white rounded-lg shadow-sm p-4 text-center border-l-4 border-green-500">
        <div className="text-2xl font-bold text-green-600">{connected}</div>
        <div className="text-sm text-gray-500">Connected</div>
      </div>
      <div className="bg-white rounded-lg shadow-sm p-4 text-center border-l-4 border-red-500">
        <div className="text-2xl font-bold text-red-600">{errors}</div>
        <div className="text-sm text-gray-500">Errors</div>
      </div>
      <div className="bg-white rounded-lg shadow-sm p-4 text-center border-l-4 border-yellow-500">
        <div className="text-2xl font-bold text-yellow-600">{notImplemented}</div>
        <div className="text-sm text-gray-500">Not Implemented</div>
      </div>
      <div className="bg-white rounded-lg shadow-sm p-4 text-center border-l-4 border-gray-400">
        <div className="text-2xl font-bold text-gray-600">{loading}</div>
        <div className="text-sm text-gray-500">Checking</div>
      </div>
    </div>
  );
}

export function ProviderStatus() {
  const apiBase = getApiBase();
  const [providersList, setProvidersList] = useState<string[]>([]);
  const [providerStatuses, setProviderStatuses] = useState<Map<string, ProviderStatus>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchProvidersList = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/healthz/providers/connection`);
      if (!res.ok) throw new Error(`Failed to fetch providers list: ${res.status}`);
      const data: ProvidersListResponse = await res.json();
      setProvidersList(data.providers);
      return data.providers;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch providers list');
      return [];
    }
  }, [apiBase]);

  const checkProvider = useCallback(
    async (providerName: string) => {
      // Set loading state for this provider
      setProviderStatuses((prev) => {
        const newMap = new Map(prev);
        const existing = newMap.get(providerName);
        newMap.set(providerName, {
          provider: providerName,
          status: existing?.status || 'error',
          latency_ms: existing?.latency_ms || null,
          message: existing?.message || null,
          error: existing?.error || null,
          timestamp: existing?.timestamp || new Date().toISOString(),
          loading: true,
        });
        return newMap;
      });

      try {
        const res = await fetch(`${apiBase}/healthz/providers/connection/${providerName}`);
        const data: ProviderConnectionResponse = await res.json();

        setProviderStatuses((prev) => {
          const newMap = new Map(prev);
          newMap.set(providerName, { ...data, loading: false });
          return newMap;
        });
      } catch (err) {
        setProviderStatuses((prev) => {
          const newMap = new Map(prev);
          newMap.set(providerName, {
            provider: providerName,
            status: 'error',
            latency_ms: null,
            message: null,
            error: err instanceof Error ? err.message : 'Failed to check provider',
            timestamp: new Date().toISOString(),
            loading: false,
          });
          return newMap;
        });
      }
    },
    [apiBase],
  );

  const checkAllProviders = useCallback(
    async (providers: string[]) => {
      // Check all providers in parallel
      await Promise.all(providers.map((provider) => checkProvider(provider)));
      setLastRefresh(new Date());
    },
    [checkProvider],
  );

  const refreshAll = useCallback(async () => {
    setError(null);
    const providers = await fetchProvidersList();
    if (providers.length > 0) {
      await checkAllProviders(providers);
    }
  }, [fetchProvidersList, checkAllProviders]);

  // Initial load
  useEffect(() => {
    const init = async () => {
      setInitialLoading(true);
      await refreshAll();
      setInitialLoading(false);
    };
    init();
  }, [refreshAll]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const providers = providersList.map(
    (name) =>
      providerStatuses.get(name) || {
        provider: name,
        status: 'error' as const,
        latency_ms: null,
        message: null,
        error: 'Not checked yet',
        timestamp: new Date().toISOString(),
        loading: true,
      },
  );

  if (initialLoading && providers.length === 0) {
    return (
      <div className="min-h-screen bg-gray-100 py-8 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
              <p className="text-gray-600">Loading provider status...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-3xl font-bold text-gray-900">Provider Status</h1>
            <button
              onClick={refreshAll}
              className="inline-flex items-center gap-2 bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Refresh All
            </button>
          </div>
          <p className="text-gray-600">Connection status for all configured service providers</p>
          {lastRefresh && (
            <p className="text-sm text-gray-500 mt-1">
              Last refreshed: {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>

        {/* Error Alert */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg mb-6">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              {error}
            </div>
          </div>
        )}

        {/* Summary Stats */}
        <SummaryStats providers={providers} />

        {/* Provider Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {providers.map((provider) => (
            <ProviderCard
              key={provider.provider}
              provider={provider}
              onRefresh={() => checkProvider(provider.provider)}
            />
          ))}
        </div>

        {/* Empty State */}
        {providers.length === 0 && !initialLoading && (
          <div className="text-center py-12">
            <svg
              className="w-16 h-16 text-gray-400 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-1">No providers found</h3>
            <p className="text-gray-500">Could not retrieve the list of providers from the API.</p>
          </div>
        )}

        {/* Footer Info */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>
            API Endpoint:{' '}
            <code className="bg-gray-200 px-2 py-1 rounded">
              {apiBase}/healthz/providers/connection
            </code>
          </p>
          <p className="mt-1">Auto-refreshes every 30 seconds</p>
        </div>
      </div>
    </div>
  );
}

export default ProviderStatus;
