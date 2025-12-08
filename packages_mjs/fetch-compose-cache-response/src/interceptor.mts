/**
 * Cache response interceptor for undici's compose pattern
 * Implements RFC 7234 HTTP caching with Cache-Control, conditional requests,
 * and stale-while-revalidate support.
 */

import type { Dispatcher } from 'undici';
import {
  ResponseCache,
  type CacheResponseConfig,
  type CacheResponseStore,
  type CacheFreshness,
} from '@internal/cache-response';

/**
 * Options for the cache response interceptor
 */
export interface CacheResponseInterceptorOptions {
  /** Cache configuration */
  config?: CacheResponseConfig;
  /** Custom cache store */
  store?: CacheResponseStore;
  /** Enable stale-while-revalidate background refresh. Default: true */
  enableBackgroundRevalidation?: boolean;
  /** Callback when cache hit occurs */
  onCacheHit?: (url: string, freshness: CacheFreshness) => void;
  /** Callback when cache miss occurs */
  onCacheMiss?: (url: string) => void;
  /** Callback when response is cached */
  onCacheStore?: (url: string, statusCode: number, ttlMs: number) => void;
  /** Callback when conditional request results in 304 */
  onRevalidated?: (url: string) => void;
}

/**
 * Create a cache response interceptor for undici's compose pattern
 *
 * This interceptor integrates with undici's dispatcher composition,
 * providing RFC 7234 compliant HTTP response caching.
 *
 * @param options - Interceptor options
 * @returns Dispatcher compose interceptor
 *
 * @example Basic usage
 * ```typescript
 * const client = new Agent().compose(
 *   cacheResponseInterceptor(),
 *   interceptors.retry({ maxRetries: 3 })
 * );
 * ```
 *
 * @example With custom configuration
 * ```typescript
 * const client = new Agent().compose(
 *   cacheResponseInterceptor({
 *     config: {
 *       defaultTtlMs: 300000,  // 5 minute default TTL
 *       maxTtlMs: 3600000,     // 1 hour max TTL
 *       staleWhileRevalidate: true,
 *     },
 *     onCacheHit: (url, freshness) => {
 *       console.log(`Cache ${freshness}: ${url}`);
 *     }
 *   })
 * );
 * ```
 */
export function cacheResponseInterceptor(
  options: CacheResponseInterceptorOptions = {}
): Dispatcher.DispatcherComposeInterceptor {
  const {
    config,
    store,
    enableBackgroundRevalidation = true,
    onCacheHit,
    onCacheMiss,
    onCacheStore,
    onRevalidated,
  } = options;

  // Create the cache instance
  const cache = new ResponseCache(config, store);

  // Set up background revalidation if enabled
  if (enableBackgroundRevalidation) {
    // Background revalidator will be set per-request context
    // since we need access to the dispatch function
  }

  return (dispatch: Dispatcher.Dispatch) => {
    return (
      opts: Dispatcher.DispatchOptions,
      handler: Dispatcher.DispatchHandler
    ): boolean => {
      const method = opts.method;
      const origin = opts.origin?.toString() ?? '';
      const path = opts.path;
      const url = `${origin}${path}`;

      // Check if method is cacheable
      if (!cache.isCacheable(method)) {
        return dispatch(opts, handler);
      }

      // Extract request headers for Vary matching
      const requestHeaders = extractHeaders(opts.headers);

      // Check cache
      handleCachedRequest(
        dispatch,
        opts,
        handler,
        cache,
        url,
        requestHeaders,
        onCacheHit,
        onCacheMiss,
        onCacheStore,
        onRevalidated,
        enableBackgroundRevalidation
      );

      return true;
    };
  };
}

/**
 * Handle a request with cache lookup
 */
async function handleCachedRequest(
  dispatch: Dispatcher.Dispatch,
  opts: Dispatcher.DispatchOptions,
  handler: Dispatcher.DispatchHandler,
  cache: ResponseCache,
  url: string,
  requestHeaders: Record<string, string> | undefined,
  onCacheHit: CacheResponseInterceptorOptions['onCacheHit'],
  onCacheMiss: CacheResponseInterceptorOptions['onCacheMiss'],
  onCacheStore: CacheResponseInterceptorOptions['onCacheStore'],
  onRevalidated: CacheResponseInterceptorOptions['onRevalidated'],
  enableBackgroundRevalidation: boolean
): Promise<void> {
  try {
    const lookup = await cache.lookup(opts.method, url, requestHeaders);

    if (lookup.found && lookup.response && lookup.freshness === 'fresh') {
      // Serve from cache
      onCacheHit?.(url, lookup.freshness);
      serveCachedResponse(handler, lookup.response);
      return;
    }

    if (lookup.found && lookup.response && lookup.freshness === 'stale') {
      // Stale-while-revalidate: serve stale and revalidate in background
      onCacheHit?.(url, lookup.freshness);
      serveCachedResponse(handler, lookup.response);

      if (enableBackgroundRevalidation) {
        // Trigger background revalidation
        revalidateInBackground(
          dispatch,
          opts,
          cache,
          url,
          requestHeaders,
          lookup.etag,
          lookup.lastModified,
          onCacheStore,
          onRevalidated
        );
      }
      return;
    }

    // Cache miss or need revalidation
    onCacheMiss?.(url);

    // Build conditional request headers
    const conditionalHeaders = buildConditionalHeaders(
      opts.headers,
      lookup.etag,
      lookup.lastModified
    );

    const modifiedOpts = {
      ...opts,
      headers: conditionalHeaders,
    };

    // Execute request and potentially cache response
    executeAndCacheRequest(
      dispatch,
      modifiedOpts,
      handler,
      cache,
      url,
      requestHeaders,
      lookup.response ?? undefined,
      onCacheStore,
      onRevalidated
    );
  } catch (error) {
    // On error, pass through to network
    handler.onError?.(error as Error);
  }
}

