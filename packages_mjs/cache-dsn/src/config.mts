/**
 * Configuration utilities for cache-dsn
 */

import type {
  DnsCacheConfig,
  HealthCheckConfig,
  LoadBalanceStrategy,
  ResolvedEndpoint,
} from './types.mjs';

/**
 * Default health check configuration
 */
export const DEFAULT_HEALTH_CHECK_CONFIG: Required<HealthCheckConfig> = {
  enabled: false,
  intervalMs: 30000,
  timeoutMs: 5000,
  unhealthyThreshold: 3,
  healthyThreshold: 2,
};

/**
 * Default DNS cache configuration
 */
export const DEFAULT_DNS_CACHE_CONFIG: Required<Omit<DnsCacheConfig, 'id'>> = {
  defaultTtlMs: 60000, // 1 minute
  minTtlMs: 1000, // 1 second
  maxTtlMs: 300000, // 5 minutes
  maxEntries: 1000,
  respectDnsTtl: true,
  negativeTtlMs: 30000, // 30 seconds
  staleWhileRevalidate: true,
  staleGracePeriodMs: 5000,
  loadBalanceStrategy: 'round-robin',
  healthCheck: DEFAULT_HEALTH_CHECK_CONFIG,
};

/**
 * Merge user config with defaults
 */
export function mergeConfig(config: DnsCacheConfig): Required<DnsCacheConfig> {
  const healthCheck: Required<HealthCheckConfig> = {
    ...DEFAULT_HEALTH_CHECK_CONFIG,
    ...config.healthCheck,
  };

  return {
    id: config.id,
    defaultTtlMs: config.defaultTtlMs ?? DEFAULT_DNS_CACHE_CONFIG.defaultTtlMs,
    minTtlMs: config.minTtlMs ?? DEFAULT_DNS_CACHE_CONFIG.minTtlMs,
    maxTtlMs: config.maxTtlMs ?? DEFAULT_DNS_CACHE_CONFIG.maxTtlMs,
    maxEntries: config.maxEntries ?? DEFAULT_DNS_CACHE_CONFIG.maxEntries,
    respectDnsTtl: config.respectDnsTtl ?? DEFAULT_DNS_CACHE_CONFIG.respectDnsTtl,
    negativeTtlMs: config.negativeTtlMs ?? DEFAULT_DNS_CACHE_CONFIG.negativeTtlMs,
    staleWhileRevalidate:
      config.staleWhileRevalidate ?? DEFAULT_DNS_CACHE_CONFIG.staleWhileRevalidate,
    staleGracePeriodMs: config.staleGracePeriodMs ?? DEFAULT_DNS_CACHE_CONFIG.staleGracePeriodMs,
    loadBalanceStrategy: config.loadBalanceStrategy ?? DEFAULT_DNS_CACHE_CONFIG.loadBalanceStrategy,
    healthCheck,
  };
}

/**
 * Clamp TTL within configured bounds
 */
export function clampTtl(ttlMs: number, minTtlMs: number, maxTtlMs: number): number {
  return Math.min(Math.max(ttlMs, minTtlMs), maxTtlMs);
}

/**
 * Calculate if a cached entry is expired
 */
export function isExpired(expiresAt: number, now: number = Date.now()): boolean {
  return now >= expiresAt;
}

/**
 * Calculate if a cached entry is within the stale grace period
 */
export function isWithinGracePeriod(
  expiresAt: number,
  gracePeriodMs: number,
  now: number = Date.now()
): boolean {
  return now < expiresAt + gracePeriodMs;
}

/**
 * Select an endpoint using the specified load balancing strategy
 */
export function selectEndpoint(
  endpoints: ResolvedEndpoint[],
  strategy: LoadBalanceStrategy,
  state: LoadBalanceState
): ResolvedEndpoint | undefined {
  // Filter to only healthy endpoints
  const healthyEndpoints = endpoints.filter((e) => e.healthy);
  if (healthyEndpoints.length === 0) {
    // Fall back to all endpoints if none are healthy
    if (endpoints.length === 0) return undefined;
    return endpoints[0];
  }

  switch (strategy) {
    case 'round-robin':
      return selectRoundRobin(healthyEndpoints, state);
    case 'random':
      return selectRandom(healthyEndpoints);
    case 'weighted':
      return selectWeighted(healthyEndpoints);
    case 'least-connections':
      return selectLeastConnections(healthyEndpoints, state);
    case 'power-of-two':
      return selectPowerOfTwo(healthyEndpoints, state);
    default:
      return healthyEndpoints[0];
  }
}

/**
 * Load balance state for stateful strategies
 */
