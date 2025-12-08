/**
 * Tests for ResponseCache
 */

import { ResponseCache, createResponseCache } from '../src/cache.mjs';
import { MemoryCacheStore } from '../src/stores/memory.mjs';
import type { CacheResponseEvent } from '../src/types.mjs';

describe('ResponseCache', () => {
  let cache: ResponseCache;

  beforeEach(() => {
    cache = new ResponseCache({
      defaultTtlMs: 300000, // 5 minutes
      maxTtlMs: 3600000, // 1 hour
    });
  });

  afterEach(async () => {
    await cache.close();
  });

  describe('isCacheable', () => {
    it('should return true for GET and HEAD', () => {
      expect(cache.isCacheable('GET')).toBe(true);
      expect(cache.isCacheable('HEAD')).toBe(true);
    });

    it('should return false for POST, PUT, DELETE', () => {
      expect(cache.isCacheable('POST')).toBe(false);
      expect(cache.isCacheable('PUT')).toBe(false);
      expect(cache.isCacheable('DELETE')).toBe(false);
    });
  });

  describe('generateKey', () => {
    it('should generate key for simple URL', () => {
      const key = cache.generateKey('GET', 'https://example.com/api/users');
      expect(key).toBe('GET:https://example.com/api/users');
    });

    it('should include query string by default', () => {
      const key = cache.generateKey('GET', 'https://example.com/api/users?page=1');
      expect(key).toContain('page=1');
    });

    it('should generate different keys for different methods', () => {
      const getKey = cache.generateKey('GET', 'https://example.com/api');
      const headKey = cache.generateKey('HEAD', 'https://example.com/api');
      expect(getKey).not.toBe(headKey);
    });
  });

  describe('store and lookup', () => {
    const url = 'https://example.com/api/users';
    const headers = {
      'content-type': 'application/json',
      'cache-control': 'max-age=3600',
    };
    const body = JSON.stringify({ users: [] });

    it('should store and retrieve a response', async () => {
      const stored = await cache.store('GET', url, 200, headers, body);
      expect(stored).toBe(true);

      const lookup = await cache.lookup('GET', url);
      expect(lookup.found).toBe(true);
      expect(lookup.freshness).toBe('fresh');
      expect(lookup.response?.body).toBe(body);
      expect(lookup.response?.metadata.statusCode).toBe(200);
    });

    it('should return not found for non-existent key', async () => {
      const lookup = await cache.lookup('GET', 'https://example.com/not-cached');
      expect(lookup.found).toBe(false);
    });

    it('should not store non-cacheable methods', async () => {
      const stored = await cache.store('POST', url, 200, headers, body);
      expect(stored).toBe(false);
    });

    it('should not store non-cacheable status codes', async () => {
      const stored = await cache.store('GET', url, 500, headers, body);
      expect(stored).toBe(false);
    });

    it('should not store no-store responses', async () => {
      const stored = await cache.store(
        'GET',
        url,
        200,
        { 'cache-control': 'no-store' },
        body
      );
      expect(stored).toBe(false);
    });

    it('should not store private responses by default', async () => {
      const stored = await cache.store(
        'GET',
        url,
        200,
        { 'cache-control': 'private, max-age=3600' },
        body
      );
      expect(stored).toBe(false);
    });
  });

  describe('conditional requests', () => {
    const url = 'https://example.com/api/users';

    it('should return etag for conditional request', async () => {
      const headers = {
        'cache-control': 'max-age=3600',
        etag: '"abc123"',
      };
      await cache.store('GET', url, 200, headers, 'body');

      const lookup = await cache.lookup('GET', url);
      expect(lookup.etag).toBe('"abc123"');
    });

    it('should return last-modified for conditional request', async () => {
      const lastModified = 'Wed, 21 Oct 2015 07:28:00 GMT';
      const headers = {
        'cache-control': 'max-age=3600',
        'last-modified': lastModified,
      };
      await cache.store('GET', url, 200, headers, 'body');

      const lookup = await cache.lookup('GET', url);
      expect(lookup.lastModified).toBe(lastModified);
    });
  });

  describe('revalidation', () => {
    const url = 'https://example.com/api/users';

    it('should update expiration on revalidation', async () => {
      // Store initial response
      const headers = { 'cache-control': 'max-age=1' }; // 1 second
      await cache.store('GET', url, 200, headers, 'body');

      // Wait for it to become stale
      await new Promise((resolve) => setTimeout(resolve, 1100));

      let lookup = await cache.lookup('GET', url);
      expect(lookup.freshness).not.toBe('fresh');

      // Revalidate
      const newHeaders = { 'cache-control': 'max-age=3600' };
      await cache.revalidate('GET', url, newHeaders);

      lookup = await cache.lookup('GET', url);
      expect(lookup.freshness).toBe('fresh');
    });
  });

  describe('invalidation', () => {
    const url = 'https://example.com/api/users';

    it('should invalidate cached response', async () => {
      await cache.store('GET', url, 200, { 'cache-control': 'max-age=3600' }, 'body');

      let lookup = await cache.lookup('GET', url);
      expect(lookup.found).toBe(true);

      const invalidated = await cache.invalidate('GET', url);
      expect(invalidated).toBe(true);

      lookup = await cache.lookup('GET', url);
      expect(lookup.found).toBe(false);
    });
  });

  describe('events', () => {
    it('should emit cache:hit event', async () => {
      const events: CacheResponseEvent[] = [];
      cache.on((event) => events.push(event));

      const url = 'https://example.com/api/users';
      await cache.store('GET', url, 200, { 'cache-control': 'max-age=3600' }, 'body');
      await cache.lookup('GET', url);

      const hitEvent = events.find((e) => e.type === 'cache:hit');
      expect(hitEvent).toBeDefined();
      expect(hitEvent?.url).toBe(url);
    });

    it('should emit cache:miss event', async () => {
      const events: CacheResponseEvent[] = [];
      cache.on((event) => events.push(event));

      await cache.lookup('GET', 'https://example.com/not-cached');

      const missEvent = events.find((e) => e.type === 'cache:miss');
      expect(missEvent).toBeDefined();
    });

    it('should emit cache:store event', async () => {
      const events: CacheResponseEvent[] = [];
      cache.on((event) => events.push(event));

      await cache.store(
        'GET',
        'https://example.com/api',
        200,
        { 'cache-control': 'max-age=3600' },
        'body'
      );

      const storeEvent = events.find((e) => e.type === 'cache:store');
      expect(storeEvent).toBeDefined();
    });

    it('should allow removing event listeners', async () => {
      const events: CacheResponseEvent[] = [];
      const listener = (event: CacheResponseEvent) => events.push(event);
      const unsubscribe = cache.on(listener);

      await cache.lookup('GET', 'https://example.com/test1');
      expect(events.length).toBeGreaterThan(0);

      const countBefore = events.length;
      unsubscribe();

      await cache.lookup('GET', 'https://example.com/test2');
      expect(events.length).toBe(countBefore);
    });
  });

  describe('Vary header handling', () => {
    const url = 'https://example.com/api/data';

    it('should not cache with Vary: *', async () => {
      const headers = {
        'cache-control': 'max-age=3600',
        vary: '*',
      };
      const stored = await cache.store('GET', url, 200, headers, 'body');
      expect(stored).toBe(false);
    });

    it('should match vary headers', async () => {
      const responseHeaders = {
        'cache-control': 'max-age=3600',
        vary: 'Accept',
      };
      const requestHeaders = { Accept: 'application/json' };

      await cache.store('GET', url, 200, responseHeaders, 'json body', requestHeaders);

      // Same accept header should hit cache
      let lookup = await cache.lookup('GET', url, { Accept: 'application/json' });
      expect(lookup.found).toBe(true);
    });
  });

  describe('stale-while-revalidate', () => {
    it('should trigger background revalidation for stale responses', async () => {
      const url = 'https://example.com/api/data';
      let revalidateCalled = false;

      const staleCache = new ResponseCache({
        staleWhileRevalidate: true,
      });

      staleCache.setBackgroundRevalidator(async () => {
        revalidateCalled = true;
      });

      // Store with very short TTL
      await staleCache.store(
        'GET',
        url,
        200,
        { 'cache-control': 'max-age=0, stale-while-revalidate=60' },
        'body'
      );

      // Wait a bit for it to become stale
      await new Promise((resolve) => setTimeout(resolve, 50));

      const lookup = await staleCache.lookup('GET', url);
      expect(lookup.found).toBe(true);
      expect(lookup.freshness).toBe('stale');

      // Wait for background revalidation
      await new Promise((resolve) => setTimeout(resolve, 100));
      expect(revalidateCalled).toBe(true);

      await staleCache.close();
    });
  });
});

describe('createResponseCache', () => {
  it('should create cache with default config', () => {
    const cache = createResponseCache();
    expect(cache).toBeInstanceOf(ResponseCache);
  });

  it('should create cache with custom config', () => {
    const cache = createResponseCache({ defaultTtlMs: 60000 });
    expect(cache.getConfig().defaultTtlMs).toBe(60000);
  });

  it('should create cache with custom store', () => {
    const store = new MemoryCacheStore({ maxEntries: 10 });
    const cache = createResponseCache({}, store);
    expect(cache).toBeInstanceOf(ResponseCache);
  });
});
