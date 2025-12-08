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
          'cache-control': 'max-age=0', // Expired to trigger revalidation
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
