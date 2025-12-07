/**
 * Tests for rate limit stores (Memory and Redis)
 *
 * Coverage includes:
 * - All store interface methods
 * - TTL expiration behavior
 * - Concurrent access patterns
 * - Cleanup mechanisms
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { MemoryStore, createMemoryStore } from '../src/stores/memory.mjs';

describe('MemoryStore', () => {
  let store: MemoryStore;

  beforeEach(() => {
    jest.useFakeTimers();
    store = new MemoryStore(60000);
  });

  afterEach(async () => {
    await store.close();
    jest.useRealTimers();
  });

  describe('getCount', () => {
    it('should return 0 for non-existent key', async () => {
      const count = await store.getCount('nonexistent');
      expect(count).toBe(0);
    });

    it('should return current count for existing key', async () => {
      await store.increment('key', 10000);
      await store.increment('key', 10000);

      const count = await store.getCount('key');
      expect(count).toBe(2);
    });

    it('should return 0 for expired key', async () => {
      await store.increment('key', 1000);

      jest.advanceTimersByTime(1001);

      const count = await store.getCount('key');
      expect(count).toBe(0);
    });

    it('should handle multiple keys independently', async () => {
      await store.increment('key1', 10000);
      await store.increment('key1', 10000);
      await store.increment('key2', 10000);

      expect(await store.getCount('key1')).toBe(2);
      expect(await store.getCount('key2')).toBe(1);
    });
  });

  describe('increment', () => {
    it('should create new entry with count 1', async () => {
      const count = await store.increment('key', 10000);
      expect(count).toBe(1);
    });

    it('should increment existing entry', async () => {
      await store.increment('key', 10000);
      const count = await store.increment('key', 10000);
      expect(count).toBe(2);
    });

    it('should reset count when TTL expires', async () => {
      await store.increment('key', 1000);
      await store.increment('key', 1000);

      jest.advanceTimersByTime(1001);

      const count = await store.increment('key', 1000);
      expect(count).toBe(1);
    });

    it('should handle rapid increments', async () => {
      const promises = Array.from({ length: 100 }, () =>
        store.increment('key', 10000)
      );

      const results = await Promise.all(promises);
      const count = await store.getCount('key');

      expect(count).toBe(100);
      expect(results).toContain(100);
    });

    it('should use correct TTL for new entries', async () => {
      await store.increment('key', 5000);

      jest.advanceTimersByTime(4999);
      expect(await store.getCount('key')).toBe(1);

      jest.advanceTimersByTime(2);
      expect(await store.getCount('key')).toBe(0);
    });
  });

  describe('getTTL', () => {
    it('should return 0 for non-existent key', async () => {
      const ttl = await store.getTTL('nonexistent');
      expect(ttl).toBe(0);
    });

    it('should return remaining TTL', async () => {
      await store.increment('key', 10000);

      jest.advanceTimersByTime(3000);

      const ttl = await store.getTTL('key');
      expect(ttl).toBeGreaterThanOrEqual(6900);
      expect(ttl).toBeLessThanOrEqual(7100);
    });

    it('should return 0 when TTL expired', async () => {
      await store.increment('key', 1000);

      jest.advanceTimersByTime(1001);

      const ttl = await store.getTTL('key');
      expect(ttl).toBe(0);
    });

    it('should never return negative TTL', async () => {
      await store.increment('key', 1000);

      jest.advanceTimersByTime(5000);

      const ttl = await store.getTTL('key');
      expect(ttl).toBe(0);
    });
  });

  describe('reset', () => {
    it('should remove existing key', async () => {
      await store.increment('key', 10000);
      await store.reset('key');

      const count = await store.getCount('key');
      expect(count).toBe(0);
    });

    it('should handle reset of non-existent key', async () => {
      await store.reset('nonexistent');
      expect(await store.getCount('nonexistent')).toBe(0);
    });

    it('should only affect specified key', async () => {
      await store.increment('key1', 10000);
      await store.increment('key2', 10000);

      await store.reset('key1');

      expect(await store.getCount('key1')).toBe(0);
      expect(await store.getCount('key2')).toBe(1);
    });
  });

  describe('close', () => {
    it('should clear all data', async () => {
      await store.increment('key1', 10000);
      await store.increment('key2', 10000);

      await store.close();

      expect(store.size).toBe(0);
    });

    it('should stop cleanup interval', async () => {
      await store.close();

      // Advance time significantly - should not cause errors
      jest.advanceTimersByTime(120000);
    });

    it('should be safe to call multiple times', async () => {
      await store.close();
      await store.close();
      await store.close();
    });
  });

  describe('size', () => {
    it('should be 0 for new store', () => {
      expect(store.size).toBe(0);
    });

    it('should track additions', async () => {
      await store.increment('key1', 10000);
      expect(store.size).toBe(1);

      await store.increment('key2', 10000);
      expect(store.size).toBe(2);
    });

    it('should not change for same key increments', async () => {
      await store.increment('key', 10000);
      await store.increment('key', 10000);

      expect(store.size).toBe(1);
    });
  });

  describe('cleanup', () => {
    it('should remove expired entries during cleanup cycle', async () => {
      await store.increment('key1', 30000);
      await store.increment('key2', 60000);

      jest.advanceTimersByTime(45000);

      // Trigger cleanup cycle
      jest.advanceTimersByTime(15001);

      expect(store.size).toBe(1);
      expect(await store.getCount('key1')).toBe(0);
      expect(await store.getCount('key2')).toBe(1);
    });

    it('should run cleanup at specified interval', async () => {
      const customStore = new MemoryStore(5000);

      await customStore.increment('key', 1000);

      jest.advanceTimersByTime(1001);
      expect(customStore.size).toBe(1);

      jest.advanceTimersByTime(5000);
      expect(customStore.size).toBe(0);

      await customStore.close();
    });
  });

  describe('createMemoryStore factory', () => {
    it('should create store with default cleanup interval', () => {
      const factoryStore = createMemoryStore();
      expect(factoryStore).toBeInstanceOf(MemoryStore);
    });

    it('should create store with custom cleanup interval', () => {
      const factoryStore = createMemoryStore(30000);
      expect(factoryStore).toBeInstanceOf(MemoryStore);
    });
  });

  describe('boundary conditions', () => {
    it('should handle very short TTL', async () => {
      await store.increment('key', 1);

      jest.advanceTimersByTime(2);

      expect(await store.getCount('key')).toBe(0);
    });

    it('should handle very long TTL', async () => {
      await store.increment('key', 86400000);

      jest.advanceTimersByTime(86399999);

      expect(await store.getCount('key')).toBe(1);
    });

    it('should handle zero TTL', async () => {
      const count = await store.increment('key', 0);
      expect(count).toBe(1);

      jest.advanceTimersByTime(1);
      expect(await store.getCount('key')).toBe(0);
    });

    it('should handle empty string key', async () => {
      await store.increment('', 10000);
      expect(await store.getCount('')).toBe(1);
    });

    it('should handle special characters in key', async () => {
      const specialKey = 'limiter:api:user@domain.com:path/to/resource';
      await store.increment(specialKey, 10000);
      expect(await store.getCount(specialKey)).toBe(1);
    });
  });

  describe('concurrent operations', () => {
    it('should handle concurrent increments correctly', async () => {
      const operations = Array.from({ length: 50 }, (_, i) =>
        store.increment(`key${i % 5}`, 10000)
      );

      await Promise.all(operations);

      let total = 0;
      for (let i = 0; i < 5; i++) {
        total += await store.getCount(`key${i}`);
      }

      expect(total).toBe(50);
    });

    it('should handle mixed operations', async () => {
      const operations = [
        store.increment('key', 10000),
        store.getCount('key'),
        store.increment('key', 10000),
        store.getTTL('key'),
        store.increment('key', 10000),
      ];

      await Promise.all(operations);
      expect(await store.getCount('key')).toBe(3);
    });
  });

  describe('state transitions', () => {
    it('should transition: empty -> active -> expired -> empty', async () => {
      expect(await store.getCount('key')).toBe(0);

      await store.increment('key', 1000);
      expect(await store.getCount('key')).toBe(1);

      jest.advanceTimersByTime(1001);
      expect(await store.getCount('key')).toBe(0);
    });

    it('should transition: active -> reset -> empty', async () => {
      await store.increment('key', 10000);
      expect(await store.getCount('key')).toBe(1);

      await store.reset('key');
      expect(await store.getCount('key')).toBe(0);
    });

    it('should transition: active -> close -> cleared', async () => {
      await store.increment('key', 10000);
      expect(store.size).toBe(1);

      await store.close();
      expect(store.size).toBe(0);
    });
  });
});
