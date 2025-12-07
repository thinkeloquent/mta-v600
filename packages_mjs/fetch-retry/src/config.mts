/**
 * Configuration utilities for fetch-retry
 */

import type { RetryConfig, ExtendedRetryConfig, RetryableError, ResponseLike } from './types.mjs';

/**
 * Default retry configuration
 */
export const DEFAULT_RETRY_CONFIG: Required<RetryConfig> = {
  maxRetries: 3,
  baseDelayMs: 1000,
  maxDelayMs: 30000,
  jitterFactor: 0.5,
  retryOnErrors: ['ECONNRESET', 'ETIMEDOUT', 'ENOTFOUND', 'ECONNREFUSED', 'EPIPE', 'UND_ERR_SOCKET'],
  retryOnStatus: [429, 500, 502, 503, 504],
  retryMethods: ['GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE'],
  respectRetryAfter: true,
};

/**
 * Idempotent HTTP methods that are safe to retry
 */
export const IDEMPOTENT_METHODS = ['GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE', 'TRACE'];

/**
 * Non-idempotent methods that require special consideration for retry
 */
export const NON_IDEMPOTENT_METHODS = ['POST', 'PATCH'];

/**
 * Calculate exponential backoff delay with jitter
 *
 * Uses the "Full Jitter" strategy to prevent thundering herd:
 * delay = random(0, min(cap, base * 2^attempt))
 *
 * @param attempt - The current attempt number (0-indexed)
 * @param config - Retry configuration
 * @returns Delay in milliseconds
 */
export function calculateBackoffDelay(attempt: number, config: RetryConfig): number {
  const { baseDelayMs = 1000, maxDelayMs = 30000, jitterFactor = 0.5 } = config;

  // Calculate exponential delay
  const exponentialDelay = Math.min(maxDelayMs, baseDelayMs * Math.pow(2, attempt));

  // Apply full jitter
  const jitter = Math.random() * jitterFactor * exponentialDelay;
  const delay = exponentialDelay * (1 - jitterFactor / 2) + jitter;

  return Math.floor(Math.min(delay, maxDelayMs));
}

/**
 * Calculate delay based on strategy
 *
 * @param attempt - The current attempt number (0-indexed)
 * @param config - Extended retry configuration
 * @returns Delay in milliseconds
 */
export function calculateDelay(attempt: number, config: ExtendedRetryConfig): number {
  const { backoffStrategy = 'exponential', linearIncrementMs = 1000 } = config;
  const { baseDelayMs = 1000, maxDelayMs = 30000, jitterFactor = 0.5 } = config;

  let baseDelay: number;

  switch (backoffStrategy) {
    case 'constant':
      baseDelay = baseDelayMs;
      break;
    case 'linear':
      baseDelay = Math.min(maxDelayMs, baseDelayMs + linearIncrementMs * attempt);
      break;
    case 'exponential':
    default:
      baseDelay = Math.min(maxDelayMs, baseDelayMs * Math.pow(2, attempt));
      break;
  }

  // Apply jitter
  const jitter = Math.random() * jitterFactor * baseDelay;
  const delay = baseDelay * (1 - jitterFactor / 2) + jitter;

  return Math.floor(Math.min(delay, maxDelayMs));
}

/**
 * Check if an error should trigger a retry
 *
 * @param error - The error to check
 * @param config - Retry configuration
 * @returns Whether the error is retryable
 */
export function isRetryableError(error: Error | RetryableError, config: RetryConfig): boolean {
  const { retryOnErrors = DEFAULT_RETRY_CONFIG.retryOnErrors } = config;

  // Check explicit retryable flag
  if ('isRetryable' in error && error.isRetryable === false) {
    return false;
  }
  if ('isRetryable' in error && error.isRetryable === true) {
    return true;
  }

  // Check error code
  const errorCode = (error as RetryableError).code;
  if (errorCode && retryOnErrors.includes(errorCode)) {
    return true;
  }

  // Check for network-related error messages
  const message = error.message.toLowerCase();
  const retryablePatterns = [
    'network',
    'timeout',
    'timed out',
    'econnreset',
    'econnrefused',
    'enotfound',
    'socket',
    'epipe',
    'connection',
    'abort',
    'fetch failed',
  ];

  if (retryablePatterns.some((pattern) => message.includes(pattern))) {
    return true;
  }

  // Check cause chain
  if (error.cause instanceof Error) {
    return isRetryableError(error.cause, config);
  }

  return false;
}

