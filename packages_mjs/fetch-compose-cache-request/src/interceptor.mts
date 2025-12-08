/**
 * Cache request interceptor for undici's compose pattern
 */

import type { Dispatcher } from 'undici';
import {
  IdempotencyManager,
  Singleflight,
  type IdempotencyConfig,
  type SingleflightConfig,
  type CacheRequestStore,
  type SingleflightStore,
  type RequestFingerprint,
} from '@internal/cache-request';

/**
 * Options for the cache request interceptor
 */
export interface CacheRequestInterceptorOptions {
  /** Enable idempotency key management. Default: true */
  enableIdempotency?: boolean;
  /** Enable request coalescing. Default: true */
  enableSingleflight?: boolean;
  /** Idempotency configuration */
  idempotency?: IdempotencyConfig;
  /** Singleflight configuration */
  singleflight?: SingleflightConfig;
  /** Custom store for idempotency */
  idempotencyStore?: CacheRequestStore;
  /** Custom store for singleflight */
  singleflightStore?: SingleflightStore;
  /** Callback when idempotency key is generated */
  onIdempotencyKeyGenerated?: (key: string, method: string, path: string) => void;
  /** Callback when request is coalesced */
  onRequestCoalesced?: (fingerprint: string, subscribers: number) => void;
}

/**
 * Create a cache request interceptor for undici's compose pattern
 *
 * This interceptor integrates with undici's dispatcher composition,
 * providing idempotency key management and request coalescing.
 *
 * @param options - Interceptor options
 * @returns Dispatcher compose interceptor
 *
 * @example
 * // Basic usage with both features
 * const client = new Agent().compose(
 *   cacheRequestInterceptor(),
 *   interceptors.retry({ maxRetries: 3 })
 * );
 *
 * @example
 * // Idempotency only
 * const client = new Agent().compose(
 *   cacheRequestInterceptor({
 *     enableSingleflight: false,
 *     idempotency: { ttlMs: 3600000 }
 *   })
 * );
 *
 * @example
 * // Singleflight only
 * const client = new Agent().compose(
 *   cacheRequestInterceptor({
 *     enableIdempotency: false,
 *     singleflight: { methods: ['GET', 'HEAD', 'OPTIONS'] }
 *   })
 * );
 */
export function cacheRequestInterceptor(
  options: CacheRequestInterceptorOptions = {}
): Dispatcher.DispatcherComposeInterceptor {
  const {
    enableIdempotency = true,
    enableSingleflight = true,
    idempotency: idempotencyConfig,
    singleflight: singleflightConfig,
    idempotencyStore,
    singleflightStore,
    onIdempotencyKeyGenerated,
    onRequestCoalesced,
  } = options;

  // Create managers
  const idempotencyManager = enableIdempotency
    ? new IdempotencyManager(idempotencyConfig, idempotencyStore)
    : null;

  const singleflight = enableSingleflight
    ? new Singleflight(singleflightConfig, singleflightStore)
    : null;

  return (dispatch: Dispatcher.Dispatch) => {
    return (
      opts: Dispatcher.DispatchOptions,
      handler: Dispatcher.DispatchHandler
    ): boolean => {
      const method = opts.method;
      const path = opts.path;
      const origin = opts.origin?.toString() ?? '';

      // Build request fingerprint
      const fingerprint: RequestFingerprint = {
        method,
        url: `${origin}${path}`,
        headers: extractHeaders(opts.headers),
        body: extractBody(opts.body),
      };

      // Handle idempotency for mutating methods
      if (idempotencyManager?.requiresIdempotency(method)) {
        return handleIdempotentRequest(
          dispatch,
          opts,
          handler,
          fingerprint,
          idempotencyManager,
          onIdempotencyKeyGenerated
        );
      }

      // Handle singleflight for safe methods
      if (singleflight?.supportsCoalescing(method)) {
        return handleSingleflightRequest(
          dispatch,
          opts,
          handler,
          fingerprint,
          singleflight,
          onRequestCoalesced
        );
      }

      // Pass through for other methods
      return dispatch(opts, handler);
    };
  };
}

/**
 * Handle idempotent request with key management
 */
