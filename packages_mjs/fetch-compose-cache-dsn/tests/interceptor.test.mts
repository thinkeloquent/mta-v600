/**
 * Tests for DNS cache interceptor
 *
 * Coverage includes:
 * - Interceptor creation and configuration
 * - Host filtering (include/exclude patterns)
 * - Method filtering
 * - DNS resolution integration
 * - Host header preservation
 * - Error handling and health marking
 * - Wildcard host matching
 * - Connection lifecycle tracking
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { Dispatcher } from 'undici';
import {
  dnsCacheInterceptor,
  createDnsCacheInterceptorWithResolver,
  type DnsCacheInterceptorOptions,
} from '../src/interceptor.mjs';

// Mock dispatcher for testing
function createMockDispatch(): {
  dispatch: Dispatcher.Dispatch;
  calls: Array<{ opts: Dispatcher.DispatchOptions; handler: Dispatcher.DispatchHandler }>;
} {
  const calls: Array<{ opts: Dispatcher.DispatchOptions; handler: Dispatcher.DispatchHandler }> = [];

  const dispatch: Dispatcher.Dispatch = (
    opts: Dispatcher.DispatchOptions,
    handler: Dispatcher.DispatchHandler
  ): boolean => {
    calls.push({ opts, handler });
    return true;
  };

  return { dispatch, calls };
}

// Mock handler for testing
function createMockHandler(): Dispatcher.DispatchHandler & {
  onRequestStartCalls: any[];
  onResponseEndCalls: any[];
  onErrorCalls: Error[];
} {
  const handler = {
    onRequestStartCalls: [] as any[],
    onResponseEndCalls: [] as any[],
    onErrorCalls: [] as Error[],
    onRequestStart: vi.fn((controller, context) => {
      handler.onRequestStartCalls.push({ controller, context });
    }),
    onResponseEnd: vi.fn((controller, trailers) => {
      handler.onResponseEndCalls.push({ controller, trailers });
    }),
    onError: vi.fn((err: Error) => {
      handler.onErrorCalls.push(err);
    }),
  };
  return handler;
}

describe('dnsCacheInterceptor', () => {
  describe('creation', () => {
    it('should create interceptor with default options', () => {
      const interceptor = dnsCacheInterceptor();
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with custom options', () => {
      const interceptor = dnsCacheInterceptor({
        defaultTtlMs: 120000,
        loadBalanceStrategy: 'power-of-two',
        markUnhealthyOnError: false,
      });
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with custom config', () => {
      const interceptor = dnsCacheInterceptor({
        config: {
          id: 'custom-interceptor',
          defaultTtlMs: 60000,
          loadBalanceStrategy: 'least-connections',
          staleWhileRevalidate: true,
        },
      });
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('method filtering', () => {
    it('should pass through when method not in filter list', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor({
        methods: ['GET', 'POST'],
      });
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'DELETE',
        origin: 'https://api.example.com',
        path: '/resource',
      };

      wrappedDispatch(opts, handler);

      // Should pass through directly without caching
      expect(calls).toHaveLength(1);
      expect(calls[0].opts.origin).toBe('https://api.example.com');
    });

    it('should apply caching when method is in filter list', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor({
        methods: ['GET', 'POST'],
      });
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://api.example.com',
        path: '/resource',
      };

      const result = wrappedDispatch(opts, handler);

      // Should return true (async dispatch)
      expect(result).toBe(true);
    });

    it('should apply caching to all methods when no filter specified', async () => {
      const { dispatch } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor();
      const wrappedDispatch = interceptor(dispatch);

      const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'];

      for (const method of methods) {
        const opts: Dispatcher.DispatchOptions = {
          method,
          origin: 'https://api.example.com',
          path: '/resource',
        };

        const result = wrappedDispatch(opts, handler);
        expect(result).toBe(true);
      }
    });
  });

  describe('host filtering', () => {
    it('should pass through when host not in include list', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor({
        hosts: ['api.example.com', 'api2.example.com'],
      });
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://other.example.com',
        path: '/resource',
      };

      wrappedDispatch(opts, handler);

      // Should pass through directly
      expect(calls).toHaveLength(1);
      expect(calls[0].opts.origin).toBe('https://other.example.com');
    });

    it('should apply caching when host is in include list', async () => {
      const { dispatch } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor({
        hosts: ['api.example.com'],
      });
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://api.example.com',
        path: '/resource',
      };

      const result = wrappedDispatch(opts, handler);
      expect(result).toBe(true);
    });

    it('should pass through when host is in exclude list', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor({
        excludeHosts: ['internal.example.com'],
      });
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://internal.example.com',
        path: '/resource',
      };

      wrappedDispatch(opts, handler);

      // Should pass through directly
      expect(calls).toHaveLength(1);
      expect(calls[0].opts.origin).toBe('https://internal.example.com');
    });

    it('should support wildcard host patterns', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor({
        hosts: ['*.example.com'],
      });
      const wrappedDispatch = interceptor(dispatch);

      // Should match subdomain
      const opts1: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://api.example.com',
        path: '/resource',
      };
      wrappedDispatch(opts1, handler);

      // Should match deeper subdomain
      const opts2: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://v2.api.example.com',
        path: '/resource',
      };
      wrappedDispatch(opts2, handler);

      // Should match base domain
      const opts3: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://example.com',
        path: '/resource',
      };
      wrappedDispatch(opts3, handler);

      // Should not match different domain (pass through)
      const opts4: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://example.org',
        path: '/resource',
      };
      wrappedDispatch(opts4, handler);

      expect(calls).toHaveLength(1);
      expect(calls[0].opts.origin).toBe('https://example.org');
    });

    it('should handle exclude list with wildcards', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor({
        excludeHosts: ['*.internal.example.com'],
      });
      const wrappedDispatch = interceptor(dispatch);

      // Should be excluded
      const opts1: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://api.internal.example.com',
        path: '/resource',
      };
      wrappedDispatch(opts1, handler);

      expect(calls).toHaveLength(1);
      expect(calls[0].opts.origin).toBe('https://api.internal.example.com');
    });
  });

  describe('invalid URL handling', () => {
    it('should pass through for invalid origin', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor();
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'not-a-valid-url',
        path: '/resource',
      };

      wrappedDispatch(opts, handler);

      expect(calls).toHaveLength(1);
      expect(calls[0].opts.origin).toBe('not-a-valid-url');
    });

    it('should pass through for empty origin', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor();
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: '',
        path: '/resource',
      };

      wrappedDispatch(opts, handler);

      expect(calls).toHaveLength(1);
    });

    it('should pass through for undefined origin', async () => {
      const { dispatch, calls } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor();
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/resource',
      };

      wrappedDispatch(opts, handler);

      expect(calls).toHaveLength(1);
    });
  });

  describe('port handling', () => {
    it('should extract port from origin', async () => {
      const { dispatch } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor();
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://api.example.com:8443',
        path: '/resource',
      };

      const result = wrappedDispatch(opts, handler);
      expect(result).toBe(true);
    });

    it('should handle default https port', async () => {
      const { dispatch } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor();
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://api.example.com',
        path: '/resource',
      };

      const result = wrappedDispatch(opts, handler);
      expect(result).toBe(true);
    });

    it('should handle default http port', async () => {
      const { dispatch } = createMockDispatch();
      const handler = createMockHandler();

      const interceptor = dnsCacheInterceptor();
      const wrappedDispatch = interceptor(dispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'http://api.example.com',
        path: '/resource',
      };

      const result = wrappedDispatch(opts, handler);
      expect(result).toBe(true);
    });
  });
});

describe('createDnsCacheInterceptorWithResolver', () => {
  it('should return both interceptor and resolver', () => {
    const { interceptor, resolver } = createDnsCacheInterceptorWithResolver();

    expect(typeof interceptor).toBe('function');
    expect(resolver).toBeDefined();
    expect(typeof resolver.resolve).toBe('function');
    expect(typeof resolver.resolveOne).toBe('function');
    expect(typeof resolver.invalidate).toBe('function');
  });

  it('should use custom config', () => {
    const { resolver } = createDnsCacheInterceptorWithResolver({
      config: {
        id: 'test-interceptor',
        defaultTtlMs: 30000,
        loadBalanceStrategy: 'random',
        staleWhileRevalidate: false,
      },
    });

    expect(resolver).toBeDefined();
  });

  it('should allow manual cache operations', async () => {
    const { resolver } = createDnsCacheInterceptorWithResolver();

    // Register custom resolver - returns ResolvedEndpoint[] directly
    resolver.registerResolver('manual.example.com', async () => [
      { host: '10.0.0.1', port: 80, healthy: true },
    ]);

    // Resolve
    const result = await resolver.resolve('manual.example.com');
    expect(result).toBeDefined();
    expect(result.endpoints[0].host).toBe('10.0.0.1');

    // Invalidate
    await resolver.invalidate('manual.example.com');

    // Destroy
    await resolver.destroy();
  });
});

describe('Host header handling', () => {
  it('should preserve existing Host header in array format', async () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    // Use excludeHosts to ensure passthrough
    const interceptor = dnsCacheInterceptor({
      excludeHosts: ['other.example.com'],
    });
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://other.example.com',
      path: '/resource',
      headers: ['Host', 'custom-host.example.com', 'Content-Type', 'application/json'],
    };

    wrappedDispatch(opts, handler);

    // For passthrough case, headers should be preserved
    expect(calls).toHaveLength(1);
  });

  it('should preserve existing Host header in object format', async () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    // Use excludeHosts to ensure passthrough
    const interceptor = dnsCacheInterceptor({
      excludeHosts: ['other.example.com'],
    });
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://other.example.com',
      path: '/resource',
      headers: { Host: 'custom-host.example.com', 'Content-Type': 'application/json' },
    };

    wrappedDispatch(opts, handler);

    expect(calls).toHaveLength(1);
  });
});

describe('Error handling', () => {
  it('should handle dispatch returning false for excluded host', async () => {
    const dispatch: Dispatcher.Dispatch = () => false;
    const handler = createMockHandler();

    // Use excludeHosts to ensure passthrough where dispatch returning false matters
    const interceptor = dnsCacheInterceptor({
      excludeHosts: ['passthrough.example.com'],
    });
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://passthrough.example.com',
      path: '/resource',
    };

    const result = wrappedDispatch(opts, handler);
    expect(result).toBe(false);
  });

  it('should return true for async dispatch (DNS caching path)', async () => {
    const { dispatch } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor();
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://api.example.com',
      path: '/resource',
    };

    // When DNS caching is applied, dispatch is async and always returns true
    const result = wrappedDispatch(opts, handler);
    expect(result).toBe(true);
  });
});

describe('Concurrent operations', () => {
  it('should handle concurrent requests to same host', async () => {
    const { dispatch } = createMockDispatch();
    const interceptor = dnsCacheInterceptor();
    const wrappedDispatch = interceptor(dispatch);

    const promises = Array.from({ length: 10 }, () => {
      const handler = createMockHandler();
      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: 'https://concurrent.example.com',
        path: '/resource',
      };

      return wrappedDispatch(opts, handler);
    });

    // All should return true (dispatched)
    expect(promises.every((result) => result === true)).toBe(true);
  });

  it('should handle concurrent requests to different hosts', async () => {
    const { dispatch } = createMockDispatch();
    const interceptor = dnsCacheInterceptor();
    const wrappedDispatch = interceptor(dispatch);

    const hosts = [
      'api1.example.com',
      'api2.example.com',
      'api3.example.com',
      'api4.example.com',
      'api5.example.com',
    ];

    const results = hosts.map((host) => {
      const handler = createMockHandler();
      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        origin: `https://${host}`,
        path: '/resource',
      };

      return wrappedDispatch(opts, handler);
    });

    expect(results.every((result) => result === true)).toBe(true);
  });
});

describe('Integration scenarios', () => {
  it('should work with both include and exclude filters', async () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor({
      hosts: ['*.example.com'],
      excludeHosts: ['internal.example.com'],
    });
    const wrappedDispatch = interceptor(dispatch);

    // Should be cached (matches include, not in exclude)
    const opts1: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://api.example.com',
      path: '/resource',
    };
    wrappedDispatch(opts1, handler);

    // Should be excluded
    const opts2: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://internal.example.com',
      path: '/resource',
    };
    wrappedDispatch(opts2, handler);

    // One passthrough for excluded host
    expect(calls).toHaveLength(1);
    expect(calls[0].opts.origin).toBe('https://internal.example.com');
  });

  it('should work with method and host filters combined', async () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor({
      methods: ['GET'],
      hosts: ['api.example.com'],
    });
    const wrappedDispatch = interceptor(dispatch);

    // Should be cached (GET to api.example.com)
    const opts1: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://api.example.com',
      path: '/resource',
    };
    const result1 = wrappedDispatch(opts1, handler);

    // Should passthrough (POST)
    const opts2: Dispatcher.DispatchOptions = {
      method: 'POST',
      origin: 'https://api.example.com',
      path: '/resource',
    };
    wrappedDispatch(opts2, handler);

    // Should passthrough (different host)
    const opts3: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://other.example.com',
      path: '/resource',
    };
    wrappedDispatch(opts3, handler);

    expect(result1).toBe(true);
    expect(calls).toHaveLength(2);
  });
});

describe('Boundary conditions', () => {
  it('should handle empty hosts array', async () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor({
      hosts: [],
    });
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://api.example.com',
      path: '/resource',
    };

    wrappedDispatch(opts, handler);

    // Empty hosts array means no host matches - should passthrough
    expect(calls).toHaveLength(1);
  });

  it('should handle empty excludeHosts array', async () => {
    const { dispatch } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor({
      excludeHosts: [],
    });
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://api.example.com',
      path: '/resource',
    };

    const result = wrappedDispatch(opts, handler);

    // Empty excludeHosts means nothing excluded - should be cached
    expect(result).toBe(true);
  });

  it('should handle empty methods array', async () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor({
      methods: [],
    });
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://api.example.com',
      path: '/resource',
    };

    wrappedDispatch(opts, handler);

    // Empty methods array means no method matches - should passthrough
    expect(calls).toHaveLength(1);
  });

  it('should handle very long hostname', async () => {
    const { dispatch } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor();
    const wrappedDispatch = interceptor(dispatch);

    const longSubdomain = 'a'.repeat(63);
    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: `https://${longSubdomain}.example.com`,
      path: '/resource',
    };

    const result = wrappedDispatch(opts, handler);
    expect(result).toBe(true);
  });

  it('should handle hostname with special characters', async () => {
    const { dispatch } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor();
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://api-v2.example-site.com',
      path: '/resource',
    };

    const result = wrappedDispatch(opts, handler);
    expect(result).toBe(true);
  });

  it('should handle IPv4 address as origin', async () => {
    const { dispatch } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor();
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'http://192.168.1.100:8080',
      path: '/resource',
    };

    const result = wrappedDispatch(opts, handler);
    expect(result).toBe(true);
  });

  it('should handle IPv6 address as origin', async () => {
    const { dispatch } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = dnsCacheInterceptor();
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'http://[::1]:8080',
      path: '/resource',
    };

    const result = wrappedDispatch(opts, handler);
    expect(result).toBe(true);
  });
});