/**
 * Check if an HTTP status code should trigger a retry
 *
 * @param status - The HTTP status code
 * @param config - Retry configuration
 * @returns Whether the status is retryable
 */
export function isRetryableStatus(status: number, config: RetryConfig): boolean {
  const { retryOnStatus = DEFAULT_RETRY_CONFIG.retryOnStatus } = config;
  return retryOnStatus.includes(status);
}

/**
 * Check if an HTTP method is safe to retry
 *
 * @param method - The HTTP method
 * @param config - Retry configuration
 * @returns Whether the method is retryable
 */
export function isRetryableMethod(method: string, config: RetryConfig): boolean {
  const { retryMethods = DEFAULT_RETRY_CONFIG.retryMethods } = config;
  return retryMethods.includes(method.toUpperCase());
}

/**
 * Check if a response should trigger a retry
 *
 * @param response - Response-like object with status
 * @param config - Retry configuration
 * @returns Whether the response status is retryable
 */
export function shouldRetryResponse(response: ResponseLike, config: RetryConfig): boolean {
  const status = response.status ?? response.statusCode;
  if (status === undefined) {
    return false;
  }
  return isRetryableStatus(status, config);
}

/**
 * Parse Retry-After header value
 *
 * The Retry-After header can contain either:
 * - A number of seconds to wait
 * - An HTTP-date indicating when to retry
 *
 * @param value - Retry-After header value
 * @returns Wait time in milliseconds, or 0 if parsing fails
 */
export function parseRetryAfter(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }

  // Try parsing as seconds
  const seconds = parseInt(value, 10);
  if (!isNaN(seconds)) {
    return seconds * 1000;
  }

  // Try parsing as HTTP-date
  const date = Date.parse(value);
  if (!isNaN(date)) {
    return Math.max(0, date - Date.now());
  }

  return 0;
}

/**
 * Merge configurations with defaults
 *
 * @param config - User-provided configuration
 * @returns Complete configuration with defaults
 */
export function mergeConfig(config: RetryConfig = {}): Required<RetryConfig> {
  return {
    ...DEFAULT_RETRY_CONFIG,
    ...config,
  };
}

/**
 * Sleep for a specified duration
 *
 * @param ms - Duration in milliseconds
 * @param signal - Optional abort signal
 * @returns Promise that resolves after the delay
 */
export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new Error('Aborted'));
      return;
    }

    const timeout = setTimeout(resolve, ms);

    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timeout);
        reject(new Error('Aborted'));
      },
      { once: true }
    );
  });
}

/**
 * Create an error with retry context
 *
 * @param message - Error message
 * @param options - Error options
 * @returns Error with retry context
 */
export function createRetryError(
  message: string,
  options?: { cause?: Error; code?: string; isRetryable?: boolean }
): RetryableError {
  const error = new Error(message) as RetryableError;
  if (options?.cause) {
    error.cause = options.cause;
  }
  if (options?.code) {
    error.code = options.code;
  }
  if (options?.isRetryable !== undefined) {
    error.isRetryable = options.isRetryable;
  }
  return error;
}

export default {
  DEFAULT_RETRY_CONFIG,
  IDEMPOTENT_METHODS,
  NON_IDEMPOTENT_METHODS,
  calculateBackoffDelay,
  calculateDelay,
  isRetryableError,
  isRetryableStatus,
  isRetryableMethod,
  shouldRetryResponse,
  parseRetryAfter,
  mergeConfig,
  sleep,
  createRetryError,
};
