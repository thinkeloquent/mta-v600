/**
 * DNS cache interceptor for undici's compose pattern
 */

import type { Dispatcher } from 'undici';
import {
  DnsCacheResolver,
  type DnsCacheConfig,
  type DnsCacheStore,
  type LoadBalanceStrategy,
  type ResolvedEndpoint,
} from '@internal/cache-dsn';

/**
 * Options for the DNS cache interceptor
 */
export interface DnsCacheInterceptorOptions {
  /** Default TTL for cached entries (ms). Default: 60000 */
  defaultTtlMs?: number;
  /** Load balancing strategy. Default: 'round-robin' */
  loadBalanceStrategy?: LoadBalanceStrategy;
  /** Custom DNS cache config (alternative to simple options) */
  config?: DnsCacheConfig;
  /** Custom store for DNS cache */
  store?: DnsCacheStore;
  /** Whether to mark endpoints unhealthy on connection errors. Default: true */
  markUnhealthyOnError?: boolean;
  /** Methods to apply DNS caching to. Default: all */
  methods?: string[];
  /** Hosts to apply DNS caching to. Default: all */
  hosts?: string[];
  /** Hosts to exclude from DNS caching */
  excludeHosts?: string[];
}

/**
 * Create a DNS cache interceptor for undici's compose pattern
 *
 * This interceptor integrates with undici's dispatcher composition,
 * providing cached DNS resolution with load balancing.
 *
 * @param options - Interceptor options
 * @returns Dispatcher compose interceptor
 *
 * @example
 * const client = new Agent().compose(
 *   dnsCacheInterceptor({ loadBalanceStrategy: 'power-of-two' }),
 *   interceptors.retry({ maxRetries: 3 })
 * );
 *
 * @example
 * // With custom config
 * const client = new Agent().compose(
 *   dnsCacheInterceptor({
 *     config: {
 *       id: 'api-dns',
 *       defaultTtlMs: 120000,
 *       staleWhileRevalidate: true
 *     }
 *   })
 * );
 */
export function dnsCacheInterceptor(
  options: DnsCacheInterceptorOptions = {}
): Dispatcher.DispatcherComposeInterceptor {
  const {
    defaultTtlMs = 60000,
    loadBalanceStrategy = 'round-robin',
    config: customConfig,
    store,
    markUnhealthyOnError = true,
    methods,
    hosts,
    excludeHosts,
  } = options;

  // Build DNS cache config
  const config: DnsCacheConfig = customConfig ?? {
    id: `interceptor-${Date.now()}`,
    defaultTtlMs,
    loadBalanceStrategy,
    staleWhileRevalidate: true,
  };

  // Create DNS cache resolver instance
  const resolver = new DnsCacheResolver(config, store);

  return (dispatch: Dispatcher.Dispatch): Dispatcher.Dispatch => {
    return (
      opts: Dispatcher.DispatchOptions,
      handler: Dispatcher.DispatchHandler
    ): boolean => {
      // Check if this method should use DNS caching
      if (methods && !methods.includes(opts.method)) {
        return dispatch(opts, handler);
      }

      // Extract host from origin
      const origin = opts.origin?.toString() ?? '';
      let host: string;
      let protocol: string;
      let port: number | undefined;

      try {
        const url = new URL(origin);
        host = url.hostname;
        protocol = url.protocol;
        port = url.port ? parseInt(url.port, 10) : undefined;
      } catch {
        // Invalid URL, pass through
        return dispatch(opts, handler);
      }

      // Check host filters
      if (hosts && !hosts.some((h) => hostMatches(host, h))) {
        return dispatch(opts, handler);
      }

      if (excludeHosts && excludeHosts.some((h) => hostMatches(host, h))) {
        return dispatch(opts, handler);
      }

      // Track selected endpoint for connection tracking
      let selectedEndpoint: ResolvedEndpoint | undefined;

      // Wrap handler to track connection lifecycle
      const wrappedHandler: Dispatcher.DispatchHandler = {
        ...handler,
        onRequestStart: (controller, context) => {
          // Increment connection count when request starts
          if (selectedEndpoint) {
            resolver.incrementConnections(selectedEndpoint);
          }
          return handler.onRequestStart?.(controller, context);
        },
        onResponseEnd: (controller, trailers) => {
          // Decrement connection count on completion
          if (selectedEndpoint) {
            resolver.decrementConnections(selectedEndpoint);
          }
          return handler.onResponseEnd?.(controller, trailers);
        },
      };

      // Resolve and dispatch asynchronously
      resolveAndDispatch(
        resolver,
        host,
        protocol,
        port,
        opts,
        wrappedHandler,
        dispatch,
        markUnhealthyOnError,
        (endpoint) => {
          selectedEndpoint = endpoint;
        }
      ).catch(() => {
        // Errors are handled inside resolveAndDispatch
      });

      return true;
    };
  };
}