function handleIdempotentRequest(
  dispatch: Dispatcher.Dispatch,
  opts: Dispatcher.DispatchOptions,
  handler: Dispatcher.DispatchHandler,
  fingerprint: RequestFingerprint,
  manager: IdempotencyManager,
  onKeyGenerated?: (key: string, method: string, path: string) => void
): boolean {
  const headerName = manager.getHeaderName().toLowerCase();

  // Check if idempotency key already exists in headers
  let existingKey: string | undefined;
  if (opts.headers) {
    const headers = opts.headers as Array<Buffer | string> | Record<string, string>;
    if (Array.isArray(headers)) {
      for (let i = 0; i < headers.length; i += 2) {
        if (headers[i]?.toString().toLowerCase() === headerName) {
          existingKey = headers[i + 1]?.toString();
          break;
        }
      }
    } else {
      for (const [key, value] of Object.entries(headers)) {
        if (key.toLowerCase() === headerName) {
          existingKey = value;
          break;
        }
      }
    }
  }

  // Generate or use existing key
  const idempotencyKey = existingKey || manager.generateKey();

  if (!existingKey && onKeyGenerated) {
    onKeyGenerated(idempotencyKey, opts.method, opts.path);
  }

  // Check for cached response
  manager
    .check(idempotencyKey, fingerprint)
    .then((result) => {
      if (result.cached && result.response) {
        // Return cached response
        const cachedResponse = result.response.value as CachedResponseData;
        // Convert headers to Buffer[] if needed
        const headersAsBuffers: Buffer[] = cachedResponse.headers.map(h =>
          Buffer.isBuffer(h) ? h : Buffer.from(h)
        );
        handler.onHeaders?.(
          cachedResponse.statusCode,
          headersAsBuffers,
          () => {},
          cachedResponse.statusText || ''
        );
        if (cachedResponse.body) {
          handler.onData?.(Buffer.from(cachedResponse.body));
        }
        handler.onComplete?.(null);
        return;
      }

      // Execute the request
      executeAndCacheRequest(
        dispatch,
        opts,
        handler,
        idempotencyKey,
        fingerprint,
        manager,
        headerName
      );
    })
    .catch((err) => {
      handler.onError?.(err);
    });

  return true;
}

interface CachedResponseData {
  statusCode: number;
  statusText?: string;
  headers: Buffer[] | string[];
  body?: string;
}

/**
 * Execute request and cache the response
 */
function executeAndCacheRequest(
  dispatch: Dispatcher.Dispatch,
  opts: Dispatcher.DispatchOptions,
  handler: Dispatcher.DispatchHandler,
  idempotencyKey: string,
  fingerprint: RequestFingerprint,
  manager: IdempotencyManager,
  headerName: string
): void {
  // Add idempotency key to headers if not present
  let modifiedHeaders = opts.headers;
  const hasHeader = checkHeaderExists(opts.headers, headerName);

  if (!hasHeader) {
    modifiedHeaders = addHeader(opts.headers, manager.getHeaderName(), idempotencyKey);
  }

  const modifiedOpts = { ...opts, headers: modifiedHeaders };

  // Collect response data for caching
  let responseStatusCode: number;
  let responseStatusText: string;
  let responseHeaders: Buffer[] | string[];
  const responseBody: Buffer[] = [];

  const wrappedHandler: Dispatcher.DispatchHandler = {
    ...handler,
    onHeaders: (statusCode: number, headers: Buffer[], resume: () => void, statusText: string): boolean => {
      responseStatusCode = statusCode;
      responseStatusText = statusText;
      responseHeaders = headers ? [...headers] : [];
      return handler.onHeaders?.(statusCode, headers, resume, statusText) ?? true;
    },
    onData: (chunk: Buffer): boolean => {
      responseBody.push(chunk);
      return handler.onData?.(chunk) ?? true;
    },
    onComplete: (trailers: string[] | null): void => {
      // Cache successful responses (2xx)
      if (responseStatusCode >= 200 && responseStatusCode < 300) {
        const cachedData: CachedResponseData = {
          statusCode: responseStatusCode,
          statusText: responseStatusText,
          headers: responseHeaders,
          body: Buffer.concat(responseBody).toString(),
        };
        manager.storeResponse(idempotencyKey, cachedData, fingerprint).catch(() => {
          // Ignore cache errors
        });
      }
      handler.onComplete?.(trailers);
    },
  };

  dispatch(modifiedOpts, wrappedHandler);
}

