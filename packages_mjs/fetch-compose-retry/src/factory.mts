/**
 * Factory functions for creating retry-enabled dispatchers
 */

import { Agent, type Dispatcher, interceptors } from 'undici';
import { retryInterceptor, type RetryInterceptorOptions } from './interceptor.mjs';
import type { RetryConfig } from '@internal/fetch-retry';

/**
 * Options for creating a retry-enabled dispatcher
 */
export interface RetryDispatcherOptions extends RetryInterceptorOptions {
  /** Base dispatcher to compose on. Default: new Agent() */
  baseDispatcher?: Dispatcher;
  /** Include DNS interceptor. Default: false */
  includeDns?: boolean;
  /** DNS affinity preference. Default: 4 (IPv4) */
  dnsAffinity?: 4 | 6;
  /** Include redirect interceptor. Default: false */
  includeRedirect?: boolean;
  /** Maximum redirections. Default: 5 */
  maxRedirections?: number;
}

/**
 * Create a retry-enabled dispatcher with optional DNS and redirect interceptors
 *
 * @param options - Dispatcher options
 * @returns Composed dispatcher with retry logic
 *
 * @example
 * // Simple retry dispatcher
 * const dispatcher = createRetryDispatcher({ maxRetries: 3 });
 *
 * @example
 * // With DNS and redirect handling
 * const dispatcher = createRetryDispatcher({
 *   maxRetries: 3,
 *   includeDns: true,
 *   includeRedirect: true,
 *   maxRedirections: 3
 * });
 *
 * @example
 * // Use with fetch
 * const response = await fetch('https://api.example.com', { dispatcher });
 */
export function createRetryDispatcher(
  options: RetryDispatcherOptions = {}
): Dispatcher {
  const {
    baseDispatcher,
    includeDns = false,
    dnsAffinity = 4,
    includeRedirect = false,
    maxRedirections = 5,
    ...retryOptions
  } = options;

  const base = baseDispatcher ?? new Agent();
  const interceptorChain: Dispatcher.DispatcherComposeInterceptor[] = [];

  // Add retry interceptor first (outermost - handles all internal errors)
  interceptorChain.push(retryInterceptor(retryOptions));

  // Add DNS interceptor if requested
  if (includeDns) {
    interceptorChain.push(interceptors.dns({ affinity: dnsAffinity }));
  }

  // Add redirect interceptor if requested
  if (includeRedirect) {
    interceptorChain.push(interceptors.redirect({ maxRedirections }));
  }

  return base.compose(...interceptorChain);
}

/**
 * Create a resilient dispatcher with retry, DNS, and redirect handling
 *
 * This is a convenience function that creates a fully-featured dispatcher
 * with sensible defaults for most use cases.
 *
 * @param options - Retry configuration
 * @returns Composed dispatcher with full resilience features
 *
 * @example
 * const dispatcher = createResilientDispatcher({ maxRetries: 3 });
 * const response = await fetch('https://api.example.com', { dispatcher });
 */
export function createResilientDispatcher(
  options: RetryInterceptorOptions = {}
): Dispatcher {
  return createRetryDispatcher({
    ...options,
    includeDns: true,
    includeRedirect: true,
  });
}

/**
 * Create a retry interceptor for a specific API endpoint
 *
 * @param apiId - Unique identifier for logging/debugging
 * @param options - Retry configuration
 * @returns Retry interceptor
 *
 * @example
 * const githubRetry = createApiRetryInterceptor('github', {
 *   maxRetries: 5,
 *   respectRetryAfter: true
 * });
 * const openaiRetry = createApiRetryInterceptor('openai', {
 *   maxRetries: 3,
 *   retryOnStatus: [429, 500, 529]
 * });
 *
 * const githubClient = new Agent().compose(githubRetry);
 * const openaiClient = new Agent().compose(openaiRetry);
 */
export function createApiRetryInterceptor(
  apiId: string,
  options: RetryInterceptorOptions = {}
): Dispatcher.DispatcherComposeInterceptor {
  return retryInterceptor({
    ...options,
    onRetry: (error, attempt, delayMs) => {
      options.onRetry?.(error, attempt, delayMs);
      // Could add logging here: console.log(`[${apiId}] Retry ${attempt}: ${error.message}`);
    },
    onSuccess: (attempt, durationMs) => {
      options.onSuccess?.(attempt, durationMs);
      // Could add logging here: console.log(`[${apiId}] Success after ${attempt} attempts in ${durationMs}ms`);
    },
  });
}

/**
 * Default retry configuration for common scenarios
 */
export const RETRY_PRESETS = {
  /** Conservative retry for general APIs */
  default: {
    maxRetries: 3,
    baseDelayMs: 1000,
    maxDelayMs: 30000,
    jitterFactor: 0.5,
    retryOnStatus: [429, 500, 502, 503, 504],
    respectRetryAfter: true,
  } as RetryInterceptorOptions,

  /** Aggressive retry for critical operations */
  aggressive: {
    maxRetries: 5,
    baseDelayMs: 500,
    maxDelayMs: 60000,
    jitterFactor: 0.3,
    retryOnStatus: [429, 500, 502, 503, 504, 520, 521, 522, 523, 524],
    respectRetryAfter: true,
  } as RetryInterceptorOptions,

  /** Quick retry for fast-failing operations */
  quick: {
    maxRetries: 2,
    baseDelayMs: 200,
    maxDelayMs: 2000,
    jitterFactor: 0.5,
    retryOnStatus: [429, 502, 503, 504],
    respectRetryAfter: true,
  } as RetryInterceptorOptions,

  /** Gentle retry for rate-limited APIs */
  gentle: {
    maxRetries: 5,
    baseDelayMs: 2000,
    maxDelayMs: 120000,
    jitterFactor: 0.7,
    retryOnStatus: [429],
    respectRetryAfter: true,
  } as RetryInterceptorOptions,
} as const;

export default {
  createRetryDispatcher,
  createResilientDispatcher,
  createApiRetryInterceptor,
  RETRY_PRESETS,
};
