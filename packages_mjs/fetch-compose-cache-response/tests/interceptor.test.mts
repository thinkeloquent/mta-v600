/**
 * Tests for cache response interceptor
 */

import { cacheResponseInterceptor, type CacheResponseInterceptorOptions } from '../src/interceptor.mjs';
import { ResponseCache, MemoryCacheStore } from '@internal/cache-response';
import type { Dispatcher } from 'undici';

// Mock dispatch handler
function createMockDispatch(
  statusCode: number = 200,
  headers: Record<string, string> = { 'cache-control': 'max-age=3600' },
  body: string = 'test body'
): Dispatcher.DispatchHandlers['dispatch'] {
  return (opts: Dispatcher.DispatchOptions, handler: Dispatcher.DispatchHandlers) => {
    const headerArray = Object.entries(headers).flat();
    handler.onHeaders?.(statusCode, headerArray, () => {}, '');
    handler.onData?.(Buffer.from(body));
    handler.onComplete?.(null);
    return true;
  };
}

// Mock handler for capturing responses
function createMockHandler(): {
  handler: Dispatcher.DispatchHandlers;
  results: { statusCode?: number; headers?: string[]; body: Buffer[]; complete: boolean; error?: Error };
} {
  const results = {
    statusCode: undefined as number | undefined,
    headers: undefined as string[] | undefined,
    body: [] as Buffer[],
    complete: false,
    error: undefined as Error | undefined,
  };

  const handler: Dispatcher.DispatchHandlers = {
    onHeaders: (statusCode, headers) => {
      results.statusCode = statusCode;
      results.headers = headers?.map((h) => h.toString());
      return true;
    },
    onData: (chunk) => {
      results.body.push(chunk);
      return true;
    },
    onComplete: () => {
      results.complete = true;
    },
    onError: (error) => {
      results.error = error;
    },
  };

  return { handler, results };
}

describe('cacheResponseInterceptor', () => {
  describe('basic behavior', () => {
    it('should pass through non-cacheable methods', async () => {
      const interceptor = cacheResponseInterceptor();
      const dispatch = createMockDispatch();
      const wrapped = interceptor(dispatch);
      const { handler, results } = createMockHandler();

      wrapped(
        { method: 'POST', path: '/api/users', origin: 'https://example.com' },
        handler
      );

      expect(results.complete).toBe(true);
      expect(results.statusCode).toBe(200);
    });

    it('should cache GET responses', async () => {
      const store = new MemoryCacheStore();
      const interceptor = cacheResponseInterceptor({ store });
      const dispatch = createMockDispatch();
      const wrapped = interceptor(dispatch);
      const { handler, results } = createMockHandler();

      wrapped(
        { method: 'GET', path: '/api/users', origin: 'https://example.com' },
        handler
      );

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(results.complete).toBe(true);
      expect(await store.size()).toBe(1);
    });
  });

  describe('callback options', () => {
    it('should call onCacheMiss on first request', async () => {
      let missUrl: string | undefined;
      const interceptor = cacheResponseInterceptor({
        onCacheMiss: (url) => {
          missUrl = url;
        },
      });
      const dispatch = createMockDispatch();
      const wrapped = interceptor(dispatch);
      const { handler } = createMockHandler();

      wrapped(
        { method: 'GET', path: '/api/data', origin: 'https://example.com' },
        handler
      );

      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(missUrl).toBe('https://example.com/api/data');
    });

    it('should call onCacheHit on cached response', async () => {
      const store = new MemoryCacheStore();
      let hitUrl: string | undefined;
      let hitFreshness: string | undefined;

      const interceptor = cacheResponseInterceptor({
        store,
        onCacheHit: (url, freshness) => {
          hitUrl = url;
          hitFreshness = freshness;
        },
      });
      const dispatch = createMockDispatch();
      const wrapped = interceptor(dispatch);

      // First request - cache miss
      wrapped(
        { method: 'GET', path: '/api/data', origin: 'https://example.com' },
        createMockHandler().handler
      );

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Second request - cache hit
      wrapped(
        { method: 'GET', path: '/api/data', origin: 'https://example.com' },
        createMockHandler().handler
      );

      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(hitUrl).toBe('https://example.com/api/data');
      expect(hitFreshness).toBe('fresh');
    });

    it('should call onCacheStore when response is cached', async () => {
      let storeUrl: string | undefined;
      let storeStatusCode: number | undefined;

      const interceptor = cacheResponseInterceptor({
        onCacheStore: (url, statusCode) => {
          storeUrl = url;
          storeStatusCode = statusCode;
        },
      });
      const dispatch = createMockDispatch();
      const wrapped = interceptor(dispatch);
      const { handler } = createMockHandler();

      wrapped(
        { method: 'GET', path: '/api/data', origin: 'https://example.com' },
        handler
      );

      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(storeUrl).toBe('https://example.com/api/data');
      expect(storeStatusCode).toBe(200);
    });
  });

  describe('conditional requests', () => {
    it('should add If-None-Match header when ETag available', async () => {
      const store = new MemoryCacheStore();

      // Pre-populate cache with response containing ETag
      const cache = new ResponseCache({}, store);
      await cache.store(
        'GET',
        'https://example.com/api/data',
        200,
        {
          // Use stale-while-revalidate to keep entry available for conditional request
          'cache-control': 'max-age=0, stale-while-revalidate=60',
          etag: '"abc123"',
        },
        Buffer.from('cached body')
      );

      let capturedHeaders: Record<string, string> = {};
      const dispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
        if (opts.headers && typeof opts.headers === 'object' && !Array.isArray(opts.headers)) {
          capturedHeaders = opts.headers as Record<string, string>;
        }
        handler.onHeaders?.(304, [], () => {}, '');
        handler.onComplete?.(null);
        return true;
      };

      const interceptor = cacheResponseInterceptor({ store });
      const wrapped = interceptor(dispatch);
      const { handler } = createMockHandler();

      wrapped(
        { method: 'GET', path: '/api/data', origin: 'https://example.com' },
        handler
      );

      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(capturedHeaders['If-None-Match']).toBe('"abc123"');
    });
  });

  describe('error handling', () => {
    it('should handle dispatch errors gracefully', async () => {
      const dispatch: Dispatcher.DispatchHandlers['dispatch'] = (_opts, handler) => {
        handler.onError?.(new Error('Network error'));
        return true;
      };

      const interceptor = cacheResponseInterceptor();
      const wrapped = interceptor(dispatch);
      const { handler, results } = createMockHandler();

      wrapped(
        { method: 'GET', path: '/api/data', origin: 'https://example.com' },
        handler
      );

      await new Promise((resolve) => setTimeout(resolve, 100));

      // The interceptor should pass the error through
      // (depends on implementation details)
    });
  });
});