/**
 * Handle singleflight request with coalescing
 */
function handleSingleflightRequest(
  dispatch: Dispatcher.Dispatch,
  opts: Dispatcher.DispatchOptions,
  handler: Dispatcher.DispatchHandler,
  fingerprint: RequestFingerprint,
  sf: Singleflight,
  onCoalesced?: (fingerprint: string, subscribers: number) => void
): boolean {
  sf.do(fingerprint, () => executeRequestAsPromise(dispatch, opts))
    .then((result) => {
      if (onCoalesced && result.shared) {
        onCoalesced(sf.generateFingerprint(fingerprint), result.subscribers);
      }

      const response = result.value;
      handler.onHeaders?.(
        response.statusCode,
        response.headers,
        () => {},
        response.statusText
      );
      if (response.body) {
        handler.onData?.(response.body);
      }
      handler.onComplete?.(response.trailers);
    })
    .catch((err) => {
      handler.onError?.(err);
    });

  return true;
}

interface ResponseData {
  statusCode: number;
  statusText: string;
  headers: Buffer[] | string[];
  body: Buffer | null;
  trailers: string[] | null;
}

/**
 * Execute a request and return as a promise
 */
function executeRequestAsPromise(
  dispatch: Dispatcher.Dispatch,
  opts: Dispatcher.DispatchOptions
): Promise<ResponseData> {
  return new Promise((resolve, reject) => {
    let statusCode: number;
    let statusText: string;
    let headers: Buffer[] | string[] = [];
    const bodyChunks: Buffer[] = [];
    let trailers: string[] | null = null;

    const collectHandler: Dispatcher.DispatchHandler = {
      onHeaders: (code: number, hdrs: Buffer[], _resume: () => void, text: string): boolean => {
        statusCode = code;
        statusText = text;
        headers = hdrs ? [...hdrs] : [];
        return true;
      },
      onData: (chunk: Buffer): boolean => {
        bodyChunks.push(chunk);
        return true;
      },
      onComplete: (trlrs: string[] | null): void => {
        trailers = trlrs;
        resolve({
          statusCode,
          statusText,
          headers,
          body: bodyChunks.length > 0 ? Buffer.concat(bodyChunks) : null,
          trailers,
        });
      },
      onError: (err: Error): void => {
        reject(err);
      },
    };

    try {
      dispatch(opts, collectHandler);
    } catch (err) {
      reject(err);
    }
  });
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
        result[key] = value;
      }
    }
  } else if (typeof headers === 'object') {
    for (const [key, value] of Object.entries(headers)) {
      if (typeof value === 'string') {
        result[key] = value;
      } else if (Array.isArray(value)) {
        result[key] = value.join(', ');
      }
    }
  }

  return Object.keys(result).length > 0 ? result : undefined;
}

/**
 * Extract body as string or buffer
 */
function extractBody(body: Dispatcher.DispatchOptions['body']): string | Buffer | null {
  if (!body) return null;
  if (typeof body === 'string') return body;
  if (Buffer.isBuffer(body)) return body;
  return null;
}

/**
 * Check if a header exists
 */
function checkHeaderExists(
  headers: Dispatcher.DispatchOptions['headers'],
  headerName: string
): boolean {
  if (!headers) return false;

  const lowerName = headerName.toLowerCase();

  if (Array.isArray(headers)) {
    for (let i = 0; i < headers.length; i += 2) {
      if (headers[i]?.toString().toLowerCase() === lowerName) {
        return true;
      }
    }
  } else if (typeof headers === 'object') {
    for (const key of Object.keys(headers)) {
      if (key.toLowerCase() === lowerName) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Add a header to the headers object/array
 */
function addHeader(
  headers: Dispatcher.DispatchOptions['headers'],
  name: string,
  value: string
): Dispatcher.DispatchOptions['headers'] {
  if (!headers) {
    return { [name]: value };
  }

  if (Array.isArray(headers)) {
    return [...headers, name, value];
  }

  return { ...headers, [name]: value };
}

export default cacheRequestInterceptor;
