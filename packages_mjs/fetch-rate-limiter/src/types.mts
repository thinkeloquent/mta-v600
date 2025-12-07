/**
 * Type definitions for fetch-rate-limiter
 */

/**
 * Rate limit status from external API or internal state
 */
export interface RateLimitStatus {
  /** Number of requests remaining in current window */
  remaining: number;
  /** Unix timestamp when the limit resets */
  reset: number;
  /** Total limit for the window */
  limit?: number;
}

/**
 * Options for scheduling a request
 */
export interface ScheduleOptions {
  /** Priority level (higher = more priority). Default: 0 */
  priority?: number;
  /** Metadata for logging/debugging */
  metadata?: Record<string, unknown>;
  /** Deadline timestamp - reject if not processed by this time */
  deadline?: number;
  /** Signal for cancellation */
  signal?: AbortSignal;
}

/**
 * Result of a scheduled operation
 */
export interface ScheduleResult<T> {
  /** The result of the operation */
  result: T;
  /** Time spent waiting in queue (ms) */
  queueTime: number;
  /** Time spent executing (ms) */
  executionTime: number;
  /** Number of retries attempted */
  retries: number;
}

/**
 * Configuration for static rate limiting
 */
export interface StaticRateLimitConfig {
  /** Maximum requests per interval */
  maxRequests: number;
  /** Interval in milliseconds */
  intervalMs: number;
}

/**
 * Configuration for dynamic rate limiting
 */
export interface DynamicRateLimitConfig {
  /** Async function to get current rate limit status */
  getRateLimitStatus: () => Promise<RateLimitStatus>;
  /** Fallback to static limits when dynamic fails */
  fallback?: StaticRateLimitConfig;
}

/**
 * Retry configuration
 */
export interface RetryConfig {
  /** Maximum number of retries. Default: 3 */
  maxRetries?: number;
  /** Base delay for exponential backoff (ms). Default: 1000 */
  baseDelayMs?: number;
  /** Maximum delay between retries (ms). Default: 30000 */
  maxDelayMs?: number;
  /** Jitter factor (0-1). Default: 0.5 */
  jitterFactor?: number;
  /** Error codes that should trigger retry */
  retryOnErrors?: string[];
  /** HTTP status codes that should trigger retry */
  retryOnStatus?: number[];
}

/**
 * Main rate limiter configuration
 */
export interface RateLimiterConfig {
  /** Unique identifier for this limiter instance */
  id: string;
  /** Static rate limit config (mutually exclusive with dynamic) */
  static?: StaticRateLimitConfig;
  /** Dynamic rate limit config (mutually exclusive with static) */
  dynamic?: DynamicRateLimitConfig;
  /** Maximum queue size. Default: Infinity */
  maxQueueSize?: number;
  /** Retry configuration */
  retry?: RetryConfig;
  /** Concurrency limit for parallel execution. Default: 1 */
  concurrency?: number;
}

/**
 * Statistics from the rate limiter
 */
export interface RateLimiterStats {
  /** Current queue size */
  queueSize: number;
  /** Number of active/in-flight requests */
  activeRequests: number;
  /** Total requests processed */
  totalProcessed: number;
  /** Total requests rejected */
  totalRejected: number;
  /** Average queue time (ms) */
  avgQueueTimeMs: number;
  /** Average execution time (ms) */
  avgExecutionTimeMs: number;
}

/**
 * Events emitted by the rate limiter
 */
export type RateLimiterEvent =
  | { type: 'rate:limited'; waitMs: number }
  | { type: 'request:queued'; priority: number; queueSize: number }
  | { type: 'request:started'; metadata?: Record<string, unknown> }
  | { type: 'request:completed'; durationMs: number; metadata?: Record<string, unknown> }
  | { type: 'request:failed'; error: Error; retries: number; metadata?: Record<string, unknown> }
  | { type: 'request:requeued'; reason: string; metadata?: Record<string, unknown> }
  | { type: 'request:expired'; deadline: number; metadata?: Record<string, unknown> }
  | { type: 'error'; error: Error };

/**
 * Event listener type
 */
export type RateLimiterEventListener = (event: RateLimiterEvent) => void;

/**
 * Queued request internal structure
 */
export interface QueuedRequest<T> {
  /** Unique request ID */
  id: string;
  /** The function to execute */
  fn: () => Promise<T>;
  /** Priority level */
  priority: number;
  /** Enqueue timestamp */
  enqueuedAt: number;
  /** Optional deadline */
  deadline?: number;
  /** Metadata */
  metadata?: Record<string, unknown>;
  /** Resolve function */
  resolve: (result: ScheduleResult<T>) => void;
  /** Reject function */
  reject: (error: Error) => void;
  /** Abort signal */
  signal?: AbortSignal;
}

/**
 * State store interface for distributed rate limiting
 */
export interface RateLimitStore {
  /** Get the current request count for the window */
  getCount(key: string): Promise<number>;
  /** Increment the count and return new value */
  increment(key: string, ttlMs: number): Promise<number>;
  /** Get the TTL remaining for the key (ms) */
  getTTL(key: string): Promise<number>;
  /** Reset the count */
  reset(key: string): Promise<void>;
  /** Close the store connection */
  close(): Promise<void>;
}

export default {
  // Types are exported, no default needed
};