/**
 * Resolve DNS and dispatch the request
 */
async function resolveAndDispatch(
  resolver: DnsCacheResolver,
  host: string,
  protocol: string,
  port: number | undefined,
  opts: Dispatcher.DispatchOptions,
  handler: Dispatcher.DispatchHandler,
  dispatch: Dispatcher.Dispatch,
  markUnhealthyOnError: boolean,
  onEndpointSelected: (endpoint: ResolvedEndpoint) => void
): Promise<void> {
  try {
    // Resolve the hostname
    const endpoint = await resolver.resolveOne(host);

    if (!endpoint) {
      throw new Error(`No endpoints available for ${host}`);
    }

    onEndpointSelected(endpoint);

    // Build new origin with resolved IP
    const resolvedPort = endpoint.port || port || (protocol === 'https:' ? 443 : 80);
    const resolvedOrigin = `${protocol}//${endpoint.host}:${resolvedPort}`;

    // Create modified options with resolved origin and original Host header
    const modifiedOpts: Dispatcher.DispatchOptions = {
      ...opts,
      origin: resolvedOrigin,
      headers: ensureHostHeader(opts.headers, host, port),
    };

    // Dispatch the request
    const result = dispatch(modifiedOpts, handler);

    if (!result) {
      throw new Error('Request not dispatched');
    }
  } catch (err) {
    // Decrement connection if we incremented but failed
    const error = err instanceof Error ? err : new Error(String(err));

    if (markUnhealthyOnError && isConnectionError(error)) {
      // Try to get endpoint to mark unhealthy
      const cached = await resolver.resolve(host).catch(() => null);
      if (cached && cached.endpoints.length > 0) {
        await resolver.markUnhealthy(host, cached.endpoints[0]).catch(() => {});
      }
    }

    // Call error handler if available - use type assertion for compatibility
    const handlerWithError = handler as { onError?: (err: Error) => void };
    handlerWithError.onError?.(error);
  }
}

/**
 * Ensure the Host header is set to the original hostname
 */
function ensureHostHeader(
  headers: Dispatcher.DispatchOptions['headers'],
  host: string,
  port?: number
): Dispatcher.DispatchOptions['headers'] {
  const hostValue = port ? `${host}:${port}` : host;

  if (Array.isArray(headers)) {
    // Check if Host header already exists
    for (let i = 0; i < headers.length; i += 2) {
      if (headers[i]?.toString().toLowerCase() === 'host') {
        return headers; // Already has Host header
      }
    }
    // Add Host header
    return [...headers, 'Host', hostValue];
  }

  if (headers && typeof headers === 'object') {
    // Check if Host header already exists (case-insensitive)
    const headerObj = headers as Record<string, string | string[] | undefined>;
    for (const key of Object.keys(headerObj)) {
      if (key.toLowerCase() === 'host') {
        return headers; // Already has Host header
      }
    }
    // Add Host header
    return { ...headerObj, Host: hostValue };
  }

  // No existing headers
  return { Host: hostValue };
}

/**
 * Check if a hostname matches a pattern
 */
function hostMatches(host: string, pattern: string): boolean {
  // Exact match
  if (host === pattern) return true;

  // Wildcard match (e.g., *.example.com)
  if (pattern.startsWith('*.')) {
    const suffix = pattern.substring(1); // .example.com
    return host.endsWith(suffix) || host === pattern.substring(2);
  }

  return false;
}

/**
 * Check if an error is a connection-related error
 */
function isConnectionError(err: Error): boolean {
  const errorCodes = [
    'ECONNREFUSED',
    'ECONNRESET',
    'ETIMEDOUT',
    'ENOTFOUND',
    'EHOSTUNREACH',
    'ENETUNREACH',
    'UND_ERR_CONNECT_TIMEOUT',
  ];

  const code = (err as NodeJS.ErrnoException).code;
  return code !== undefined && errorCodes.includes(code);
}

/**
 * Get the DNS cache resolver from an interceptor
 * Useful for manual operations like invalidation
 */
export function createDnsCacheInterceptorWithResolver(
  options: DnsCacheInterceptorOptions = {}
): {
  interceptor: Dispatcher.DispatcherComposeInterceptor;
  resolver: DnsCacheResolver;
} {
  const {
    defaultTtlMs = 60000,
    loadBalanceStrategy = 'round-robin',
    config: customConfig,
    store,
  } = options;

  const config: DnsCacheConfig = customConfig ?? {
    id: `interceptor-${Date.now()}`,
    defaultTtlMs,
    loadBalanceStrategy,
    staleWhileRevalidate: true,
  };

  const resolver = new DnsCacheResolver(config, store);

  const interceptor = dnsCacheInterceptor({
    ...options,
    config,
    store: undefined, // Don't pass store, resolver already has it
  });

  return { interceptor, resolver };
}

export default dnsCacheInterceptor;
