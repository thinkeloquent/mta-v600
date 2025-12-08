/**
 * Retry interceptor for undici's compose pattern
 */

import type { Dispatcher } from 'undici';
import {
  RetryExecutor,
  type RetryConfig,
  calculateBackoffDelay,
  isRetryableStatus,
  isRetryableMethod,
  parseRetryAfter,
  mergeConfig,
  sleep,
} from '@internal/fetch-retry';

/**
 * Options for the retry interceptor
 */
export interface RetryInterceptorOptions extends RetryConfig {
  /** Custom retry executor (for shared state across interceptors) */
  executor?: RetryExecutor;
  /** Callback before each retry attempt */
  onRetry?: (error: Error, attempt: number, delayMs: number) => void;
  /** Callback on success */
  onSuccess?: (attempt: number, durationMs: number) => void;
}

/**
 * Create a retry interceptor for undici's compose pattern
 *
 * This interceptor integrates with undici's dispatcher composition,
 * providing automatic retry with exponential backoff and jitter.
 *
 * @param options - Interceptor options
 * @returns Dispatcher compose interceptor
 *
 * @example
 * const client = new Agent().compose(
 *   retryInterceptor({ maxRetries: 3 }),
 *   interceptors.dns({ affinity: 4 })
 * );
 *
 * @example
 * // With custom configuration
 * const client = new Agent().compose(
 *   retryInterceptor({
 *     maxRetries: 5,
 *     baseDelayMs: 500,
 *     maxDelayMs: 10000,
 *     retryOnStatus: [429, 502, 503, 504],
 *     respectRetryAfter: true
 *   })
 * );
 */
export function retryInterceptor(
  options: RetryInterceptorOptions = {}
): Dispatcher.DispatcherComposeInterceptor {
  const config = mergeConfig(options);
  const {
    onRetry,
    onSuccess,
  } = options;
  const maxRetries = config.maxRetries;
  const respectRetryAfter = config.respectRetryAfter;

  return (dispatch: Dispatcher.Dispatch) => {
    return (
      opts: Dispatcher.DispatchOptions,
      handler: Dispatcher.DispatchHandler
    ): boolean => {
      // Check if this method is retryable
      if (!isRetryableMethod(opts.method, config)) {
        return dispatch(opts, handler);
      }

      let attempt = 0;
      let startTime = Date.now();
      let retryAfterMs = 0;

      const attemptRequest = (): boolean => {
        // Create a wrapped handler to intercept responses
        const wrappedHandler: Dispatcher.DispatchHandler = {
          ...handler,
          onHeaders: (
            statusCode: number,
            headers: Buffer[] | string[] | null,
            resume: () => void,
            statusText: string
          ) => {
            // Check if we should retry based on status code
            if (isRetryableStatus(statusCode, config) && attempt < maxRetries) {
              // Check for Retry-After header
              if (respectRetryAfter && headers) {
                const headerMap = parseHeaders(headers);
                const retryAfter = headerMap['retry-after'];
                if (retryAfter) {
                  retryAfterMs = parseRetryAfter(retryAfter);
                }
              }

              // Schedule retry
              const delay = retryAfterMs > 0
                ? retryAfterMs
                : calculateBackoffDelay(attempt, config);

              attempt++;

              if (onRetry) {
                const error = new Error(`HTTP ${statusCode}: ${statusText}`);
                onRetry(error, attempt, delay);
              }

              // Schedule the retry
              setTimeout(() => {
                retryAfterMs = 0;
                attemptRequest();
              }, delay);

              // Don't call the original handler for this response
              return false;
            }

            // Success or non-retryable status - pass through
            if (onSuccess && statusCode >= 200 && statusCode < 400) {
              onSuccess(attempt, Date.now() - startTime);
            }

            return handler.onHeaders?.(statusCode, headers as Buffer[], resume, statusText) ?? true;
          },
          onError: (err: Error) => {
            // Check if error is retryable
            const errorCode = (err as Error & { code?: string }).code;
            const retryableErrors = config.retryOnErrors;

            const isNetworkError = retryableErrors.some((code) =>
              errorCode === code ||
              err.message.toLowerCase().includes(code.toLowerCase())
            );

            if (isNetworkError && attempt < maxRetries) {
              const delay = calculateBackoffDelay(attempt, config);
              attempt++;

              if (onRetry) {
                onRetry(err, attempt, delay);
              }

              // Schedule retry
              setTimeout(() => attemptRequest(), delay);
              return;
            }

            // Not retryable or exhausted retries
            handler.onError?.(err);
          },
        };

        return dispatch(opts, wrappedHandler);
      };

      startTime = Date.now();
      return attemptRequest();
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

export default retryInterceptor;