/**
 * Serve a cached response to the handler
 */
function serveCachedResponse(
  handler: Dispatcher.DispatchHandler,
  response: { metadata: { statusCode: number; headers: Record<string, string> }; body: Buffer | string | null }
): void {
  const headersArray: Buffer[] = [];
  for (const [key, value] of Object.entries(response.metadata.headers)) {
    headersArray.push(Buffer.from(key), Buffer.from(value));
  }

  handler.onHeaders?.(
    response.metadata.statusCode,
    headersArray,
    () => {},
    ''
  );

  if (response.body) {
    const bodyBuffer = Buffer.isBuffer(response.body)
      ? response.body
      : Buffer.from(response.body);
    handler.onData?.(bodyBuffer);
  }

  handler.onComplete?.(null);
}

/**
 * Execute request and cache the response
 */
function executeAndCacheRequest(
  dispatch: Dispatcher.Dispatch,
  opts: Dispatcher.DispatchOptions,
  handler: Dispatcher.DispatchHandler,
  cache: ResponseCache,
  url: string,
  requestHeaders: Record<string, string> | undefined,
  cachedResponse: { metadata: { statusCode: number; headers: Record<string, string> }; body: Buffer | string | null } | undefined,
  onCacheStore: CacheResponseInterceptorOptions['onCacheStore'],
  onRevalidated: CacheResponseInterceptorOptions['onRevalidated']
): void {
  let responseStatusCode: number;
  let responseHeaders: Record<string, string> = {};
  const responseBody: Buffer[] = [];

  const wrappedHandler: Dispatcher.DispatchHandler = {
    ...handler,
    onHeaders: (statusCode: number, headers: Buffer[], resume: () => void, statusText: string): boolean => {
      responseStatusCode = statusCode;
      responseHeaders = parseHeaders(headers);

      // Handle 304 Not Modified
      if (statusCode === 304 && cachedResponse) {
        onRevalidated?.(url);

        // Update cache expiration
        cache.revalidate(opts.method, url, responseHeaders, requestHeaders).catch(() => {});

        // Serve the cached response instead - convert headers to Buffer[]
        const cachedHeadersArray: Buffer[] = [];
        for (const [key, value] of Object.entries(cachedResponse.metadata.headers)) {
          cachedHeadersArray.push(Buffer.from(key), Buffer.from(value));
        }
        handler.onHeaders?.(
          cachedResponse.metadata.statusCode,
          cachedHeadersArray,
          resume,
          ''
        );

        if (cachedResponse.body) {
          const bodyBuffer = Buffer.isBuffer(cachedResponse.body)
            ? cachedResponse.body
            : Buffer.from(cachedResponse.body);
          handler.onData?.(bodyBuffer);
        }

        handler.onComplete?.(null);
        return false; // Stop processing
      }

      return handler.onHeaders?.(statusCode, headers, resume, statusText) ?? true;
    },
    onData: (chunk: Buffer): boolean => {
      responseBody.push(chunk);
      return handler.onData?.(chunk) ?? true;
    },
    onComplete: (trailers: string[] | null): void => {
      // Cache successful responses
      const body = Buffer.concat(responseBody);

      cache
        .store(opts.method, url, responseStatusCode, responseHeaders, body, requestHeaders)
        .then((stored) => {
          if (stored && onCacheStore) {
            const cacheControl = responseHeaders['cache-control'];
            const maxAge = parseCacheControlMaxAge(cacheControl);
            onCacheStore(url, responseStatusCode, maxAge * 1000);
          }
        })
        .catch(() => {});

      handler.onComplete?.(trailers);
    },
  };

  dispatch(opts, wrappedHandler);
}

/**
 * Revalidate in background for stale-while-revalidate
 */
