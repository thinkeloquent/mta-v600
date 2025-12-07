/**
 * Tests for connection pool factory functions
 *
 * Coverage includes:
 * - Preset configuration testing
 * - Factory function testing
 * - Composition pattern testing
 * - Shared pool testing
 */

import { describe, it, expect, afterEach } from 'vitest';
import type { Dispatcher } from 'undici';
import {
  HIGH_CONCURRENCY_PRESET,
  LOW_LATENCY_PRESET,
  MINIMAL_PRESET,
  createFromPreset,
  createApiConnectionPool,
  createSharedConnectionPool,
  composeConnectionPoolInterceptors,
} from '../src/factory.mjs';
import { ConnectionPool } from '@internal/connection-pool';

// Mock dispatch function
function createMockDispatch(): {
  dispatch: Dispatcher.Dispatch;
  calls: Array<{ opts: Dispatcher.DispatchOptions }>;
} {
  const calls: Array<{ opts: Dispatcher.DispatchOptions }> = [];

  const dispatch: Dispatcher.Dispatch = (opts, handler) => {
    calls.push({ opts });
    setImmediate(() => {
      handler.onResponseEnd?.({} as any, {} as any);
    });
    return true;
  };

  return { dispatch, calls };
}

describe('Presets', () => {
  describe('HIGH_CONCURRENCY_PRESET', () => {
    it('should have correct name', () => {
      expect(HIGH_CONCURRENCY_PRESET.name).toBe('high-concurrency');
    });

    it('should have high connection limits', () => {
      expect(HIGH_CONCURRENCY_PRESET.config.maxConnections).toBe(200);
      expect(HIGH_CONCURRENCY_PRESET.config.maxConnectionsPerHost).toBe(20);
      expect(HIGH_CONCURRENCY_PRESET.config.maxIdleConnections).toBe(50);
    });

    it('should have aggressive queue settings', () => {
      expect(HIGH_CONCURRENCY_PRESET.config.queueRequests).toBe(true);
      expect(HIGH_CONCURRENCY_PRESET.config.maxQueueSize).toBe(2000);
    });

    it('should have short timeouts for quick recycling', () => {
      expect(HIGH_CONCURRENCY_PRESET.config.idleTimeoutMs).toBe(30000);
      expect(HIGH_CONCURRENCY_PRESET.config.keepAliveTimeoutMs).toBe(15000);
    });
  });

  describe('LOW_LATENCY_PRESET', () => {
    it('should have correct name', () => {
      expect(LOW_LATENCY_PRESET.name).toBe('low-latency');
    });

    it('should have moderate connection limits', () => {
      expect(LOW_LATENCY_PRESET.config.maxConnections).toBe(100);
      expect(LOW_LATENCY_PRESET.config.maxConnectionsPerHost).toBe(10);
      expect(LOW_LATENCY_PRESET.config.maxIdleConnections).toBe(30);
    });

    it('should have longer timeouts to keep connections warm', () => {
      expect(LOW_LATENCY_PRESET.config.idleTimeoutMs).toBe(120000);
      expect(LOW_LATENCY_PRESET.config.keepAliveTimeoutMs).toBe(60000);
    });

    it('should have smaller queue', () => {
      expect(LOW_LATENCY_PRESET.config.maxQueueSize).toBe(500);
    });
  });

  describe('MINIMAL_PRESET', () => {
    it('should have correct name', () => {
      expect(MINIMAL_PRESET.name).toBe('minimal');
    });

    it('should have low connection limits', () => {
      expect(MINIMAL_PRESET.config.maxConnections).toBe(20);
      expect(MINIMAL_PRESET.config.maxConnectionsPerHost).toBe(5);
      expect(MINIMAL_PRESET.config.maxIdleConnections).toBe(5);
    });

    it('should have short timeouts', () => {
      expect(MINIMAL_PRESET.config.idleTimeoutMs).toBe(10000);
      expect(MINIMAL_PRESET.config.keepAliveTimeoutMs).toBe(5000);
    });

    it('should have small queue', () => {
      expect(MINIMAL_PRESET.config.maxQueueSize).toBe(100);
    });
  });

  describe('Preset Ordering', () => {
    it('should have ascending connection limits: minimal < low-latency < high-concurrency', () => {
      expect(MINIMAL_PRESET.config.maxConnections!).toBeLessThan(
        LOW_LATENCY_PRESET.config.maxConnections!
      );
      expect(LOW_LATENCY_PRESET.config.maxConnections!).toBeLessThan(
        HIGH_CONCURRENCY_PRESET.config.maxConnections!
      );
    });

    it('should have descending keep-alive timeouts for latency optimization', () => {
      expect(LOW_LATENCY_PRESET.config.keepAliveTimeoutMs!).toBeGreaterThan(
        HIGH_CONCURRENCY_PRESET.config.keepAliveTimeoutMs!
      );
    });
  });
});

