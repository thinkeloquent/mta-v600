/**
 * Tests for cache request stores (Memory implementations)
 *
 * Coverage includes:
 * - Statement coverage: All executable statements
 * - Decision coverage: All branches (true/false)
 * - Condition coverage: All boolean conditions
 * - Path coverage: Key execution paths
 * - Boundary testing: Edge cases and limits
 * - State transitions: Store lifecycle states
 * - Concurrent operations: Parallel access patterns
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import {
  MemoryCacheStore,
  MemorySingleflightStore,
  createMemoryCacheStore,
  createMemorySingleflightStore,
} from '../src/stores/memory.mjs';
import type { StoredResponse, InFlightRequest } from '../src/types.mjs';

describe('MemoryCacheStore', () => {
  let store: MemoryCacheStore;

  beforeEach(() => {
    jest.useFakeTimers();
    store = new MemoryCacheStore({ cleanupIntervalMs: 60000 });
  });

  afterEach(async () => {
    await store.close();
    jest.useRealTimers();
  });

  describe('get()', () => {
    it('should return null for non-existent key', async () => {
      const result = await store.get('nonexistent');
      expect(result).toBeNull();
    });

    it('should return stored response for existing key', async () => {
      const response: StoredResponse<string> = {
        value: 'test-value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      };
      await store.set('key', response);

      const result = await store.get<string>('key');
      expect(result).not.toBeNull();
      expect(result?.value).toBe('test-value');
    });

    it('should return null for expired key and remove it', async () => {
      const response: StoredResponse<string> = {
        value: 'test-value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 1000,
      };
      await store.set('key', response);

      jest.advanceTimersByTime(1001);

      const result = await store.get('key');
      expect(result).toBeNull();
      expect(await store.has('key')).toBe(false);
    });

    it('should handle generic types correctly', async () => {
      interface TestData {
        id: number;
        name: string;
      }
      const response: StoredResponse<TestData> = {
        value: { id: 1, name: 'test' },
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      };
      await store.set('typed-key', response);

      const result = await store.get<TestData>('typed-key');
      expect(result?.value.id).toBe(1);
      expect(result?.value.name).toBe('test');
    });
  });

  describe('set()', () => {
    it('should store a new entry', async () => {
      const response: StoredResponse<string> = {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      };
      await store.set('key', response);

      expect(await store.has('key')).toBe(true);
    });

    it('should overwrite existing entry', async () => {
      const response1: StoredResponse<string> = {
        value: 'first',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      };
      const response2: StoredResponse<string> = {
        value: 'second',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      };

      await store.set('key', response1);
      await store.set('key', response2);

      const result = await store.get<string>('key');
      expect(result?.value).toBe('second');
    });

    it('should handle multiple keys independently', async () => {
      await store.set('key1', {
        value: 'value1',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });
      await store.set('key2', {
        value: 'value2',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      expect((await store.get<string>('key1'))?.value).toBe('value1');
      expect((await store.get<string>('key2'))?.value).toBe('value2');
    });
  });

  describe('has()', () => {
    it('should return false for non-existent key', async () => {
      expect(await store.has('nonexistent')).toBe(false);
    });

    it('should return true for existing key', async () => {
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      expect(await store.has('key')).toBe(true);
    });

    it('should return false for expired key and remove it', async () => {
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 1000,
      });

      jest.advanceTimersByTime(1001);

      expect(await store.has('key')).toBe(false);
    });
  });

  describe('delete()', () => {
    it('should return true when deleting existing key', async () => {
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      const result = await store.delete('key');
      expect(result).toBe(true);
      expect(await store.has('key')).toBe(false);
    });

    it('should return false when deleting non-existent key', async () => {
      const result = await store.delete('nonexistent');
      expect(result).toBe(false);
    });

    it('should only delete specified key', async () => {
      await store.set('key1', {
        value: 'value1',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });
      await store.set('key2', {
        value: 'value2',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      await store.delete('key1');

      expect(await store.has('key1')).toBe(false);
      expect(await store.has('key2')).toBe(true);
    });
  });

  describe('clear()', () => {
    it('should remove all entries', async () => {
      await store.set('key1', {
        value: 'value1',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });
      await store.set('key2', {
        value: 'value2',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      await store.clear();

      expect(await store.size()).toBe(0);
    });

    it('should be safe to call on empty store', async () => {
      await store.clear();
      expect(await store.size()).toBe(0);
    });
  });

  describe('size()', () => {
    it('should return 0 for empty store', async () => {
      expect(await store.size()).toBe(0);
    });

    it('should return correct count', async () => {
      await store.set('key1', {
        value: 'value1',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });
      await store.set('key2', {
        value: 'value2',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      expect(await store.size()).toBe(2);
    });

    it('should cleanup expired entries before returning size', async () => {
      await store.set('key1', {
        value: 'value1',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 1000,
      });
      await store.set('key2', {
        value: 'value2',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      jest.advanceTimersByTime(1001);

      expect(await store.size()).toBe(1);
    });
  });

  describe('close()', () => {
    it('should clear all data', async () => {
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      await store.close();

      expect(await store.size()).toBe(0);
    });

    it('should be safe to call multiple times', async () => {
      await store.close();
      await store.close();
      await store.close();
    });

    it('should stop cleanup interval', async () => {
      await store.close();
      jest.advanceTimersByTime(120000);
      // No errors should occur
    });
  });

  describe('cleanup mechanism', () => {
    it('should automatically remove expired entries', async () => {
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 30000,
      });

      jest.advanceTimersByTime(30001);
      jest.advanceTimersByTime(60001); // Trigger cleanup cycle

      expect(await store.size()).toBe(0);
    });
  });

  describe('boundary conditions', () => {
    it('should handle empty string key', async () => {
      await store.set('', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      expect(await store.has('')).toBe(true);
    });

    it('should handle special characters in key', async () => {
      const specialKey = 'key:with/special@chars#and$symbols';
      await store.set(specialKey, {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      expect(await store.has(specialKey)).toBe(true);
    });

    it('should handle very long key', async () => {
      const longKey = 'a'.repeat(10000);
      await store.set(longKey, {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      expect(await store.has(longKey)).toBe(true);
    });

    it('should handle immediate expiration', async () => {
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now(),
      });

      jest.advanceTimersByTime(1);

      expect(await store.has('key')).toBe(false);
    });
  });

  describe('concurrent operations', () => {
    it('should handle concurrent sets', async () => {
      const promises = Array.from({ length: 100 }, (_, i) =>
        store.set(`key${i}`, {
          value: `value${i}`,
          cachedAt: Date.now(),
          expiresAt: Date.now() + 10000,
        })
      );

      await Promise.all(promises);

      expect(await store.size()).toBe(100);
    });

    it('should handle concurrent gets', async () => {
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });

      const promises = Array.from({ length: 100 }, () => store.get('key'));
      const results = await Promise.all(promises);

      expect(results.every((r) => r?.value === 'value')).toBe(true);
    });

    it('should handle mixed operations', async () => {
      const operations = [
        store.set('key', {
          value: 'value',
          cachedAt: Date.now(),
          expiresAt: Date.now() + 10000,
        }),
        store.get('key'),
        store.has('key'),
        store.size(),
      ];

      await Promise.all(operations);
    });
  });

  describe('state transitions', () => {
    it('should transition: empty -> stored -> retrieved -> deleted -> empty', async () => {
      // Empty state
      expect(await store.has('key')).toBe(false);

      // Stored state
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 10000,
      });
      expect(await store.has('key')).toBe(true);

      // Retrieved state
      const result = await store.get('key');
      expect(result?.value).toBe('value');

      // Deleted state
      await store.delete('key');
      expect(await store.has('key')).toBe(false);
    });

    it('should transition: stored -> expired -> auto-removed', async () => {
      await store.set('key', {
        value: 'value',
        cachedAt: Date.now(),
        expiresAt: Date.now() + 1000,
      });
      expect(await store.has('key')).toBe(true);

      jest.advanceTimersByTime(1001);

      expect(await store.has('key')).toBe(false);
    });
  });

  describe('factory function', () => {
    it('should create store with default options', () => {
      const factoryStore = createMemoryCacheStore();
      expect(factoryStore).toBeInstanceOf(MemoryCacheStore);
    });

    it('should create store with custom cleanup interval', () => {
      const factoryStore = createMemoryCacheStore({ cleanupIntervalMs: 30000 });
      expect(factoryStore).toBeInstanceOf(MemoryCacheStore);
    });
  });
});

describe('MemorySingleflightStore', () => {
  let store: MemorySingleflightStore;

  beforeEach(() => {
    store = new MemorySingleflightStore();
  });

  describe('get()', () => {
    it('should return null for non-existent fingerprint', () => {
      const result = store.get('nonexistent');
      expect(result).toBeNull();
    });

    it('should return stored request for existing fingerprint', () => {
      const request: InFlightRequest<string> = {
        promise: Promise.resolve('value'),
        subscribers: 1,
        startedAt: Date.now(),
      };
      store.set('fingerprint', request);

      const result = store.get<string>('fingerprint');
      expect(result).not.toBeNull();
      expect(result?.subscribers).toBe(1);
    });
  });

  describe('set()', () => {
    it('should store a new in-flight request', () => {
      const request: InFlightRequest<string> = {
        promise: Promise.resolve('value'),
        subscribers: 1,
        startedAt: Date.now(),
      };
      store.set('fingerprint', request);

      expect(store.has('fingerprint')).toBe(true);
    });

    it('should overwrite existing request', () => {
      const request1: InFlightRequest<string> = {
        promise: Promise.resolve('first'),
        subscribers: 1,
        startedAt: Date.now(),
      };
      const request2: InFlightRequest<string> = {
        promise: Promise.resolve('second'),
        subscribers: 2,
        startedAt: Date.now(),
      };

      store.set('fingerprint', request1);
      store.set('fingerprint', request2);

      const result = store.get<string>('fingerprint');
      expect(result?.subscribers).toBe(2);
    });
  });

  describe('delete()', () => {
    it('should return true when deleting existing request', () => {
      store.set('fingerprint', {
        promise: Promise.resolve('value'),
        subscribers: 1,
        startedAt: Date.now(),
      });

      const result = store.delete('fingerprint');
      expect(result).toBe(true);
      expect(store.has('fingerprint')).toBe(false);
    });

    it('should return false when deleting non-existent request', () => {
      const result = store.delete('nonexistent');
      expect(result).toBe(false);
    });
  });

  describe('has()', () => {
    it('should return false for non-existent fingerprint', () => {
      expect(store.has('nonexistent')).toBe(false);
    });

    it('should return true for existing fingerprint', () => {
      store.set('fingerprint', {
        promise: Promise.resolve('value'),
        subscribers: 1,
        startedAt: Date.now(),
      });

      expect(store.has('fingerprint')).toBe(true);
    });
  });

  describe('size()', () => {
    it('should return 0 for empty store', () => {
      expect(store.size()).toBe(0);
    });

    it('should return correct count', () => {
      store.set('fingerprint1', {
        promise: Promise.resolve('value1'),
        subscribers: 1,
        startedAt: Date.now(),
      });
      store.set('fingerprint2', {
        promise: Promise.resolve('value2'),
        subscribers: 1,
        startedAt: Date.now(),
      });

      expect(store.size()).toBe(2);
    });
  });

  describe('clear()', () => {
    it('should remove all in-flight requests', () => {
      store.set('fingerprint1', {
        promise: Promise.resolve('value1'),
        subscribers: 1,
        startedAt: Date.now(),
      });
      store.set('fingerprint2', {
        promise: Promise.resolve('value2'),
        subscribers: 1,
        startedAt: Date.now(),
      });

      store.clear();

      expect(store.size()).toBe(0);
    });
  });

  describe('factory function', () => {
    it('should create a singleflight store', () => {
      const factoryStore = createMemorySingleflightStore();
      expect(factoryStore).toBeInstanceOf(MemorySingleflightStore);
    });
  });
});
