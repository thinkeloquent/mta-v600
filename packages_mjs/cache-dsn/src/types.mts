/**
 * Type definitions for cache-dsn
 */

/**
 * A resolved endpoint from DNS/service discovery
 */
export interface ResolvedEndpoint {
  /** The resolved IP address or hostname */
  host: string;
  /** The port number */
  port: number;
  /** Optional weight for load balancing (higher = more traffic) */
  weight?: number;
  /** Optional priority (lower = higher priority) */
  priority?: number;
  /** Whether this endpoint is considered healthy */
  healthy: boolean;
  /** Last time this endpoint was checked */
  lastChecked?: number;
  /** Custom metadata */
  metadata?: Record<string, unknown>;
}

/**
 * A cached DNS entry
 */
export interface CachedEntry {
  /** The original DSN/hostname that was resolved */
  dsn: string;
  /** List of resolved endpoints */
  endpoints: ResolvedEndpoint[];
  /** When this entry was resolved */
  resolvedAt: number;
  /** When this entry expires (Unix timestamp ms) */
  expiresAt: number;
  /** TTL in milliseconds */
  ttlMs: number;
  /** Number of times this entry has been used */
  hitCount: number;
  /** Error message if this is a negative cache entry */
  error?: string;
}

/**
 * Result of a resolution operation
 */
export interface ResolutionResult {
  /** The resolved endpoints */
  endpoints: ResolvedEndpoint[];
  /** Whether this result came from cache */
  fromCache: boolean;
  /** Time until cache expires (ms), or 0 if fresh resolution */
  ttlRemainingMs: number;
  /** Resolution time in milliseconds */
  resolutionTimeMs: number;
}

/**
 * Load balancing strategy
 */
export type LoadBalanceStrategy =
  | 'round-robin'
  | 'random'
  | 'weighted'
  | 'least-connections'
  | 'power-of-two';

/**
 * Configuration for the DNS cache resolver
 */
export interface DnsCacheConfig {
  /** Unique identifier for this resolver instance */
  id: string;
  /** Default TTL for cached entries (ms). Default: 60000 (1 minute) */
  defaultTtlMs?: number;
  /** Minimum TTL (prevents overly aggressive caching). Default: 1000 (1 second) */
  minTtlMs?: number;
  /** Maximum TTL (prevents stale data). Default: 300000 (5 minutes) */
  maxTtlMs?: number;
  /** Maximum number of cached entries. Default: 1000 */
  maxEntries?: number;
  /** Whether to respect DNS TTL from response. Default: true */
  respectDnsTtl?: boolean;
  /** Negative cache TTL for failed lookups (ms). Default: 30000 (30 seconds) */
  negativeTtlMs?: number;
  /** Whether to enable stale-while-revalidate. Default: true */
  staleWhileRevalidate?: boolean;
  /** Grace period for serving stale data while revalidating (ms). Default: 5000 */
  staleGracePeriodMs?: number;
  /** Load balancing strategy. Default: 'round-robin' */
  loadBalanceStrategy?: LoadBalanceStrategy;
  /** Health check configuration */
  healthCheck?: HealthCheckConfig;
}

/**
 * Health check configuration
 */
export interface HealthCheckConfig {
  /** Whether to enable health checks. Default: false */
  enabled?: boolean;
  /** Interval between health checks (ms). Default: 30000 */
  intervalMs?: number;
  /** Timeout for health check (ms). Default: 5000 */
  timeoutMs?: number;
  /** Number of consecutive failures before marking unhealthy. Default: 3 */
  unhealthyThreshold?: number;
  /** Number of consecutive successes before marking healthy. Default: 2 */
  healthyThreshold?: number;
}

/**
 * Statistics from the DNS cache
 */
export interface DnsCacheStats {
  /** Total number of cached entries */
  totalEntries: number;
  /** Total cache hits */
  cacheHits: number;
  /** Total cache misses */
  cacheMisses: number;
  /** Cache hit ratio (0-1) */
  hitRatio: number;
  /** Total stale-while-revalidate hits */
  staleHits: number;
  /** Average resolution time (ms) */
  avgResolutionTimeMs: number;
  /** Total healthy endpoints across all entries */
  healthyEndpoints: number;
  /** Total unhealthy endpoints across all entries */
  unhealthyEndpoints: number;
}

/**
 * Events emitted by the DNS cache resolver
 */
export type DnsCacheEvent =
  | { type: 'cache:hit'; dsn: string; ttlRemainingMs: number }
  | { type: 'cache:miss'; dsn: string }
  | { type: 'cache:stale'; dsn: string; revalidating: boolean }
  | { type: 'cache:expired'; dsn: string }
  | { type: 'cache:evicted'; dsn: string; reason: 'ttl' | 'capacity' | 'manual' }
  | { type: 'resolve:start'; dsn: string }
  | { type: 'resolve:success'; dsn: string; endpointCount: number; durationMs: number }
  | { type: 'resolve:error'; dsn: string; error: Error }
  | { type: 'health:check'; endpoint: ResolvedEndpoint; healthy: boolean }
  | { type: 'health:changed'; endpoint: ResolvedEndpoint; previousHealthy: boolean }
  | { type: 'error'; error: Error };

/**
 * Event listener type
 */
export type DnsCacheEventListener = (event: DnsCacheEvent) => void;

/**
 * Custom resolver function type
 */
export type ResolverFunction = (dsn: string) => Promise<ResolvedEndpoint[]>;

/**
 * State store interface for DNS cache
 */
export interface DnsCacheStore {
  /** Get a cached entry */
  get(key: string): Promise<CachedEntry | undefined>;
  /** Set a cached entry */
  set(key: string, entry: CachedEntry): Promise<void>;
  /** Delete a cached entry */
  delete(key: string): Promise<boolean>;
  /** Check if an entry exists */
  has(key: string): Promise<boolean>;
  /** Get all cached keys */
  keys(): Promise<string[]>;
  /** Get the number of cached entries */
  size(): Promise<number>;
  /** Clear all cached entries */
  clear(): Promise<void>;
  /** Close the store connection */
  close(): Promise<void>;
}

export default {
  // Types are exported, no default needed
};