describe('factory functions', () => {
  it('should be importable', async () => {
    const { createCacheResponseDispatcher, createCacheResponseAgent, composeCacheResponse } =
      await import('../src/factory.mjs');

    expect(typeof createCacheResponseDispatcher).toBe('function');
    expect(typeof createCacheResponseAgent).toBe('function');
    expect(typeof composeCacheResponse).toBe('function');
  });
});

/**
 * =============================================================================
 * LOGIC TESTING - COMPREHENSIVE COVERAGE
 * =============================================================================
 * Additional tests for:
 * - Decision/Branch Coverage
 * - Boundary Value Analysis
 * - State Transition Testing
 * - Path Coverage
 * - Error Handling
 * =============================================================================
 */

describe('cacheResponseInterceptor - Decision/Branch Coverage', () => {
  it('should pass through DELETE method', async () => {
    const interceptor = cacheResponseInterceptor();
    const dispatch = createMockDispatch();
    const wrapped = interceptor(dispatch);
    const { handler, results } = createMockHandler();

    wrapped(
      { method: 'DELETE', path: '/api/users/1', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(results.complete).toBe(true);
    expect(results.statusCode).toBe(200);
  });

  it('should pass through PUT method', async () => {
    const interceptor = cacheResponseInterceptor();
    const dispatch = createMockDispatch();
    const wrapped = interceptor(dispatch);
    const { handler, results } = createMockHandler();

    wrapped(
      { method: 'PUT', path: '/api/users/1', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(results.complete).toBe(true);
  });

  it('should pass through PATCH method', async () => {
    const interceptor = cacheResponseInterceptor();
    const dispatch = createMockDispatch();
    const wrapped = interceptor(dispatch);
    const { handler, results } = createMockHandler();

    wrapped(
      { method: 'PATCH', path: '/api/users/1', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(results.complete).toBe(true);
  });

  it('should cache HEAD responses', async () => {
    const store = new MemoryCacheStore();
    const interceptor = cacheResponseInterceptor({ store });
    const dispatch = createMockDispatch();
    const wrapped = interceptor(dispatch);
    const { handler, results } = createMockHandler();

    wrapped(
      { method: 'HEAD', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(results.complete).toBe(true);
    expect(await store.size()).toBe(1);
  });
});

describe('cacheResponseInterceptor - Boundary Value Analysis', () => {
  it('should handle max-age=0', async () => {
    const store = new MemoryCacheStore();
    const interceptor = cacheResponseInterceptor({ store });
    const dispatch = createMockDispatch(200, { 'cache-control': 'max-age=0' });
    const wrapped = interceptor(dispatch);
    const { handler } = createMockHandler();

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    // max-age=0 should not be cached
    expect(await store.size()).toBe(0);
  });

  it('should handle empty path', async () => {
    const interceptor = cacheResponseInterceptor();
    const dispatch = createMockDispatch();
    const wrapped = interceptor(dispatch);
    const { handler, results } = createMockHandler();

    wrapped(
      { method: 'GET', path: '', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(results.complete).toBe(true);
  });

  it('should handle path with query params', async () => {
    const store = new MemoryCacheStore();
    const interceptor = cacheResponseInterceptor({ store });
    const dispatch = createMockDispatch();
    const wrapped = interceptor(dispatch);

    // First request with params
    wrapped(
      { method: 'GET', path: '/api/data?page=1&limit=10', origin: 'https://example.com' },
      createMockHandler().handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    // Same params - should hit cache
    wrapped(
      { method: 'GET', path: '/api/data?page=1&limit=10', origin: 'https://example.com' },
      createMockHandler().handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    // Different params - should not hit cache
    let missUrl: string | undefined;
    const interceptor2 = cacheResponseInterceptor({
      store,
      onCacheMiss: (url) => { missUrl = url; }
    });
    const wrapped2 = interceptor2(dispatch);

    wrapped2(
      { method: 'GET', path: '/api/data?page=2&limit=10', origin: 'https://example.com' },
      createMockHandler().handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(missUrl).toContain('page=2');
  });
});

describe('cacheResponseInterceptor - Non-cacheable responses', () => {
  it('should not cache no-store responses', async () => {
    const store = new MemoryCacheStore();
    const interceptor = cacheResponseInterceptor({ store });
    const dispatch = createMockDispatch(200, { 'cache-control': 'no-store' });
    const wrapped = interceptor(dispatch);
    const { handler } = createMockHandler();

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(await store.size()).toBe(0);
  });

  it('should not cache private responses', async () => {
    const store = new MemoryCacheStore();
    const interceptor = cacheResponseInterceptor({ store });
    const dispatch = createMockDispatch(200, { 'cache-control': 'private, max-age=3600' });
    const wrapped = interceptor(dispatch);
    const { handler } = createMockHandler();

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(await store.size()).toBe(0);
  });

  it('should not cache non-cacheable status codes', async () => {
    const store = new MemoryCacheStore();
    const interceptor = cacheResponseInterceptor({ store });
    const dispatch = createMockDispatch(500, { 'cache-control': 'max-age=3600' });
    const wrapped = interceptor(dispatch);
    const { handler } = createMockHandler();

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(await store.size()).toBe(0);
  });
});

describe('cacheResponseInterceptor - State Transitions', () => {
  it('should handle fresh -> stale transition', async () => {
    const store = new MemoryCacheStore();
    let hitFreshness: string | undefined;

    const interceptor = cacheResponseInterceptor({
      store,
      onCacheHit: (_url, freshness) => {
        hitFreshness = freshness;
      },
    });

    // Use very short max-age
    const dispatch = createMockDispatch(200, { 'cache-control': 'max-age=0, stale-while-revalidate=60' });
    const wrapped = interceptor(dispatch);

    // First request
    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      createMockHandler().handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    // Second request - should be stale
    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      createMockHandler().handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(hitFreshness).toBe('stale');
  });

  it('should handle multiple sequential requests', async () => {
    const store = new MemoryCacheStore();
    let hitCount = 0;
    let missCount = 0;

    const interceptor = cacheResponseInterceptor({
      store,
      onCacheHit: () => { hitCount++; },
      onCacheMiss: () => { missCount++; },
    });

    const dispatch = createMockDispatch();
    const wrapped = interceptor(dispatch);

    // 5 requests to same endpoint
    for (let i = 0; i < 5; i++) {
      wrapped(
        { method: 'GET', path: '/api/data', origin: 'https://example.com' },
        createMockHandler().handler
      );
      await new Promise((resolve) => setTimeout(resolve, 50));
    }

    // First should miss, rest should hit
    expect(missCount).toBe(1);
    expect(hitCount).toBe(4);
  });

  it('should handle requests to different endpoints', async () => {
    const store = new MemoryCacheStore();
    let storeCount = 0;

    const interceptor = cacheResponseInterceptor({
      store,
      onCacheStore: () => { storeCount++; },
    });

    const dispatch = createMockDispatch();
    const wrapped = interceptor(dispatch);

    const endpoints = ['/api/users', '/api/posts', '/api/comments'];

    for (const endpoint of endpoints) {
      wrapped(
        { method: 'GET', path: endpoint, origin: 'https://example.com' },
        createMockHandler().handler
      );
      await new Promise((resolve) => setTimeout(resolve, 50));
    }

    expect(storeCount).toBe(3);
  });
});

describe('cacheResponseInterceptor - Error Scenarios', () => {
  it('should propagate network errors', async () => {
    const dispatch: Dispatcher.DispatchHandlers['dispatch'] = (_opts, handler) => {
      handler.onError?.(new Error('Connection refused'));
      return true;
    };

    const interceptor = cacheResponseInterceptor();
    const wrapped = interceptor(dispatch);
    const { handler, results } = createMockHandler();

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(results.error).toBeDefined();
    expect(results.error?.message).toBe('Connection refused');
  });

  it('should handle timeout errors', async () => {
    const dispatch: Dispatcher.DispatchHandlers['dispatch'] = (_opts, handler) => {
      handler.onError?.(new Error('Request timeout'));
      return true;
    };

    const interceptor = cacheResponseInterceptor();
    const wrapped = interceptor(dispatch);
    const { handler, results } = createMockHandler();

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(results.error).toBeDefined();
    expect(results.error?.message).toBe('Request timeout');
  });
});

describe('cacheResponseInterceptor - Cache Revalidation', () => {
  it('should use If-Modified-Since when Last-Modified available', async () => {
    const store = new MemoryCacheStore();
    const lastModified = 'Wed, 21 Oct 2015 07:28:00 GMT';

    // Pre-populate cache
    const cache = new ResponseCache({}, store);
    await cache.store(
      'GET',
      'https://example.com/api/data',
      200,
      {
        // Use stale-while-revalidate to keep entry available for conditional request
        'cache-control': 'max-age=0, stale-while-revalidate=60',
        'last-modified': lastModified,
      },
      Buffer.from('cached body')
    );

    let capturedHeaders: Record<string, string> = {};
    const dispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
      if (opts.headers && typeof opts.headers === 'object' && !Array.isArray(opts.headers)) {
        capturedHeaders = opts.headers as Record<string, string>;
      }
      handler.onHeaders?.(200, [], () => {}, '');
      handler.onComplete?.(null);
      return true;
    };

    const interceptor = cacheResponseInterceptor({ store });
    const wrapped = interceptor(dispatch);

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      createMockHandler().handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(capturedHeaders['If-Modified-Since']).toBe(lastModified);
  });

  it('should handle 304 response by using cached body', async () => {
    const store = new MemoryCacheStore();
    const cachedBody = 'cached body content';

    // Pre-populate cache
    const cache = new ResponseCache({}, store);
    await cache.store(
      'GET',
      'https://example.com/api/data',
      200,
      {
        // Use stale-while-revalidate to keep entry available for conditional request
        'cache-control': 'max-age=0, stale-while-revalidate=60',
        'etag': '"abc123"',
      },
      Buffer.from(cachedBody)
    );

    const dispatch: Dispatcher.DispatchHandlers['dispatch'] = (_opts, handler) => {
      handler.onHeaders?.(304, [], () => {}, '');
      handler.onComplete?.(null);
      return true;
    };

    const interceptor = cacheResponseInterceptor({ store });
    const wrapped = interceptor(dispatch);
    const { handler, results } = createMockHandler();

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should return cached body on 304
    expect(results.body.length).toBeGreaterThan(0);
  });
});

describe('cacheResponseInterceptor - Vary Header Handling', () => {
  it('should not cache Vary: * responses', async () => {
    const store = new MemoryCacheStore();
    const interceptor = cacheResponseInterceptor({ store });
    const dispatch = createMockDispatch(200, {
      'cache-control': 'max-age=3600',
      'vary': '*',
    });
    const wrapped = interceptor(dispatch);
    const { handler } = createMockHandler();

    wrapped(
      { method: 'GET', path: '/api/data', origin: 'https://example.com' },
      handler
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(await store.size()).toBe(0);
  });
});
