/**
 * Configuration utilities for fetch-rate-limiter
 */

import type { RateLimiterConfig, RetryConfig } from './types.mjs';

/**
 * Default retry configuration
 */
export const DEFAULT_RETRY_CONFIG: Required<RetryConfig> = {
  maxRetries: 3,
  baseDelayMs: 1000,
  maxDelayMs: 30000,
  jitterFactor: 0.5,
  retryOnErrors: ['ECONNRESET', 'ETIMEDOUT', 'ENOTFOUND', 'ECONNREFUSED'],
  retryOnStatus: [429, 500, 502, 503, 504],
};

/**
 * Default rate limiter configuration
 */
export const DEFAULT_CONFIG: Partial<RateLimiterConfig> = {
  maxQueueSize: Infinity,
  concurrency: 1,
  retry: DEFAULT_RETRY_CONFIG,
};

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
 * Check if an error should trigger a retry
 *
 * @param error - The error to check
 * @param config - Retry configuration
 * @returns Whether the error is retryable
 */
export function isRetryableError(error: Error, config: RetryConfig): boolean {
  const { retryOnErrors = DEFAULT_RETRY_CONFIG.retryOnErrors } = config;

  // Check error code
  const errorCode = (error as Error & { code?: string }).code;
  if (errorCode && retryOnErrors.includes(errorCode)) {
    return true;
  }

  // Check for network-related error messages
  const message = error.message.toLowerCase();
  if (
    message.includes('network') ||
    message.includes('timeout') ||
    message.includes('econnreset') ||
    message.includes('socket')
  ) {
    return true;
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
 * Merge configurations with defaults
 *
 * @param config - User-provided configuration
 * @returns Complete configuration with defaults
 */
export function mergeConfig(config: RateLimiterConfig): RateLimiterConfig {
  return {
    ...DEFAULT_CONFIG,
    ...config,
    retry: {
      ...DEFAULT_RETRY_CONFIG,
      ...config.retry,
    },
  };
}

/**
 * Generate a unique request ID
 */
export function generateRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
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

export default {
  DEFAULT_RETRY_CONFIG,
  DEFAULT_CONFIG,
  calculateBackoffDelay,
  isRetryableError,
  isRetryableStatus,
  mergeConfig,
  generateRequestId,
  sleep,
};
