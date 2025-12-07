/**
 * Factory functions for creating rate-limited dispatchers
 */

import { Agent, type Dispatcher, interceptors } from 'undici';
import { rateLimitInterceptor, type RateLimitInterceptorOptions } from './interceptor.mjs';
import type { RateLimitStore } from '@internal/fetch-rate-limiter';

/**
 * Options for creating a rate-limited dispatcher
 */
export interface RateLimitedDispatcherOptions extends RateLimitInterceptorOptions {
  /** Base dispatcher to compose on. Default: new Agent() */
  baseDispatcher?: Dispatcher;
  /** Include DNS interceptor. Default: false */
  includeDns?: boolean;
  /** DNS affinity preference. Default: 4 (IPv4) */
  dnsAffinity?: 4 | 6;
  /** Include retry interceptor. Default: false */
  includeRetry?: boolean;
  /** Retry options for built-in retry interceptor */
  retryOptions?: {
    maxRetries?: number;
    minTimeout?: number;
    maxTimeout?: number;
    timeoutFactor?: number;
    retryAfter?: boolean;
  };
}

/**
 * Create a rate-limited dispatcher with optional DNS and retry interceptors
 *
 * @param options - Dispatcher options
 * @returns Composed dispatcher with rate limiting
 *
 * @example
 * // Simple rate limiting
 * const dispatcher = createRateLimitedDispatcher({ maxPerSecond: 10 });
 *
 * @example
 * // With retry and DNS resolution
 * const dispatcher = createRateLimitedDispatcher({
 *   maxPerSecond: 10,
 *   includeRetry: true,
 *   includeDns: true,
 *   retryOptions: { maxRetries: 3 }
 * });
 *
 * @example
 * // Use with fetch
 * const response = await fetch('https://api.example.com', { dispatcher });
 */
export function createRateLimitedDispatcher(
  options: RateLimitedDispatcherOptions = {}
): Dispatcher {
  const {
    baseDispatcher,
    includeDns = false,
    dnsAffinity = 4,
    includeRetry = false,
    retryOptions,
    ...rateLimitOptions
  } = options;

  const base = baseDispatcher ?? new Agent();
  const interceptorChain: Dispatcher.DispatcherComposeInterceptor[] = [];

  // Add rate limit interceptor first (outermost)
  interceptorChain.push(rateLimitInterceptor(rateLimitOptions));

  // Add DNS interceptor if requested
  if (includeDns) {
    interceptorChain.push(interceptors.dns({ affinity: dnsAffinity }));
  }

  // Add retry interceptor if requested
  if (includeRetry) {
    interceptorChain.push(
      interceptors.retry({
        maxRetries: retryOptions?.maxRetries ?? 3,
        minTimeout: retryOptions?.minTimeout ?? 500,
        maxTimeout: retryOptions?.maxTimeout ?? 10000,
        timeoutFactor: retryOptions?.timeoutFactor ?? 2,
        retryAfter: retryOptions?.retryAfter ?? true,
      })
    );
  }

  return base.compose(...interceptorChain);
}

/**
 * Create a rate limiter for a specific API endpoint
 *
 * @param apiId - Unique identifier for the API
 * @param maxPerSecond - Maximum requests per second
 * @param store - Optional distributed store
 * @returns Rate limit interceptor
 *
 * @example
 * const githubLimiter = createApiRateLimiter('github', 5000 / 3600);
 * const openaiLimiter = createApiRateLimiter('openai', 60);
 *
 * const githubClient = new Agent().compose(githubLimiter);
 * const openaiClient = new Agent().compose(openaiLimiter);
 */
export function createApiRateLimiter(
  apiId: string,
  maxPerSecond: number,
  store?: RateLimitStore
): Dispatcher.DispatcherComposeInterceptor {
  return rateLimitInterceptor({
    config: {
      id: apiId,
      static: {
        maxRequests: Math.ceil(maxPerSecond),
        intervalMs: 1000,
      },
    },
    store,
  });
}

export default {
  createRateLimitedDispatcher,
  createApiRateLimiter,
};
