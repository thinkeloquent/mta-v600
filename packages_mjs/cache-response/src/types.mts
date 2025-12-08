/**
 * Types for RFC 7234 HTTP response caching
 */

/**
 * Parsed Cache-Control directives
 */
export interface CacheControlDirectives {
  /** Response must not be cached */
  noStore?: boolean;
  /** Response must be revalidated before use */
  noCache?: boolean;
  /** Maximum age in seconds */
  maxAge?: number;
  /** Shared cache maximum age in seconds */
  sMaxAge?: number;
  /** Response is private (user-specific) */
  private?: boolean;
  /** Response is public (can be cached by shared caches) */
  public?: boolean;
  /** Response must be revalidated if stale */
  mustRevalidate?: boolean;
  /** Proxy must revalidate if stale */
  proxyRevalidate?: boolean;
  /** Response must not be transformed */
  noTransform?: boolean;
  /** Response can be served stale while revalidating */
  staleWhileRevalidate?: number;
  /** Response can be served stale if error occurs */
  staleIfError?: number;
  /** Immutable - response will not change */
  immutable?: boolean;
}

/**
 * Cache entry metadata
 */
export interface CacheEntryMetadata {
  /** Request URL */
  url: string;
  /** Request method */
  method: string;
  /** Response status code */
  statusCode: number;
  /** Response headers */
  headers: Record<string, string>;
  /** When the response was cached (Unix timestamp ms) */
  cachedAt: number;
  /** When the cache entry expires (Unix timestamp ms) */
  expiresAt: number;
  /** ETag for conditional requests */
  etag?: string;
  /** Last-Modified date for conditional requests */
  lastModified?: string;
  /** Original Cache-Control header */
  cacheControl?: string;
  /** Parsed Cache-Control directives */
  directives?: CacheControlDirectives;
  /** Vary header value */
  vary?: string;
  /** Request headers used for Vary matching */
  varyHeaders?: Record<string, string>;
}

/**
 * Cached response entry
 */
export interface CachedResponse {
  /** Cache entry metadata */
  metadata: CacheEntryMetadata;
  /** Response body */
  body: Buffer | string | null;
}

/**
 * Cache freshness status
 */
export type CacheFreshness = 'fresh' | 'stale' | 'expired';

/**
 * Result of cache lookup
 */
export interface CacheLookupResult {
  /** Whether a cached response was found */
  found: boolean;
  /** The cached response if found */
  response?: CachedResponse;
  /** Freshness status of the cached response */
  freshness?: CacheFreshness;
  /** Whether conditional request should be made */
  shouldRevalidate?: boolean;
  /** ETag for If-None-Match header */
  etag?: string;
  /** Last-Modified for If-Modified-Since header */
  lastModified?: string;
}

/**
 * Revalidation result
 */
export interface RevalidationResult {
  /** Whether the cached response is still valid */
  valid: boolean;
  /** Updated response if not valid */
  response?: CachedResponse;
}

/**
 * Cache store interface
 */
export interface CacheResponseStore {
  /**
   * Get a cached response by key
   */
  get(key: string): Promise<CachedResponse | null>;

  /**
   * Store a response
   */
  set(key: string, response: CachedResponse): Promise<void>;

  /**
   * Check if a key exists
   */
  has(key: string): Promise<boolean>;

  /**
   * Delete a cached response
   */
  delete(key: string): Promise<boolean>;

  /**
   * Clear all cached responses
   */
  clear(): Promise<void>;

  /**
   * Get current size of store
   */
  size(): Promise<number>;

  /**
   * Get all keys (for cleanup)
   */
  keys(): Promise<string[]>;

  /**
   * Close the store and release resources
   */
  close(): Promise<void>;
}

/**
 * Configuration for cache response
 */
export interface CacheResponseConfig {
  /** Methods to cache. Default: ['GET', 'HEAD'] */
  methods?: string[];
  /** Status codes to cache. Default: [200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501] */
  cacheableStatuses?: number[];
  /** Default TTL in milliseconds when no Cache-Control. Default: 0 (no caching) */
  defaultTtlMs?: number;
  /** Maximum TTL in milliseconds. Default: 86400000 (24 hours) */
  maxTtlMs?: number;
  /** Whether to respect no-cache directive. Default: true */
  respectNoCache?: boolean;
  /** Whether to respect no-store directive. Default: true */
  respectNoStore?: boolean;
  /** Whether to respect private directive. Default: true (honor it) */
  respectPrivate?: boolean;
  /** Enable stale-while-revalidate. Default: true */
  staleWhileRevalidate?: boolean;
  /** Enable stale-if-error. Default: true */
  staleIfError?: boolean;
  /** Whether to include query string in cache key. Default: true */
  includeQueryInKey?: boolean;
  /** Custom cache key generator */
  keyGenerator?: (method: string, url: string, headers?: Record<string, string>) => string;
  /** Headers to include in Vary-based cache key */
  varyHeaders?: string[];
}

/**
 * Event types for cache operations
 */
export type CacheResponseEventType =
  | 'cache:hit'
  | 'cache:miss'
  | 'cache:store'
  | 'cache:expire'
  | 'cache:revalidate'
  | 'cache:stale-serve'
  | 'cache:bypass';

/**
 * Cache event
 */
export interface CacheResponseEvent {
  type: CacheResponseEventType;
  key: string;
  url: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

/**
 * Event listener type
 */
export type CacheResponseEventListener = (event: CacheResponseEvent) => void;

/**
 * Background revalidation callback
 */
export type BackgroundRevalidator = (
  url: string,
  headers?: Record<string, string>
) => Promise<void>;