function revalidateInBackground(
  dispatch: Dispatcher.Dispatch,
  opts: Dispatcher.DispatchOptions,
  cache: ResponseCache,
  url: string,
  requestHeaders: Record<string, string> | undefined,
  etag: string | undefined,
  lastModified: string | undefined,
  onCacheStore: CacheResponseInterceptorOptions['onCacheStore'],
  onRevalidated: CacheResponseInterceptorOptions['onRevalidated']
): void {
  const conditionalHeaders = buildConditionalHeaders(opts.headers, etag, lastModified);

  const backgroundOpts = {
    ...opts,
    headers: conditionalHeaders,
  };

  let responseStatusCode: number;
  let responseHeaders: Record<string, string> = {};
  const responseBody: Buffer[] = [];

  const backgroundHandler: Dispatcher.DispatchHandler = {
    onHeaders: (statusCode: number, headers: Buffer[]) => {
      responseStatusCode = statusCode;
      responseHeaders = parseHeaders(headers);

      if (statusCode === 304) {
        onRevalidated?.(url);
        cache.revalidate(opts.method, url, responseHeaders, requestHeaders).catch(() => {});
        return false;
      }
      return true;
    },
    onData: (chunk: Buffer) => {
      responseBody.push(chunk);
      return true;
    },
    onComplete: (_trailers: string[] | null) => {
      if (responseStatusCode !== 304) {
        const body = Buffer.concat(responseBody);
        cache
          .store(opts.method, url, responseStatusCode, responseHeaders, body, requestHeaders)
          .then((stored) => {
            if (stored && onCacheStore) {
              const cacheControl = responseHeaders['cache-control'];
              const maxAge = parseCacheControlMaxAge(cacheControl);
              onCacheStore(url, responseStatusCode, maxAge * 1000);
            }
          })
          .catch(() => {});
      }
    },
    onError: () => {
      // Silently ignore background revalidation errors
    },
  };

  try {
    dispatch(backgroundOpts, backgroundHandler);
  } catch {
    // Ignore errors in background revalidation
  }
}

/**
 * Extract headers from various formats
 */
function extractHeaders(
  headers: Dispatcher.DispatchOptions['headers']
): Record<string, string> | undefined {
  if (!headers) return undefined;

  const result: Record<string, string> = {};

  if (Array.isArray(headers)) {
    for (let i = 0; i < headers.length; i += 2) {
      const key = headers[i]?.toString();
      const value = headers[i + 1]?.toString();
      if (key && value) {
        result[key.toLowerCase()] = value;
      }
    }
  } else if (typeof headers === 'object') {
    for (const [key, value] of Object.entries(headers)) {
      if (typeof value === 'string') {
        result[key.toLowerCase()] = value;
      } else if (Array.isArray(value)) {
        result[key.toLowerCase()] = value.join(', ');
      }
    }
  }

  return Object.keys(result).length > 0 ? result : undefined;
}

/**
 * Parse response headers array to object
 */
function parseHeaders(headers: Buffer[] | string[] | null): Record<string, string> {
  const result: Record<string, string> = {};
  if (!headers) return result;

  for (let i = 0; i < headers.length; i += 2) {
    const key = headers[i]?.toString().toLowerCase();
    const value = headers[i + 1]?.toString();
    if (key && value) {
      result[key] = value;
    }
  }

  return result;
}

/**
 * Build conditional request headers
 */
function buildConditionalHeaders(
  originalHeaders: Dispatcher.DispatchOptions['headers'],
  etag: string | undefined,
  lastModified: string | undefined
): Dispatcher.DispatchOptions['headers'] {
  const headers: Record<string, string> = {};

  // Copy original headers
  if (originalHeaders) {
    if (Array.isArray(originalHeaders)) {
      for (let i = 0; i < originalHeaders.length; i += 2) {
        const key = originalHeaders[i]?.toString();
        const value = originalHeaders[i + 1]?.toString();
        if (key && value) {
          headers[key] = value;
        }
      }
    } else if (typeof originalHeaders === 'object') {
      for (const [key, value] of Object.entries(originalHeaders)) {
        if (typeof value === 'string') {
          headers[key] = value;
        } else if (Array.isArray(value)) {
          headers[key] = value.join(', ');
        }
      }
    }
  }

  // Add conditional headers
  if (etag && !headers['if-none-match']) {
    headers['If-None-Match'] = etag;
  }
  if (lastModified && !headers['if-modified-since']) {
    headers['If-Modified-Since'] = lastModified;
  }

  return headers;
}

/**
 * Parse max-age from Cache-Control header
 */
function parseCacheControlMaxAge(cacheControl: string | undefined): number {
  if (!cacheControl) return 0;

  const match = cacheControl.match(/max-age=(\d+)/i);
  if (match) {
    return parseInt(match[1], 10);
  }

  const sMatch = cacheControl.match(/s-maxage=(\d+)/i);
  if (sMatch) {
    return parseInt(sMatch[1], 10);
  }

  return 0;
}

export default cacheResponseInterceptor;
