/**
 * Tests for cache stores
 */

import { MemoryCacheStore, createMemoryCacheStore } from '../src/stores/memory.mjs';
import type { CachedResponse } from '../src/types.mjs';

describe('MemoryCacheStore', () => {
  let store: MemoryCacheStore;

  const createResponse = (key: string, expiresInMs: number = 60000): CachedResponse => ({
    metadata: {
      url: `https://example.com/${key}`,
      method: 'GET',
      statusCode: 200,
      headers: { 'content-type': 'application/json' },
      cachedAt: Date.now(),
      expiresAt: Date.now() + expiresInMs,
    },
    body: JSON.stringify({ key }),
  });

  beforeEach(() => {
    store = new MemoryCacheStore({
      maxSize: 1024 * 1024, // 1MB
      maxEntries: 100,
      maxEntrySize: 100 * 1024, // 100KB
      cleanupIntervalMs: 1000,
    });
  });

  afterEach(async () => {
    await store.close();
  });

  describe('get/set', () => {
    it('should store and retrieve a response', async () => {
      const response = createResponse('test');
      await store.set('key1', response);

      const retrieved = await store.get('key1');
      expect(retrieved).not.toBeNull();
      expect(retrieved?.metadata.url).toBe('https://example.com/test');
      expect(retrieved?.body).toBe(JSON.stringify({ key: 'test' }));
    });

    it('should return null for non-existent key', async () => {
      const result = await store.get('non-existent');
      expect(result).toBeNull();
    });

    it('should overwrite existing key', async () => {
      await store.set('key1', createResponse('first'));
      await store.set('key1', createResponse('second'));

      const retrieved = await store.get('key1');
      expect(retrieved?.body).toBe(JSON.stringify({ key: 'second' }));
    });
  });

  describe('has', () => {
    it('should return true for existing key', async () => {
      await store.set('key1', createResponse('test'));
      expect(await store.has('key1')).toBe(true);
    });

    it('should return false for non-existent key', async () => {
      expect(await store.has('non-existent')).toBe(false);
    });
  });

  describe('delete', () => {
    it('should delete existing key', async () => {
      await store.set('key1', createResponse('test'));
      expect(await store.delete('key1')).toBe(true);
      expect(await store.has('key1')).toBe(false);
    });

    it('should return false for non-existent key', async () => {
      expect(await store.delete('non-existent')).toBe(false);
    });
  });

  describe('clear', () => {
    it('should remove all entries', async () => {
      await store.set('key1', createResponse('test1'));
      await store.set('key2', createResponse('test2'));
      await store.set('key3', createResponse('test3'));

      await store.clear();

      expect(await store.size()).toBe(0);
    });
  });

  describe('size', () => {
    it('should return correct count', async () => {
      expect(await store.size()).toBe(0);

      await store.set('key1', createResponse('test1'));
      expect(await store.size()).toBe(1);

      await store.set('key2', createResponse('test2'));
      expect(await store.size()).toBe(2);

      await store.delete('key1');
      expect(await store.size()).toBe(1);
    });
  });

  describe('keys', () => {
    it('should return all keys', async () => {
      await store.set('key1', createResponse('test1'));
      await store.set('key2', createResponse('test2'));
      await store.set('key3', createResponse('test3'));

      const keys = await store.keys();
      expect(keys).toHaveLength(3);
      expect(keys).toContain('key1');
      expect(keys).toContain('key2');
      expect(keys).toContain('key3');
    });
  });

  describe('expiration', () => {
    it('should return null for expired entries', async () => {
      const response = createResponse('test', -1000); // Already expired
      await store.set('expired', response);

      const result = await store.get('expired');
      expect(result).toBeNull();
    });

    it('should remove expired entries on has()', async () => {
      const response = createResponse('test', -1000);
      await store.set('expired', response);

      expect(await store.has('expired')).toBe(false);
    });

    it('should clean up expired entries', async () => {
      // Create store with fast cleanup
      const fastStore = new MemoryCacheStore({
        cleanupIntervalMs: 100,
      });

      const response = createResponse('test', 50); // Expires in 50ms
      await fastStore.set('key1', response);

      expect(await fastStore.has('key1')).toBe(true);

      // Wait for expiration and cleanup
      await new Promise((resolve) => setTimeout(resolve, 200));

      expect(await fastStore.size()).toBe(0);

      await fastStore.close();
    });
  });

  describe('LRU eviction', () => {
    it('should evict oldest entries when max entries exceeded', async () => {
      const smallStore = new MemoryCacheStore({
        maxEntries: 3,
      });

      await smallStore.set('key1', createResponse('test1'));
      await smallStore.set('key2', createResponse('test2'));
      await smallStore.set('key3', createResponse('test3'));
      await smallStore.set('key4', createResponse('test4'));

      expect(await smallStore.size()).toBe(3);
      expect(await smallStore.has('key1')).toBe(false); // Evicted
      expect(await smallStore.has('key4')).toBe(true); // Most recent

      await smallStore.close();
    });

    it('should evict entries when max size exceeded', async () => {
      const smallStore = new MemoryCacheStore({
        maxSize: 200, // Very small
        maxEntrySize: 100,
      });

      await smallStore.set('key1', createResponse('test1'));
      await smallStore.set('key2', createResponse('test2'));
      await smallStore.set('key3', createResponse('test3'));

      // Should have evicted some entries to stay under limit
      const size = await smallStore.size();
      expect(size).toBeLessThan(3);

      await smallStore.close();
    });

    it('should not store entries exceeding max entry size', async () => {
      const smallStore = new MemoryCacheStore({
        maxEntrySize: 10, // Very small
      });

      // This response is larger than 10 bytes
      await smallStore.set('key1', createResponse('test'));

      expect(await smallStore.size()).toBe(0);

      await smallStore.close();
    });

    it('should move accessed entries to end of LRU queue', async () => {
      const smallStore = new MemoryCacheStore({
        maxEntries: 3,
      });

      await smallStore.set('key1', createResponse('test1'));
      await smallStore.set('key2', createResponse('test2'));
      await smallStore.set('key3', createResponse('test3'));

      // Access key1 to move it to end
      await smallStore.get('key1');

      // Add new entry, should evict key2 (now oldest)
      await smallStore.set('key4', createResponse('test4'));

      expect(await smallStore.has('key1')).toBe(true); // Still there (recently accessed)
      expect(await smallStore.has('key2')).toBe(false); // Evicted

      await smallStore.close();
    });
  });

  describe('getStats', () => {
    it('should return cache statistics', async () => {
      await store.set('key1', createResponse('test1'));
      await store.set('key2', createResponse('test2'));

      const stats = store.getStats();
      expect(stats.entries).toBe(2);
      expect(stats.sizeBytes).toBeGreaterThan(0);
      expect(stats.maxSizeBytes).toBe(1024 * 1024);
      expect(stats.maxEntries).toBe(100);
      expect(stats.utilizationPercent).toBeGreaterThan(0);
    });
  });
});

describe('createMemoryCacheStore', () => {
  it('should create store with default options', () => {
    const store = createMemoryCacheStore();
    expect(store).toBeInstanceOf(MemoryCacheStore);
  });

  it('should create store with custom options', () => {
    const store = createMemoryCacheStore({
      maxSize: 50 * 1024 * 1024,
      maxEntries: 500,
    });
    const stats = store.getStats();
    expect(stats.maxSizeBytes).toBe(50 * 1024 * 1024);
    expect(stats.maxEntries).toBe(500);
  });
});
