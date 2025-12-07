/**
 * Type definitions for fetch-retry
 */

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
  /** Jitter factor (0-1). Default: 0.5 (Full Jitter strategy) */
  jitterFactor?: number;
  /** Error codes that should trigger retry */
  retryOnErrors?: string[];
  /** HTTP status codes that should trigger retry */
  retryOnStatus?: number[];
  /** HTTP methods to retry. Default: ['GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE'] (idempotent methods) */
  retryMethods?: string[];
  /** Whether to respect Retry-After header. Default: true */
  respectRetryAfter?: boolean;
}

/**
 * Options for individual retry operations
 */
export interface RetryOptions {
  /** Override max retries for this operation */
  maxRetries?: number;
  /** Signal for cancellation */
  signal?: AbortSignal;
  /** Metadata for logging/debugging */
  metadata?: Record<string, unknown>;
  /** Custom should-retry predicate for this operation */
  shouldRetry?: (error: Error, attempt: number) => boolean | Promise<boolean>;
}

/**
 * Result of a retried operation
 */
export interface RetryResult<T> {
  /** The result of the operation */
  result: T;
  /** Number of retries attempted (0 if succeeded on first try) */
  retries: number;
  /** Total time spent including retries (ms) */
  totalTimeMs: number;
  /** Time spent in backoff delays (ms) */
  delayTimeMs: number;
}

/**
 * Events emitted by the retry executor
 */
export type RetryEvent =
  | { type: 'attempt:start'; attempt: number; metadata?: Record<string, unknown> }
  | { type: 'attempt:success'; attempt: number; durationMs: number; metadata?: Record<string, unknown> }
  | { type: 'attempt:fail'; attempt: number; error: Error; willRetry: boolean; metadata?: Record<string, unknown> }
  | { type: 'retry:wait'; attempt: number; delayMs: number; metadata?: Record<string, unknown> }
  | { type: 'retry:abort'; attempt: number; reason: string; metadata?: Record<string, unknown> };

/**
 * Event listener type
 */
export type RetryEventListener = (event: RetryEvent) => void;

/**
 * Executor configuration
 */
export interface RetryExecutorConfig extends RetryConfig {
  /** Unique identifier for this executor instance */
  id?: string;
}

/**
 * Backoff strategy type
 */
export type BackoffStrategy = 'exponential' | 'linear' | 'constant';

/**
 * Extended retry config with strategy options
 */
export interface ExtendedRetryConfig extends RetryConfig {
  /** Backoff strategy. Default: 'exponential' */
  backoffStrategy?: BackoffStrategy;
  /** Linear increment for linear backoff (ms). Default: 1000 */
  linearIncrementMs?: number;
}

/**
 * HTTP response-like interface for status checking
 */
export interface ResponseLike {
  status?: number;
  statusCode?: number;
  ok?: boolean;
}

/**
 * Error with additional context
 */
export interface RetryableError extends Error {
  code?: string;
  statusCode?: number;
  status?: number;
  cause?: Error;
  isRetryable?: boolean;
}

export default {
  // Types are exported, no default needed
};
