/**
 * Rate limiter interceptor for undici's compose pattern
 */

import type { Dispatcher } from 'undici';
import {
  RateLimiter,
  type RateLimiterConfig,
  type RateLimitStore,
  type StaticRateLimitConfig,
} from '@internal/fetch-rate-limiter';

/**
 * Options for the rate limit interceptor
 */
export interface RateLimitInterceptorOptions {
  /** Maximum requests per interval */
  maxPerSecond?: number;
  /** Custom rate limiter config (alternative to maxPerSecond) */
  config?: RateLimiterConfig;
  /** Custom store for distributed rate limiting */
  store?: RateLimitStore;
  /** Whether to respect Retry-After header. Default: true */
  respectRetryAfter?: boolean;
  /** Methods to apply rate limiting to. Default: all */
  methods?: string[];
}

/**
 * Internal state for tracking rate limit from headers
 */
interface RateLimitState {
  remaining: number;
  reset: number;
}

/**
 * Create a rate limit interceptor for undici's compose pattern
 *
 * This interceptor integrates with undici's dispatcher composition,
 * allowing rate limiting to be applied as part of the request pipeline.
 *
 * @param options - Interceptor options
 * @returns Dispatcher compose interceptor
 *
 * @example
 * const client = new Agent().compose(
 *   rateLimitInterceptor({ maxPerSecond: 10 }),
 *   interceptors.retry({ maxRetries: 3 })
 * );
 *
 * @example
 * // With custom config
 * const client = new Agent().compose(
 *   rateLimitInterceptor({
 *     config: {
 *       id: 'github-api',
 *       static: { maxRequests: 5000, intervalMs: 3600000 },
 *       retry: { maxRetries: 3 }
 *     }
 *   })
 * );
 */
export function rateLimitInterceptor(
  options: RateLimitInterceptorOptions = {}
): Dispatcher.DispatcherComposeInterceptor {
  const {
    maxPerSecond,
    config: customConfig,
    store,
    respectRetryAfter = true,
    methods,
  } = options;

  // Build rate limiter config
  let config: RateLimiterConfig;
  if (customConfig) {
    config = customConfig;
  } else if (maxPerSecond) {
    config = {
      id: `interceptor-${Date.now()}`,
      static: {
        maxRequests: maxPerSecond,
        intervalMs: 1000,
      },
    };
  } else {
    config = {
      id: `interceptor-${Date.now()}`,
      static: {
        maxRequests: 10,
        intervalMs: 1000,
      },
    };
  }

  // Create rate limiter instance
  const limiter = new RateLimiter(config, store);

  // Track rate limit state from response headers
  const headerState: RateLimitState = {
    remaining: Infinity,
    reset: 0,
  };

  return (dispatch: Dispatcher.DispatchHandlers['dispatch']) => {
    return (
      opts: Dispatcher.DispatchOptions,
      handler: Dispatcher.DispatchHandlers
    ): boolean => {
      // Check if this method should be rate limited
      if (methods && !methods.includes(opts.method)) {
        return dispatch(opts, handler);
      }

      // Wrap the handler to intercept responses
      const wrappedHandler: Dispatcher.DispatchHandlers = {
        ...handler,
        onHeaders: (
          statusCode: number,
          headers: Buffer[] | string[] | null,
          resume: () => void,
          statusText: string
        ) => {
          // Parse rate limit headers if present
          if (headers && respectRetryAfter) {
            const headerMap = parseHeaders(headers);

            // Handle Retry-After header
            const retryAfter = headerMap['retry-after'];
            if (statusCode === 429 && retryAfter) {
              const waitSeconds = parseRetryAfter(retryAfter);
              if (waitSeconds > 0) {
                headerState.remaining = 0;
                headerState.reset = Date.now() + waitSeconds * 1000;
              }
            }

            // Handle X-RateLimit headers (common convention)
            const remaining = headerMap['x-ratelimit-remaining'];
            const reset = headerMap['x-ratelimit-reset'];
            if (remaining !== undefined) {
              headerState.remaining = parseInt(remaining, 10);
            }
            if (reset !== undefined) {
              headerState.reset = parseInt(reset, 10) * 1000; // Convert to ms
            }
          }

          return handler.onHeaders?.(statusCode, headers, resume, statusText);
        },
      };

      // Schedule the request through the rate limiter
      const executeRequest = async (): Promise<void> => {
        return new Promise((resolve, reject) => {
          try {
            const result = dispatch(opts, {
              ...wrappedHandler,
              onComplete: (trailers: string[] | null) => {
                handler.onComplete?.(trailers);
                resolve();
              },
              onError: (err: Error) => {
                handler.onError?.(err);
                reject(err);
              },
            });

            if (!result) {
              // If dispatch returns false, the request was not sent
              reject(new Error('Request not dispatched'));
            }
          } catch (err) {
            reject(err);
          }
        });
      };

      // Use the rate limiter to schedule the request
      limiter
        .schedule(executeRequest, {
          metadata: {
            method: opts.method,
            path: opts.path,
            origin: opts.origin?.toString(),
          },
        })
        .catch((err) => {
          handler.onError?.(err);
        });

      return true;
    };
  };
}

/**
 * Parse headers array into a map
 */
function parseHeaders(headers: Buffer[] | string[] | null): Record<string, string> {
  const map: Record<string, string> = {};
  if (!headers) return map;

  for (let i = 0; i < headers.length; i += 2) {
    const key = headers[i]?.toString().toLowerCase();
    const value = headers[i + 1]?.toString();
    if (key && value) {
      map[key] = value;
    }
  }

  return map;
}

/**
 * Parse Retry-After header value
 * Can be either a number of seconds or an HTTP-date
 */
function parseRetryAfter(value: string): number {
  // Try parsing as seconds
  const seconds = parseInt(value, 10);
  if (!isNaN(seconds)) {
    return seconds;
  }

  // Try parsing as HTTP-date
  const date = Date.parse(value);
  if (!isNaN(date)) {
    return Math.max(0, Math.ceil((date - Date.now()) / 1000));
  }

  return 0;
}

export default rateLimitInterceptor;
