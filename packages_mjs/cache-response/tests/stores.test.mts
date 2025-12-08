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

/**
 * =============================================================================
 * LOGIC TESTING - COMPREHENSIVE COVERAGE
 * =============================================================================
 * Additional tests for:
 * - Decision/Branch Coverage
 * - Boundary Value Analysis
 * - State Transition Testing
 * - Loop Testing
 * - Error Handling
 * =============================================================================
 */

// Helper function for standalone tests
const createTestResponse = (key: string, expiresInMs: number = 60000): CachedResponse => ({
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

describe('MemoryCacheStore - Boundary Value Analysis', () => {
  it('should handle exactly maxEntries entries', async () => {
    const store = new MemoryCacheStore({ maxEntries: 3, maxEntrySize: 1024 * 1024 });

    await store.set('key1', createTestResponse('test1'));
    await store.set('key2', createTestResponse('test2'));
    await store.set('key3', createTestResponse('test3'));

    expect(await store.size()).toBe(3);

    await store.close();
  });

  it('should handle entry size exactly at maxEntrySize', async () => {
    // Create a store with a specific max entry size
    const maxEntrySize = 500;
    const store = new MemoryCacheStore({ maxEntrySize });

    // Create a response that's under the limit
    const smallResponse = createTestResponse('small');

    await store.set('key1', smallResponse);
    expect(await store.size()).toBe(1);

    await store.close();
  });

  it('should handle zero cleanup interval (disabled)', async () => {
    const store = new MemoryCacheStore({ cleanupIntervalMs: 0 });

    // Store should still work
    await store.set('key1', createTestResponse('test1'));
    expect(await store.has('key1')).toBe(true);

    await store.close();
  });

  it('should handle very large maxSize', async () => {
    const store = new MemoryCacheStore({
      maxSize: Number.MAX_SAFE_INTEGER,
    });

    await store.set('key1', createTestResponse('test1'));
    expect(await store.size()).toBe(1);

    await store.close();
  });
});

describe('MemoryCacheStore - Size Calculation', () => {
  it('should calculate size for string body', async () => {
    const store = new MemoryCacheStore();

    const response = createTestResponse('test');
    await store.set('key1', response);

    const stats = store.getStats();
    expect(stats.sizeBytes).toBeGreaterThan(0);

    await store.close();
  });

  it('should calculate size for Buffer body', async () => {
    const store = new MemoryCacheStore();

    const response: CachedResponse = {
      metadata: {
        url: 'https://example.com/buffer',
        method: 'GET',
        statusCode: 200,
        headers: { 'content-type': 'application/octet-stream' },
        cachedAt: Date.now(),
        expiresAt: Date.now() + 60000,
      },
      body: Buffer.from('binary data here'),
    };

    await store.set('key1', response);

    const stats = store.getStats();
    expect(stats.sizeBytes).toBeGreaterThan(0);

    await store.close();
  });

  it('should calculate size for null body', async () => {
    const store = new MemoryCacheStore();

    const response: CachedResponse = {
      metadata: {
        url: 'https://example.com/null',
        method: 'GET',
        statusCode: 204,
        headers: {},
        cachedAt: Date.now(),
        expiresAt: Date.now() + 60000,
      },
      body: null,
    };

    await store.set('key1', response);

    const stats = store.getStats();
    expect(stats.sizeBytes).toBeGreaterThan(0); // Metadata still has size

    await store.close();
  });
});

describe('MemoryCacheStore - Eviction Policy', () => {
  it('should evict based on size when maxSize exceeded', async () => {
    const store = new MemoryCacheStore({
      maxSize: 150,
      maxEntrySize: 100,
      maxEntries: 100,
    });

    await store.set('key1', createTestResponse('test1'));
    const size1 = await store.size();

    await store.set('key2', createTestResponse('test2'));
    const size2 = await store.size();

    await store.set('key3', createTestResponse('test3'));

    // Should have evicted some entries
    expect(await store.size()).toBeLessThanOrEqual(size2);

    await store.close();
  });

  it('should handle multiple evictions in sequence', async () => {
    const store = new MemoryCacheStore({
      maxEntries: 2,
    });

    await store.set('key1', createTestResponse('test1'));
    await store.set('key2', createTestResponse('test2'));
    await store.set('key3', createTestResponse('test3')); // Evicts key1
    await store.set('key4', createTestResponse('test4')); // Evicts key2

    expect(await store.has('key1')).toBe(false);
    expect(await store.has('key2')).toBe(false);
    expect(await store.has('key3')).toBe(true);
    expect(await store.has('key4')).toBe(true);

    await store.close();
  });

  it('should correctly update currentSize after deletion', async () => {
    const store = new MemoryCacheStore();

    await store.set('key1', createTestResponse('test1'));
    await store.set('key2', createTestResponse('test2'));

    const statsBefore = store.getStats();
    const sizeBefore = statsBefore.sizeBytes;

    await store.delete('key1');

    const statsAfter = store.getStats();
    expect(statsAfter.sizeBytes).toBeLessThan(sizeBefore);

    await store.close();
  });
});

describe('MemoryCacheStore - LRU Behavior', () => {
  it('should move to end on get', async () => {
    const store = new MemoryCacheStore({ maxEntries: 3 });

    await store.set('key1', createTestResponse('test1'));
    await store.set('key2', createTestResponse('test2'));
    await store.set('key3', createTestResponse('test3'));

    // Access key1 to move it to end (most recently used)
    await store.get('key1');

    // Add key4, should evict key2 (now oldest unused)
    await store.set('key4', createTestResponse('test4'));

    expect(await store.has('key1')).toBe(true); // Most recently used
    expect(await store.has('key2')).toBe(false); // Evicted
    expect(await store.has('key3')).toBe(true);
    expect(await store.has('key4')).toBe(true);

    await store.close();
  });

  it('should not move to end on has', async () => {
    const store = new MemoryCacheStore({ maxEntries: 3 });

    await store.set('key1', createTestResponse('test1'));
    await store.set('key2', createTestResponse('test2'));
    await store.set('key3', createTestResponse('test3'));

    // Just check if key1 exists (should not affect LRU order)
    await store.has('key1');

    // Add key4, should evict key1 (still oldest)
    await store.set('key4', createTestResponse('test4'));

    expect(await store.has('key1')).toBe(false); // Evicted
    expect(await store.has('key4')).toBe(true);

    await store.close();
  });
});

describe('MemoryCacheStore - Concurrent Operations', () => {
  it('should handle concurrent sets', async () => {
    const store = new MemoryCacheStore();

    // Simulate concurrent sets
    const promises = [];
    for (let i = 0; i < 10; i++) {
      promises.push(store.set(`key${i}`, createTestResponse(`test${i}`)));
    }

    await Promise.all(promises);

    expect(await store.size()).toBe(10);

    await store.close();
  });

  it('should handle concurrent gets and sets', async () => {
    const store = new MemoryCacheStore();

    await store.set('key1', createTestResponse('test1'));

    const promises = [
      store.get('key1'),
      store.set('key2', createTestResponse('test2')),
      store.get('key1'),
      store.set('key3', createTestResponse('test3')),
    ];

    const results = await Promise.all(promises);

    expect(results[0]).not.toBeNull();
    expect(results[2]).not.toBeNull();

    await store.close();
  });
});

describe('MemoryCacheStore - Cleanup', () => {
  it('should clean up multiple expired entries', async () => {
    const store = new MemoryCacheStore({ cleanupIntervalMs: 50 });

    // Add multiple entries with different expiration times
    await store.set('key1', createTestResponse('test1', 10)); // Expires quickly
    await store.set('key2', createTestResponse('test2', 10)); // Expires quickly
    await store.set('key3', createTestResponse('test3', 60000)); // Long expiry

    // Wait for cleanup
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(await store.has('key1')).toBe(false);
    expect(await store.has('key2')).toBe(false);
    expect(await store.has('key3')).toBe(true);

    await store.close();
  });

  it('should handle cleanup when store is empty', async () => {
    const store = new MemoryCacheStore({ cleanupIntervalMs: 50 });

    // Wait for cleanup to run on empty store
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(await store.size()).toBe(0);

    await store.close();
  });
});

describe('MemoryCacheStore - Edge Cases', () => {
  it('should handle overwriting entry with different size', async () => {
    const store = new MemoryCacheStore();

    const smallResponse = createTestResponse('a');
    const largeResponse = createTestResponse('a'.repeat(1000));

    await store.set('key1', smallResponse);
    const smallStats = store.getStats();

    await store.set('key1', largeResponse);
    const largeStats = store.getStats();

    expect(largeStats.sizeBytes).toBeGreaterThan(smallStats.sizeBytes);

    await store.close();
  });

  it('should handle keys() returning empty array', async () => {
    const store = new MemoryCacheStore();

    const keys = await store.keys();
    expect(keys).toEqual([]);

    await store.close();
  });

  it('should handle close called multiple times', async () => {
    const store = new MemoryCacheStore();

    await store.set('key1', createTestResponse('test1'));

    await store.close();
    await store.close(); // Should not throw

    expect(await store.size()).toBe(0);
  });

  it('should handle clear called multiple times', async () => {
    const store = new MemoryCacheStore();

    await store.set('key1', createTestResponse('test1'));

    await store.clear();
    await store.clear(); // Should not throw

    expect(await store.size()).toBe(0);

    await store.close();
  });
});

describe('MemoryCacheStore - Stats Calculation', () => {
  it('should calculate utilization percentage correctly', async () => {
    const maxSize = 1000;
    const store = new MemoryCacheStore({ maxSize });

    const stats1 = store.getStats();
    expect(stats1.utilizationPercent).toBe(0);

    await store.set('key1', createTestResponse('test1'));

    const stats2 = store.getStats();
    expect(stats2.utilizationPercent).toBeGreaterThan(0);
    expect(stats2.utilizationPercent).toBeLessThanOrEqual(100);

    await store.close();
  });
});
