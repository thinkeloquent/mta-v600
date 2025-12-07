/**
 * Connection pool interceptor for undici's compose pattern
 */

import type { Dispatcher } from 'undici';
import {
  ConnectionPool,
  type ConnectionPoolConfig,
  type ConnectionPoolStore,
  type ConnectionPoolEventListener,
  type ConnectionPoolEventType,
} from '@internal/connection-pool';

/**
 * Options for the connection pool interceptor
 */
export interface ConnectionPoolInterceptorOptions {
  /** Maximum total connections across all hosts. Default: 100 */
  maxConnections?: number;
  /** Maximum connections per host. Default: 10 */
  maxConnectionsPerHost?: number;
  /** Maximum idle connections to keep. Default: 20 */
  maxIdleConnections?: number;
  /** Idle connection timeout in ms. Default: 60000 (1 minute) */
  idleTimeoutMs?: number;
  /** Keep-alive timeout in ms. Default: 30000 (30 seconds) */
  keepAliveTimeoutMs?: number;
  /** Connection timeout in ms. Default: 10000 (10 seconds) */
  connectTimeoutMs?: number;
  /** Enable keep-alive. Default: true */
  keepAlive?: boolean;
  /** Queue pending requests when at capacity. Default: true */
  queueRequests?: boolean;
  /** Max pending requests in queue. Default: 1000 */
  maxQueueSize?: number;
  /** Request timeout while waiting in queue in ms. Default: 30000 */
  queueTimeoutMs?: number;
  /** Custom connection pool config (alternative to simple options) */
  config?: ConnectionPoolConfig;
  /** Custom store for connection pool */
  store?: ConnectionPoolStore;
  /** Methods to apply connection pooling to. Default: all */
  methods?: string[];
  /** Hosts to apply connection pooling to. Default: all */
  hosts?: string[];
  /** Hosts to exclude from connection pooling */
  excludeHosts?: string[];
}

/**
 * Create a connection pool interceptor for undici's compose pattern
 *
 * This interceptor manages connection reuse and limits concurrent connections
 * per host, providing keep-alive and connection tracking.
 *
 * @param options - Interceptor options
 * @returns Dispatcher compose interceptor
 *
 * @example
 * const client = new Agent().compose(
 *   connectionPoolInterceptor({ maxConnectionsPerHost: 10 }),
 *   interceptors.retry({ maxRetries: 3 })
 * );
 *
 * @example
 * // With custom config
 * const client = new Agent().compose(
 *   connectionPoolInterceptor({
 *     config: {
 *       id: 'api-pool',
 *       maxConnections: 50,
 *       keepAlive: true
 *     }
 *   })
 * );
 */
export function connectionPoolInterceptor(
  options: ConnectionPoolInterceptorOptions = {}
): Dispatcher.DispatcherComposeInterceptor {
  const {
    maxConnections = 100,
    maxConnectionsPerHost = 10,
    maxIdleConnections = 20,
    idleTimeoutMs = 60000,
    keepAliveTimeoutMs = 30000,
    connectTimeoutMs = 10000,
    keepAlive = true,
    queueRequests = true,
    maxQueueSize = 1000,
    queueTimeoutMs = 30000,
    config: customConfig,
    store,
    methods,
    hosts,
    excludeHosts,
  } = options;

  // Build connection pool config
  const config: ConnectionPoolConfig = customConfig ?? {
    id: `interceptor-${Date.now()}`,
    maxConnections,
    maxConnectionsPerHost,
    maxIdleConnections,
    idleTimeoutMs,
    keepAliveTimeoutMs,
    connectTimeoutMs,
    keepAlive,
    queueRequests,
    maxQueueSize,
    queueTimeoutMs,
    enableHealthCheck: true,
    healthCheckIntervalMs: 30000,
    maxConnectionAgeMs: 300000,
  };

  // Create connection pool instance
  const pool = new ConnectionPool(config, store);

  return (dispatch: Dispatcher.Dispatch): Dispatcher.Dispatch => {
    return (
      opts: Dispatcher.DispatchOptions,
      handler: Dispatcher.DispatchHandler
    ): boolean => {
      // Check if this method should use connection pooling
      if (methods && !methods.includes(opts.method)) {
        return dispatch(opts, handler);
      }

      // Extract host from origin
      const origin = opts.origin?.toString() ?? '';
      let host: string;
      let protocol: 'http' | 'https';
      let port: number;

      try {
        const url = new URL(origin);
        host = url.hostname;
        protocol = url.protocol === 'https:' ? 'https' : 'http';
        port = url.port ? parseInt(url.port, 10) : protocol === 'https' ? 443 : 80;
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

      // Acquire connection and dispatch asynchronously
      acquireAndDispatch(pool, host, port, protocol, opts, handler, dispatch).catch(
        () => {
          // Errors are handled inside acquireAndDispatch
        }
      );

      return true;
    };
  };
}

/**
 * Acquire a connection and dispatch the request
 */
async function acquireAndDispatch(
  pool: ConnectionPool,
  host: string,
  port: number,
  protocol: 'http' | 'https',
  opts: Dispatcher.DispatchOptions,
  handler: Dispatcher.DispatchHandler,
  dispatch: Dispatcher.Dispatch
): Promise<void> {
  try {
    // Acquire connection from pool
    const acquired = await pool.acquire({
      host,
      port,
      protocol,
    });

    // Wrap handler to release connection on completion
    const wrappedHandler: Dispatcher.DispatchHandler = {
      ...handler,
      onResponseEnd: (controller, trailers) => {
        // Release connection back to pool
        acquired.release().catch(() => {
          // Ignore release errors
        });
        return handler.onResponseEnd?.(controller, trailers);
      },
    };

    // Dispatch the request
    const result = dispatch(opts, wrappedHandler);

    if (!result) {
      await acquired.fail(new Error('Request not dispatched'));
      throw new Error('Request not dispatched');
    }
  } catch (err) {
    const error = err instanceof Error ? err : new Error(String(err));

    // Call error handler if available
    const handlerWithError = handler as { onError?: (err: Error) => void };
    handlerWithError.onError?.(error);
  }
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
 * Create a connection pool interceptor with access to the pool instance
 */
export function createConnectionPoolInterceptorWithPool(
  options: ConnectionPoolInterceptorOptions = {}
): {
  interceptor: Dispatcher.DispatcherComposeInterceptor;
  pool: ConnectionPool;
} {
  const {
    maxConnections = 100,
    maxConnectionsPerHost = 10,
    maxIdleConnections = 20,
    idleTimeoutMs = 60000,
    keepAliveTimeoutMs = 30000,
    connectTimeoutMs = 10000,
    keepAlive = true,
    queueRequests = true,
    maxQueueSize = 1000,
    queueTimeoutMs = 30000,
    config: customConfig,
    store,
  } = options;

  const config: ConnectionPoolConfig = customConfig ?? {
    id: `interceptor-${Date.now()}`,
    maxConnections,
    maxConnectionsPerHost,
    maxIdleConnections,
    idleTimeoutMs,
    keepAliveTimeoutMs,
    connectTimeoutMs,
    keepAlive,
    queueRequests,
    maxQueueSize,
    queueTimeoutMs,
    enableHealthCheck: true,
    healthCheckIntervalMs: 30000,
    maxConnectionAgeMs: 300000,
  };

  const pool = new ConnectionPool(config, store);

  const interceptor = connectionPoolInterceptor({
    ...options,
    config,
    store: undefined,
  });

  return { interceptor, pool };
}

export default connectionPoolInterceptor;