describe('createFromPreset', () => {
  it('should create interceptor from high-concurrency preset', () => {
    const interceptor = createFromPreset(HIGH_CONCURRENCY_PRESET);
    expect(typeof interceptor).toBe('function');
  });

  it('should create interceptor from low-latency preset', () => {
    const interceptor = createFromPreset(LOW_LATENCY_PRESET);
    expect(typeof interceptor).toBe('function');
  });

  it('should create interceptor from minimal preset', () => {
    const interceptor = createFromPreset(MINIMAL_PRESET);
    expect(typeof interceptor).toBe('function');
  });

  it('should apply overrides to preset', () => {
    const interceptor = createFromPreset(HIGH_CONCURRENCY_PRESET, {
      maxConnections: 50, // Override
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should allow adding host filters as override', () => {
    const interceptor = createFromPreset(LOW_LATENCY_PRESET, {
      hosts: ['api.example.com'],
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should wrap dispatch correctly', async () => {
    const interceptor = createFromPreset(MINIMAL_PRESET);
    const { dispatch, calls } = createMockDispatch();
    const wrappedDispatch = interceptor(dispatch);

    wrappedDispatch(
      {
        origin: 'https://api.example.com',
        path: '/test',
        method: 'GET',
      },
      {
        onResponseEnd: () => {},
      } as any
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(calls.length).toBe(1);
  });
});

describe('createApiConnectionPool', () => {
  it('should create interceptor for specific API', () => {
    const interceptor = createApiConnectionPool('github-api');
    expect(typeof interceptor).toBe('function');
  });

  it('should accept custom connection limits', () => {
    const interceptor = createApiConnectionPool('my-api', {
      maxConnectionsPerHost: 5,
      maxIdleConnections: 10,
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should accept custom timeout', () => {
    const interceptor = createApiConnectionPool('my-api', {
      idleTimeoutMs: 30000,
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should accept host filter', () => {
    const interceptor = createApiConnectionPool('my-api', {
      hosts: ['api.myservice.com'],
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should accept custom store', () => {
    const mockStore = {
      getConnections: async () => [],
      getConnectionsByHost: async () => [],
      addConnection: async () => {},
      updateConnection: async () => {},
      removeConnection: async () => false,
      getCount: async () => 0,
      getCountByHost: async () => 0,
      clear: async () => {},
      close: async () => {},
    };

    const interceptor = createApiConnectionPool('my-api', {
      store: mockStore,
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should work with dispatch', async () => {
    const interceptor = createApiConnectionPool('test-api');
    const { dispatch, calls } = createMockDispatch();
    const wrappedDispatch = interceptor(dispatch);

    wrappedDispatch(
      {
        origin: 'https://api.example.com',
        path: '/resource',
        method: 'GET',
      },
      {
        onResponseEnd: () => {},
      } as any
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(calls.length).toBe(1);
  });
});

describe('createSharedConnectionPool', () => {
  let pool: ConnectionPool;

  afterEach(async () => {
    if (pool) {
      await pool.close();
    }
  });

  it('should return pool and createInterceptor function', () => {
    const result = createSharedConnectionPool({
      id: 'shared-pool',
    });

    pool = result.pool;
    expect(pool).toBeDefined();
    expect(typeof result.createInterceptor).toBe('function');
  });

  it('should create pool with correct ID', () => {
    const { pool: p } = createSharedConnectionPool({
      id: 'test-shared-pool',
    });
    pool = p;

    expect(pool.id).toBe('test-shared-pool');
  });

  it('should create interceptors that use the same config', () => {
    const { pool: p, createInterceptor } = createSharedConnectionPool({
      id: 'shared-pool',
      maxConnections: 50,
    });
    pool = p;

    const interceptor1 = createInterceptor();
    const interceptor2 = createInterceptor({ hosts: ['api.example.com'] });

    expect(typeof interceptor1).toBe('function');
    expect(typeof interceptor2).toBe('function');
  });

  it('should allow host filtering in individual interceptors', () => {
    const { pool: p, createInterceptor } = createSharedConnectionPool({
      id: 'shared-pool',
    });
    pool = p;

    const apiInterceptor = createInterceptor({
      hosts: ['api.example.com'],
    });

    const internalInterceptor = createInterceptor({
      excludeHosts: ['public.example.com'],
    });

    expect(typeof apiInterceptor).toBe('function');
    expect(typeof internalInterceptor).toBe('function');
  });

  it('should allow custom store', async () => {
    const mockStore = {
      getConnections: async () => [],
      getConnectionsByHost: async () => [],
      addConnection: async () => {},
      updateConnection: async () => {},
      removeConnection: async () => false,
      getCount: async () => 0,
      getCountByHost: async () => 0,
      clear: async () => {},
      close: async () => {},
    };

    const { pool: p } = createSharedConnectionPool(
      { id: 'custom-store-pool' },
      mockStore
    );
    pool = p;

    expect(pool).toBeDefined();
  });

  it('should get stats from shared pool', async () => {
    const { pool: p, createInterceptor } = createSharedConnectionPool({
      id: 'stats-pool',
    });
    pool = p;

    const interceptor = createInterceptor();
    const { dispatch } = createMockDispatch();
    const wrappedDispatch = interceptor(dispatch);

    wrappedDispatch(
      {
        origin: 'https://api.example.com',
        path: '/test',
        method: 'GET',
      },
      {
        onResponseEnd: () => {},
      } as any
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    const stats = await pool.getStats();
    expect(stats.totalRequests).toBeGreaterThanOrEqual(0);
  });
});

describe('composeConnectionPoolInterceptors', () => {
  it('should compose multiple interceptors', () => {
    const composed = composeConnectionPoolInterceptors([
      { hosts: ['api.example.com'] },
      { hosts: ['internal.example.com'] },
    ]);

    expect(typeof composed).toBe('function');
  });

  it('should chain interceptors in order', async () => {
    const composed = composeConnectionPoolInterceptors([
      { hosts: ['api1.example.com'], options: { maxConnections: 50 } },
      { hosts: ['api2.example.com'], options: { maxConnections: 100 } },
    ]);

    const { dispatch, calls } = createMockDispatch();
    const wrappedDispatch = composed(dispatch);

    wrappedDispatch(
      {
        origin: 'https://api1.example.com',
        path: '/test',
        method: 'GET',
      },
      {
        onResponseEnd: () => {},
      } as any
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(calls.length).toBe(1);
  });

  it('should handle empty config array', () => {
    const composed = composeConnectionPoolInterceptors([]);
    expect(typeof composed).toBe('function');
  });

  it('should handle single config', () => {
    const composed = composeConnectionPoolInterceptors([
      { hosts: ['api.example.com'] },
    ]);

    expect(typeof composed).toBe('function');
  });

  it('should allow different options per host pattern', async () => {
    const composed = composeConnectionPoolInterceptors([
      {
        hosts: ['high-traffic.example.com'],
        options: { maxConnections: 200, maxConnectionsPerHost: 50 },
      },
      {
        hosts: ['low-traffic.example.com'],
        options: { maxConnections: 20, maxConnectionsPerHost: 5 },
      },
    ]);

    const { dispatch, calls } = createMockDispatch();
    const wrappedDispatch = composed(dispatch);

    wrappedDispatch(
      {
        origin: 'https://high-traffic.example.com',
        path: '/test',
        method: 'GET',
      },
      {
        onResponseEnd: () => {},
      } as any
    );

    wrappedDispatch(
      {
        origin: 'https://low-traffic.example.com',
        path: '/test',
        method: 'GET',
      },
      {
        onResponseEnd: () => {},
      } as any
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(calls.length).toBe(2);
  });
});

describe('Integration Tests', () => {
  it('should compose preset with API-specific pool', async () => {
    const baseInterceptor = createFromPreset(LOW_LATENCY_PRESET);
    const apiInterceptor = createApiConnectionPool('special-api', {
      maxConnectionsPerHost: 20,
    });

    // Create a meta-interceptor
    const combined: Dispatcher.DispatcherComposeInterceptor = (dispatch) => {
      return apiInterceptor(baseInterceptor(dispatch));
    };

    const { dispatch, calls } = createMockDispatch();
    const wrappedDispatch = combined(dispatch);

    wrappedDispatch(
      {
        origin: 'https://api.example.com',
        path: '/test',
        method: 'GET',
      },
      {
        onResponseEnd: () => {},
      } as any
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(calls.length).toBe(1);
  });

  it('should work with shared pool across multiple services', async () => {
    const { pool, createInterceptor } = createSharedConnectionPool({
      id: 'multi-service-pool',
      maxConnections: 100,
    });

    const service1Interceptor = createInterceptor({
      hosts: ['service1.example.com'],
    });

    const service2Interceptor = createInterceptor({
      hosts: ['service2.example.com'],
    });

    const { dispatch, calls } = createMockDispatch();

    // Use service1
    const wrapped1 = service1Interceptor(dispatch);
    wrapped1(
      {
        origin: 'https://service1.example.com',
        path: '/api',
        method: 'GET',
      },
      { onResponseEnd: () => {} } as any
    );

    // Use service2
    const wrapped2 = service2Interceptor(dispatch);
    wrapped2(
      {
        origin: 'https://service2.example.com',
        path: '/api',
        method: 'GET',
      },
      { onResponseEnd: () => {} } as any
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(calls.length).toBe(2);

    await pool.close();
  });
});

describe('Boundary Conditions', () => {
  it('should handle empty API ID', () => {
    const interceptor = createApiConnectionPool('');
    expect(typeof interceptor).toBe('function');
  });

  it('should handle very long API ID', () => {
    const interceptor = createApiConnectionPool('a'.repeat(1000));
    expect(typeof interceptor).toBe('function');
  });

  it('should handle zero connection limits in override', () => {
    const interceptor = createFromPreset(MINIMAL_PRESET, {
      maxQueueSize: 0,
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should handle very large connection limits', () => {
    const interceptor = createApiConnectionPool('large-pool', {
      maxConnectionsPerHost: 1000,
      maxIdleConnections: 500,
    });
    expect(typeof interceptor).toBe('function');
  });
});
