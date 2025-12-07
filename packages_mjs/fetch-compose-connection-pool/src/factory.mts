/**
 * Factory functions for connection pool interceptor
 */

import type { Dispatcher } from 'undici';
import {
  ConnectionPool,
  type ConnectionPoolConfig,
  type ConnectionPoolStore,
} from '@internal/connection-pool';
import {
  connectionPoolInterceptor,
  type ConnectionPoolInterceptorOptions,
} from './interceptor.mjs';

/**
 * Preset configuration for connection pool
 */
export interface ConnectionPoolPreset {
  /** Preset name */
  name: string;
  /** Preset configuration */
  config: ConnectionPoolInterceptorOptions;
}

/**
 * Preset for high-concurrency workloads (many connections)
 */
export const HIGH_CONCURRENCY_PRESET: ConnectionPoolPreset = {
  name: 'high-concurrency',
  config: {
    maxConnections: 200,
    maxConnectionsPerHost: 20,
    maxIdleConnections: 50,
    idleTimeoutMs: 30000,
    keepAliveTimeoutMs: 15000,
    queueRequests: true,
    maxQueueSize: 2000,
  },
};

/**
 * Preset for low-latency workloads (keep connections warm)
 */
export const LOW_LATENCY_PRESET: ConnectionPoolPreset = {
  name: 'low-latency',
  config: {
    maxConnections: 100,
    maxConnectionsPerHost: 10,
    maxIdleConnections: 30,
    idleTimeoutMs: 120000,
    keepAliveTimeoutMs: 60000,
    queueRequests: true,
    maxQueueSize: 500,
  },
};

/**
 * Preset for resource-constrained environments
 */
export const MINIMAL_PRESET: ConnectionPoolPreset = {
  name: 'minimal',
  config: {
    maxConnections: 20,
    maxConnectionsPerHost: 5,
    maxIdleConnections: 5,
    idleTimeoutMs: 10000,
    keepAliveTimeoutMs: 5000,
    queueRequests: true,
    maxQueueSize: 100,
  },
};

/**
 * Create an interceptor from a preset
 */
export function createFromPreset(
  preset: ConnectionPoolPreset,
  overrides?: Partial<ConnectionPoolInterceptorOptions>
): Dispatcher.DispatcherComposeInterceptor {
  return connectionPoolInterceptor({
    ...preset.config,
    ...overrides,
  });
}

/**
 * Create an interceptor for a specific API/service
 */
export function createApiConnectionPool(
  apiId: string,
  options: {
    maxConnectionsPerHost?: number;
    maxIdleConnections?: number;
    idleTimeoutMs?: number;
    hosts?: string[];
    store?: ConnectionPoolStore;
  } = {}
): Dispatcher.DispatcherComposeInterceptor {
  return connectionPoolInterceptor({
    config: {
      id: apiId,
      maxConnections: 100,
      maxConnectionsPerHost: options.maxConnectionsPerHost ?? 10,
      maxIdleConnections: options.maxIdleConnections ?? 20,
      idleTimeoutMs: options.idleTimeoutMs ?? 60000,
      keepAliveTimeoutMs: 30000,
      connectTimeoutMs: 10000,
      keepAlive: true,
      queueRequests: true,
      maxQueueSize: 1000,
      queueTimeoutMs: 30000,
      enableHealthCheck: true,
      healthCheckIntervalMs: 30000,
      maxConnectionAgeMs: 300000,
    },
    store: options.store,
    hosts: options.hosts,
  });
}

/**
 * Create a shared connection pool for multiple interceptors
 *
 * @example
 * const { createInterceptor, pool } = createSharedConnectionPool({
 *   id: 'shared-pool',
 *   maxConnections: 200
 * });
 *
 * const client1 = new Agent().compose(createInterceptor());
 * const client2 = new Agent().compose(createInterceptor({ hosts: ['api.example.com'] }));
 *
 * // Get pool stats
 * const stats = await pool.getStats();
 */
export function createSharedConnectionPool(
  config: ConnectionPoolConfig,
  store?: ConnectionPoolStore
): {
  pool: ConnectionPool;
  createInterceptor: (
    options?: Omit<ConnectionPoolInterceptorOptions, 'config' | 'store'>
  ) => Dispatcher.DispatcherComposeInterceptor;
} {
  const pool = new ConnectionPool(config, store);

  const createInterceptor = (
    options?: Omit<ConnectionPoolInterceptorOptions, 'config' | 'store'>
  ): Dispatcher.DispatcherComposeInterceptor => {
    return connectionPoolInterceptor({
      ...options,
      config,
      store,
    });
  };

  return { pool, createInterceptor };
}

/**
 * Compose multiple connection pool interceptors for different host patterns
 */
export function composeConnectionPoolInterceptors(
  configs: Array<{
    hosts: string[];
    options?: Omit<ConnectionPoolInterceptorOptions, 'hosts'>;
  }>
): Dispatcher.DispatcherComposeInterceptor {
  const interceptors = configs.map(({ hosts, options }) =>
    connectionPoolInterceptor({ ...options, hosts })
  );

  // Return a meta-interceptor that chains all interceptors
  return (dispatch: Dispatcher.Dispatch): Dispatcher.Dispatch => {
    let finalDispatch = dispatch;
    for (let i = interceptors.length - 1; i >= 0; i--) {
      finalDispatch = interceptors[i](finalDispatch);
    }
    return finalDispatch;
  };
}

export default {
  HIGH_CONCURRENCY_PRESET,
  LOW_LATENCY_PRESET,
  MINIMAL_PRESET,
  createFromPreset,
  createApiConnectionPool,
  createSharedConnectionPool,
  composeConnectionPoolInterceptors,
};
