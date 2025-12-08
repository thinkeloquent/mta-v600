/**
 * Types for cache-request package
 */

/**
 * Configuration for idempotency key generation and management
 */
export interface IdempotencyConfig {
  /** Header name for the idempotency key. Default: 'Idempotency-Key' */
  headerName?: string;
  /** TTL for cached responses in milliseconds. Default: 86400000 (24 hours) */
  ttlMs?: number;
  /** Whether to auto-generate keys for applicable methods. Default: true */
  autoGenerate?: boolean;
  /** HTTP methods that require idempotency keys. Default: ['POST', 'PATCH'] */
  methods?: string[];
  /** Custom key generator function */
  keyGenerator?: () => string;
}

/**
 * Configuration for request coalescing (singleflight)
 */
export interface SingleflightConfig {
  /** TTL for in-flight request tracking in milliseconds. Default: 30000 (30 seconds) */
  ttlMs?: number;
  /** HTTP methods to apply coalescing to. Default: ['GET', 'HEAD'] */
  methods?: string[];
  /** Custom request fingerprint generator */
  fingerprintGenerator?: (request: RequestFingerprint) => string;
  /** Whether to include headers in fingerprint. Default: false */
  includeHeaders?: boolean;
  /** Headers to include in fingerprint if includeHeaders is true */
  headerKeys?: string[];
}

/**
 * Request fingerprint components for generating cache keys
 */
export interface RequestFingerprint {
  method: string;
  url: string;
  headers?: Record<string, string>;
  body?: string | Buffer | null;
}

/**
 * Stored response for idempotency
 */
export interface StoredResponse<T = unknown> {
  /** The cached response value */
  value: T;
  /** When the response was cached */
  cachedAt: number;
  /** When the cache entry expires */
  expiresAt: number;
  /** Original request fingerprint for validation */
  fingerprint?: string;
}

/**
 * In-flight request tracker for singleflight
 */
export interface InFlightRequest<T = unknown> {
  /** Promise that resolves when the request completes */
  promise: Promise<T>;
  /** Number of subscribers waiting for this request */
  subscribers: number;
  /** When the request was initiated */
  startedAt: number;
}

/**
 * Cache request store interface
 */
export interface CacheRequestStore {
  /**
   * Get a stored response by idempotency key
   */
  get<T>(key: string): Promise<StoredResponse<T> | null>;

  /**
   * Store a response with an idempotency key
   */
  set<T>(key: string, response: StoredResponse<T>): Promise<void>;

  /**
   * Check if a key exists
   */
  has(key: string): Promise<boolean>;

  /**
   * Delete a stored response
   */
  delete(key: string): Promise<boolean>;

  /**
   * Clear all stored responses
   */
  clear(): Promise<void>;

  /**
   * Get current size of store
   */
  size(): Promise<number>;

  /**
   * Close the store and release resources
   */
  close(): Promise<void>;
}

/**
 * Singleflight store interface for tracking in-flight requests
 */
export interface SingleflightStore {
  /**
   * Get an in-flight request by fingerprint
   */
  get<T>(fingerprint: string): InFlightRequest<T> | null;

  /**
   * Register an in-flight request
   */
  set<T>(fingerprint: string, request: InFlightRequest<T>): void;

  /**
   * Remove an in-flight request
   */
  delete(fingerprint: string): boolean;

  /**
   * Check if a request is in-flight
   */
  has(fingerprint: string): boolean;

  /**
   * Get current number of in-flight requests
   */
  size(): number;

  /**
   * Clear all in-flight requests
   */
  clear(): void;
}

/**
 * Combined cache request configuration
 */
export interface CacheRequestConfig {
  /** Idempotency configuration */
  idempotency?: IdempotencyConfig;
  /** Singleflight configuration */
  singleflight?: SingleflightConfig;
  /** Custom store for idempotency responses */
  store?: CacheRequestStore;
}

/**
 * Result of an idempotency check
 */
export interface IdempotencyCheckResult<T = unknown> {
  /** Whether a cached response was found */
  cached: boolean;
  /** The idempotency key used */
  key: string;
  /** The cached response if found */
  response?: StoredResponse<T>;
}

/**
 * Result of a singleflight operation
 */
export interface SingleflightResult<T = unknown> {
  /** The result value */
  value: T;
  /** Whether this was from a shared/coalesced request */
  shared: boolean;
  /** Number of requests that shared this result */
  subscribers: number;
}

/**
 * Event types for cache request operations
 */
export type CacheRequestEventType =
  | 'idempotency:hit'
  | 'idempotency:miss'
  | 'idempotency:store'
  | 'idempotency:expire'
  | 'singleflight:join'
  | 'singleflight:lead'
  | 'singleflight:complete'
  | 'singleflight:error';

/**
 * Cache request event
 */
export interface CacheRequestEvent {
  type: CacheRequestEventType;
  key: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

/**
 * Event listener type
 */
export type CacheRequestEventListener = (event: CacheRequestEvent) => void;
