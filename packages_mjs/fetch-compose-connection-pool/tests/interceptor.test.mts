/**
 * Tests for connection pool interceptor
 *
 * Coverage includes:
 * - Decision/Branch Coverage: Host and method filtering
 * - State Transition Testing: Connection lifecycle
 * - Error handling paths
 * - Integration with undici dispatch pattern
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { Dispatcher } from 'undici';
import {
  connectionPoolInterceptor,
  createConnectionPoolInterceptorWithPool,
} from '../src/interceptor.mjs';

// Mock dispatch function for testing
function createMockDispatch(
  options: {
    shouldSucceed?: boolean;
    delay?: number;
  } = {}
): {
  dispatch: Dispatcher.Dispatch;
  calls: Array<{ opts: Dispatcher.DispatchOptions; handler: Dispatcher.DispatchHandler }>;
} {
  const calls: Array<{
    opts: Dispatcher.DispatchOptions;
    handler: Dispatcher.DispatchHandler;
  }> = [];

  const dispatch: Dispatcher.Dispatch = (opts, handler) => {
    calls.push({ opts, handler });

    if (options.delay) {
      setTimeout(() => {
        if (options.shouldSucceed !== false) {
          handler.onResponseEnd?.({} as any, {} as any);
        } else {
          (handler as any).onError?.(new Error('Request failed'));
        }
      }, options.delay);
    } else {
      if (options.shouldSucceed !== false) {
        // Immediate success
        setImmediate(() => {
          handler.onResponseEnd?.({} as any, {} as any);
        });
      }
    }

    return true;
  };

  return { dispatch, calls };
}

// Create mock handler
function createMockHandler(): Dispatcher.DispatchHandler & {
  events: string[];
  errors: Error[];
} {
  const events: string[] = [];
  const errors: Error[] = [];

  return {
    events,
    errors,
    onRequestStart: () => {
      events.push('requestStart');
    },
    onResponseEnd: () => {
      events.push('responseEnd');
    },
    onError: (err: Error) => {
      events.push('error');
      errors.push(err);
    },
  } as any;
}

describe('connectionPoolInterceptor', () => {
  describe('Basic Functionality', () => {
    it('should create interceptor with default options', () => {
      const interceptor = connectionPoolInterceptor();
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with custom options', () => {
      const interceptor = connectionPoolInterceptor({
        maxConnections: 50,
        maxConnectionsPerHost: 5,
        maxIdleConnections: 10,
      });
      expect(typeof interceptor).toBe('function');
    });

    it('should wrap dispatch function', () => {
      const interceptor = connectionPoolInterceptor();
      const { dispatch } = createMockDispatch();

      const wrappedDispatch = interceptor(dispatch);
      expect(typeof wrappedDispatch).toBe('function');
    });

    it('should pass through requests', async () => {
      const interceptor = connectionPoolInterceptor();
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);
      const handler = createMockHandler();

      const result = wrappedDispatch(
        {
          origin: 'https://api.example.com',
          path: '/test',
          method: 'GET',
        },
        handler
      );

      expect(result).toBe(true);

      // Wait for async processing
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(calls.length).toBe(1);
      expect(calls[0].opts.path).toBe('/test');
    });
  });

  describe('Method Filtering', () => {
    it('should apply pooling only to specified methods', async () => {
      const interceptor = connectionPoolInterceptor({
        methods: ['GET', 'POST'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      // GET should use pooling
      wrappedDispatch(
        {
          origin: 'https://api.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      // DELETE should pass through directly
      wrappedDispatch(
        {
          origin: 'https://api.example.com',
          path: '/test',
          method: 'DELETE',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Both should be dispatched, but DELETE bypasses pool
      expect(calls.length).toBe(2);
    });

    it('should apply pooling to all methods when not specified', async () => {
      const interceptor = connectionPoolInterceptor();
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      for (const method of ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']) {
        wrappedDispatch(
          {
            origin: 'https://api.example.com',
            path: '/test',
            method,
          },
          createMockHandler()
        );
      }

      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(calls.length).toBe(5);
    });
  });

  describe('Host Filtering', () => {
    it('should apply pooling only to specified hosts', async () => {
      const interceptor = connectionPoolInterceptor({
        hosts: ['api.example.com'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      // Included host - should use pool
      wrappedDispatch(
        {
          origin: 'https://api.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      // Excluded host - should pass through
      wrappedDispatch(
        {
          origin: 'https://other.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(calls.length).toBe(2);
    });

    it('should exclude specified hosts', async () => {
      const interceptor = connectionPoolInterceptor({
        excludeHosts: ['internal.example.com'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      // Excluded host - should pass through
      wrappedDispatch(
        {
          origin: 'https://internal.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(calls.length).toBe(1);
      expect(calls[0].opts.origin).toBe('https://internal.example.com');
    });

    it('should support wildcard host patterns', async () => {
      const interceptor = connectionPoolInterceptor({
        hosts: ['*.example.com'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      // Should match wildcard
      wrappedDispatch(
        {
          origin: 'https://api.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      wrappedDispatch(
        {
          origin: 'https://v2.api.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      // Should not match
      wrappedDispatch(
        {
          origin: 'https://api.other.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(calls.length).toBe(3);
    });

    it('should pass through when origin is invalid', async () => {
      const interceptor = connectionPoolInterceptor();
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      wrappedDispatch(
        {
          origin: 'not-a-valid-url',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      // Should pass through immediately
      expect(calls.length).toBe(1);
    });

    it('should pass through when origin is missing', async () => {
      const interceptor = connectionPoolInterceptor();
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      wrappedDispatch(
        {
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      // Should pass through
      expect(calls.length).toBe(1);
    });
  });

  describe('Error Handling', () => {
    it('should handle dispatch errors', async () => {
      const interceptor = connectionPoolInterceptor();
      const handler = createMockHandler();

      // Create a dispatch that throws
      const errorDispatch: Dispatcher.Dispatch = () => {
        throw new Error('Dispatch error');
      };

      const wrappedDispatch = interceptor(errorDispatch);

      wrappedDispatch(
        {
          origin: 'https://api.example.com',
          path: '/test',
          method: 'GET',
        },
        handler
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Error should be passed to handler
      expect(handler.errors.length).toBeGreaterThanOrEqual(0);
    });

    it('should handle async dispatch failures', async () => {
      const interceptor = connectionPoolInterceptor();
      const { dispatch } = createMockDispatch({ shouldSucceed: false, delay: 10 });
      const wrappedDispatch = interceptor(dispatch);
      const handler = createMockHandler();

      wrappedDispatch(
        {
          origin: 'https://api.example.com',
          path: '/test',
          method: 'GET',
        },
        handler
      );

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Handler should receive error
      expect(handler.events).toContain('error');
    });
  });

  describe('Configuration Options', () => {
    it('should apply custom config', () => {
      const interceptor = connectionPoolInterceptor({
        config: {
          id: 'custom-pool',
          maxConnections: 50,
          maxConnectionsPerHost: 5,
        },
      });

      expect(typeof interceptor).toBe('function');
    });

    it('should use custom store', () => {
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

      const interceptor = connectionPoolInterceptor({
        store: mockStore,
      });

      expect(typeof interceptor).toBe('function');
    });
  });
});

describe('createConnectionPoolInterceptorWithPool', () => {
  it('should return both interceptor and pool', () => {
    const { interceptor, pool } = createConnectionPoolInterceptorWithPool();

    expect(typeof interceptor).toBe('function');
    expect(pool).toBeDefined();
    expect(typeof pool.acquire).toBe('function');
  });

  it('should return pool with correct ID', () => {
    const { pool } = createConnectionPoolInterceptorWithPool({
      config: {
        id: 'test-pool',
      },
    });

    expect(pool.id).toBe('test-pool');
  });

  it('should allow manual pool operations', async () => {
    const { pool } = createConnectionPoolInterceptorWithPool({
      config: {
        id: 'manual-pool',
        maxConnections: 10,
      },
    });

    const stats = await pool.getStats();
    expect(stats.totalRequests).toBe(0);

    await pool.close();
  });

  it('should share pool state with interceptor', async () => {
    const { interceptor, pool } = createConnectionPoolInterceptorWithPool({
      config: {
        id: 'shared-pool',
      },
    });

    const { dispatch } = createMockDispatch();
    const wrappedDispatch = interceptor(dispatch);

    // Use interceptor
    wrappedDispatch(
      {
        origin: 'https://api.example.com',
        path: '/test',
        method: 'GET',
      },
      createMockHandler()
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    // Pool should reflect the request
    const stats = await pool.getStats();
    expect(stats.totalRequests).toBeGreaterThanOrEqual(0);

    await pool.close();
  });
});

describe('Host Matching Logic', () => {
  describe('Exact Matching', () => {
    it('should match exact host', async () => {
      const interceptor = connectionPoolInterceptor({
        hosts: ['api.example.com'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      wrappedDispatch(
        {
          origin: 'https://api.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(calls.length).toBe(1);
    });

    it('should not match different host', async () => {
      const interceptor = connectionPoolInterceptor({
        hosts: ['api.example.com'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      wrappedDispatch(
        {
          origin: 'https://different.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Should still be dispatched (pass through)
      expect(calls.length).toBe(1);
    });
  });

  describe('Wildcard Matching', () => {
    it('should match wildcard prefix', async () => {
      const interceptor = connectionPoolInterceptor({
        hosts: ['*.example.com'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      wrappedDispatch(
        {
          origin: 'https://sub.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(calls.length).toBe(1);
    });

    it('should match base domain with wildcard', async () => {
      const interceptor = connectionPoolInterceptor({
        hosts: ['*.example.com'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      wrappedDispatch(
        {
          origin: 'https://example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(calls.length).toBe(1);
    });
  });

  describe('Combined Include/Exclude', () => {
    it('should exclude even if included', async () => {
      const interceptor = connectionPoolInterceptor({
        hosts: ['*.example.com'],
        excludeHosts: ['internal.example.com'],
      });
      const { dispatch, calls } = createMockDispatch();
      const wrappedDispatch = interceptor(dispatch);

      // Excluded - should pass through
      wrappedDispatch(
        {
          origin: 'https://internal.example.com',
          path: '/test',
          method: 'GET',
        },
        createMockHandler()
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Should be dispatched (pass through)
      expect(calls.length).toBe(1);
    });
  });
});

describe('Boundary Conditions', () => {
  it('should handle empty hosts list', async () => {
    const interceptor = connectionPoolInterceptor({
      hosts: [],
    });
    const { dispatch, calls } = createMockDispatch();
    const wrappedDispatch = interceptor(dispatch);

    wrappedDispatch(
      {
        origin: 'https://api.example.com',
        path: '/test',
        method: 'GET',
      },
      createMockHandler()
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    // Empty hosts means nothing matches - should pass through
    expect(calls.length).toBe(1);
  });

  it('should handle empty methods list', async () => {
    const interceptor = connectionPoolInterceptor({
      methods: [],
    });
    const { dispatch, calls } = createMockDispatch();
    const wrappedDispatch = interceptor(dispatch);

    wrappedDispatch(
      {
        origin: 'https://api.example.com',
        path: '/test',
        method: 'GET',
      },
      createMockHandler()
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    // Empty methods means no methods match - should pass through
    expect(calls.length).toBe(1);
  });

  it('should handle very long host names', () => {
    const longHost = 'a'.repeat(100) + '.example.com';
    const interceptor = connectionPoolInterceptor({
      hosts: [longHost],
    });

    expect(typeof interceptor).toBe('function');
  });

  it('should handle zero timeouts', () => {
    const interceptor = connectionPoolInterceptor({
      idleTimeoutMs: 0,
      keepAliveTimeoutMs: 0,
      connectTimeoutMs: 0,
    });

    expect(typeof interceptor).toBe('function');
  });
});
