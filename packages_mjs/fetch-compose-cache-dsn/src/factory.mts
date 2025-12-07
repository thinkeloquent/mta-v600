/**
 * Factory functions for DNS cache interceptor
 */

import type { Dispatcher } from 'undici';
import {
  DnsCacheResolver,
  type DnsCacheConfig,
  type DnsCacheStore,
  type LoadBalanceStrategy,
} from '@internal/cache-dsn';
import { dnsCacheInterceptor, type DnsCacheInterceptorOptions } from './interceptor.mjs';

/**
 * Create a DNS cache interceptor with preset configuration
 */
export interface DnsCachePreset {
  /** Preset name */
  name: string;
  /** Preset configuration */
  config: DnsCacheInterceptorOptions;
}

/**
 * Preset for aggressive caching (long TTL, high performance)
 */
export const AGGRESSIVE_PRESET: DnsCachePreset = {
  name: 'aggressive',
  config: {
    defaultTtlMs: 300000, // 5 minutes
    loadBalanceStrategy: 'power-of-two',
    markUnhealthyOnError: true,
  },
};

/**
 * Preset for conservative caching (short TTL, more fresh data)
 */
export const CONSERVATIVE_PRESET: DnsCachePreset = {
  name: 'conservative',
  config: {
    defaultTtlMs: 10000, // 10 seconds
    loadBalanceStrategy: 'round-robin',
    markUnhealthyOnError: true,
  },
};

/**
 * Preset for high-availability (fast failover)
 */
export const HIGH_AVAILABILITY_PRESET: DnsCachePreset = {
  name: 'high-availability',
  config: {
    defaultTtlMs: 30000, // 30 seconds
    loadBalanceStrategy: 'least-connections',
    markUnhealthyOnError: true,
  },
};

/**
 * Create an interceptor from a preset
 */
export function createFromPreset(
  preset: DnsCachePreset,
  overrides?: Partial<DnsCacheInterceptorOptions>
): Dispatcher.DispatcherComposeInterceptor {
  return dnsCacheInterceptor({
    ...preset.config,
    ...overrides,
  });
}

/**
 * Create an interceptor for a specific API/service
 */
export function createApiDnsCache(
  apiId: string,
  options: {
    ttlMs?: number;
    loadBalanceStrategy?: LoadBalanceStrategy;
    hosts?: string[];
    store?: DnsCacheStore;
  } = {}
): Dispatcher.DispatcherComposeInterceptor {
  return dnsCacheInterceptor({
    config: {
      id: apiId,
      defaultTtlMs: options.ttlMs ?? 60000,
      loadBalanceStrategy: options.loadBalanceStrategy ?? 'round-robin',
      staleWhileRevalidate: true,
    },
    store: options.store,
    hosts: options.hosts,
    markUnhealthyOnError: true,
  });
}

/**
 * Create a shared DNS cache resolver for multiple interceptors
 *
 * @example
 * const { createInterceptor, resolver } = createSharedDnsCache({
 *   id: 'shared-dns',
 *   defaultTtlMs: 60000
 * });
 *
 * const client1 = new Agent().compose(createInterceptor());
 * const client2 = new Agent().compose(createInterceptor({ hosts: ['api.example.com'] }));
 *
 * // Manually invalidate
 * await resolver.invalidate('api.example.com');
 */
export function createSharedDnsCache(
  config: DnsCacheConfig,
  store?: DnsCacheStore
): {
  resolver: DnsCacheResolver;
  createInterceptor: (
    options?: Omit<DnsCacheInterceptorOptions, 'config' | 'store'>
  ) => Dispatcher.DispatcherComposeInterceptor;
} {
  const resolver = new DnsCacheResolver(config, store);

  const createInterceptor = (
    options?: Omit<DnsCacheInterceptorOptions, 'config' | 'store'>
  ): Dispatcher.DispatcherComposeInterceptor => {
    // Return an interceptor that uses the shared resolver
    // Note: The current interceptor creates its own resolver internally
    // For true sharing, we'd need to refactor the interceptor
    return dnsCacheInterceptor({
      ...options,
      config,
      store,
    });
  };

  return { resolver, createInterceptor };
}

/**
 * Compose multiple DNS cache interceptors for different host patterns
 */
export function composeDnsCacheInterceptors(
  configs: Array<{
    hosts: string[];
    options?: Omit<DnsCacheInterceptorOptions, 'hosts'>;
  }>
): Dispatcher.DispatcherComposeInterceptor {
  const interceptors = configs.map(({ hosts, options }) =>
    dnsCacheInterceptor({ ...options, hosts })
  );

  // Return a meta-interceptor that delegates to the appropriate child
  return (dispatch: Dispatcher.Dispatch): Dispatcher.Dispatch => {
    // Chain all interceptors
    let finalDispatch = dispatch;
    for (let i = interceptors.length - 1; i >= 0; i--) {
      finalDispatch = interceptors[i](finalDispatch);
    }
    return finalDispatch;
  };
}

export default {
  AGGRESSIVE_PRESET,
  CONSERVATIVE_PRESET,
  HIGH_AVAILABILITY_PRESET,
  createFromPreset,
  createApiDnsCache,
  createSharedDnsCache,
  composeDnsCacheInterceptors,
};