export interface LoadBalanceState {
  /** Current index for round-robin */
  roundRobinIndex: Map<string, number>;
  /** Active connections per endpoint */
  activeConnections: Map<string, number>;
}

/**
 * Create initial load balance state
 */
export function createLoadBalanceState(): LoadBalanceState {
  return {
    roundRobinIndex: new Map(),
    activeConnections: new Map(),
  };
}

/**
 * Get endpoint key for state tracking
 */
export function getEndpointKey(endpoint: ResolvedEndpoint): string {
  return `${endpoint.host}:${endpoint.port}`;
}

/**
 * Round-robin selection
 */
function selectRoundRobin(
  endpoints: ResolvedEndpoint[],
  state: LoadBalanceState
): ResolvedEndpoint {
  // Use a global key for round-robin across all DSNs
  const key = endpoints.map(getEndpointKey).sort().join(',');
  const currentIndex = state.roundRobinIndex.get(key) ?? 0;
  const endpoint = endpoints[currentIndex % endpoints.length];
  state.roundRobinIndex.set(key, (currentIndex + 1) % endpoints.length);
  return endpoint;
}

/**
 * Random selection
 */
function selectRandom(endpoints: ResolvedEndpoint[]): ResolvedEndpoint {
  const index = Math.floor(Math.random() * endpoints.length);
  return endpoints[index];
}

/**
 * Weighted random selection
 */
function selectWeighted(endpoints: ResolvedEndpoint[]): ResolvedEndpoint {
  const totalWeight = endpoints.reduce((sum, e) => sum + (e.weight ?? 1), 0);
  let random = Math.random() * totalWeight;

  for (const endpoint of endpoints) {
    random -= endpoint.weight ?? 1;
    if (random <= 0) {
      return endpoint;
    }
  }

  return endpoints[endpoints.length - 1];
}

/**
 * Least connections selection
 */
function selectLeastConnections(
  endpoints: ResolvedEndpoint[],
  state: LoadBalanceState
): ResolvedEndpoint {
  let minConnections = Infinity;
  let selected = endpoints[0];

  for (const endpoint of endpoints) {
    const key = getEndpointKey(endpoint);
    const connections = state.activeConnections.get(key) ?? 0;
    if (connections < minConnections) {
      minConnections = connections;
      selected = endpoint;
    }
  }

  return selected;
}

/**
 * Power of Two Choices selection
 * Picks two random endpoints and chooses the one with fewer connections
 */
function selectPowerOfTwo(
  endpoints: ResolvedEndpoint[],
  state: LoadBalanceState
): ResolvedEndpoint {
  if (endpoints.length === 1) return endpoints[0];

  // Pick two random endpoints
  const idx1 = Math.floor(Math.random() * endpoints.length);
  let idx2 = Math.floor(Math.random() * (endpoints.length - 1));
  if (idx2 >= idx1) idx2++;

  const endpoint1 = endpoints[idx1];
  const endpoint2 = endpoints[idx2];

  const conn1 = state.activeConnections.get(getEndpointKey(endpoint1)) ?? 0;
  const conn2 = state.activeConnections.get(getEndpointKey(endpoint2)) ?? 0;

  return conn1 <= conn2 ? endpoint1 : endpoint2;
}

/**
 * Parse a DSN string into components
 */
export function parseDsn(dsn: string): { host: string; port?: number; protocol?: string } {
  // Handle URLs
  if (dsn.includes('://')) {
    try {
      const url = new URL(dsn);
      return {
        protocol: url.protocol.replace(':', ''),
        host: url.hostname,
        port: url.port ? parseInt(url.port, 10) : undefined,
      };
    } catch {
      // Fall through to simple parsing
    }
  }

  // Handle host:port format
  const colonIndex = dsn.lastIndexOf(':');
  if (colonIndex > 0) {
    const port = parseInt(dsn.substring(colonIndex + 1), 10);
    if (!isNaN(port)) {
      return {
        host: dsn.substring(0, colonIndex),
        port,
      };
    }
  }

  return { host: dsn };
}

/**
 * Sleep for a specified duration
 */
export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new Error('Aborted'));
      return;
    }

    const timer = setTimeout(resolve, ms);

    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new Error('Aborted'));
    });
  });
}

export default {
  DEFAULT_DNS_CACHE_CONFIG,
  DEFAULT_HEALTH_CHECK_CONFIG,
  mergeConfig,
  clampTtl,
  isExpired,
  isWithinGracePeriod,
  selectEndpoint,
  createLoadBalanceState,
  getEndpointKey,
  parseDsn,
  sleep,
};
