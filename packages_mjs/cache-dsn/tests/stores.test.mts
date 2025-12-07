/**
 * Tests for DNS cache stores (Memory)
 *
 * Coverage includes:
 * - All store interface methods (get, set, delete, has, keys, size, clear, close)
 * - LRU eviction behavior
 * - Concurrent access patterns
 * - State transitions: empty -> active -> expired -> evicted
 * - Boundary conditions: max entries, special characters
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { MemoryStore, createMemoryStore } from '../src/stores/memory.mjs';
import type { CachedEntry, ResolvedEndpoint } from '../src/types.mjs';

describe('MemoryStore', () => {
  let store: MemoryStore;

  const createEntry = (dsn: string, expiresIn: number = 60000): CachedEntry => {
    const now = Date.now();
    return {
      dsn,
      endpoints: [{ host: '10.0.0.1', port: 80, healthy: true }],
      resolvedAt: now,
      expiresAt: now + expiresIn,
      ttlMs: expiresIn,
      hitCount: 0,
    };
  };

  beforeEach(() => {
    store = new MemoryStore(100);
  });

  afterEach(async () => {
    await store.close();
  });

  describe('get', () => {
    it('should return undefined for non-existent key', async () => {
      const result = await store.get('nonexistent');
      expect(result).toBeUndefined();
    });

    it('should return entry for existing key', async () => {
      const entry = createEntry('example.com');
      await store.set('example.com', entry);

      const result = await store.get('example.com');
      expect(result).toEqual(entry);
    });

    it('should update LRU order on access', async () => {
      // Fill store
      for (let i = 0; i < 100; i++) {
        await store.set(`key${i}`, createEntry(`key${i}`));
      }

      // Access key0 to make it recently used
      await store.get('key0');

      // Add new entry to trigger eviction
      await store.set('newkey', createEntry('newkey'));

      // key0 should still exist (was recently accessed)
      expect(await store.has('key0')).toBe(true);

      // key1 should be evicted (was least recently used)
      expect(await store.has('key1')).toBe(false);
    });

    it('should handle concurrent gets', async () => {
      const entry = createEntry('example.com');
      await store.set('example.com', entry);

      const results = await Promise.all([
        store.get('example.com'),
        store.get('example.com'),
        store.get('example.com'),
      ]);

      expect(results.every((r) => r?.dsn === 'example.com')).toBe(true);
    });
  });

  describe('set', () => {
    it('should store entry', async () => {
      const entry = createEntry('example.com');
      await store.set('example.com', entry);

      expect(await store.size()).toBe(1);
      expect(await store.get('example.com')).toEqual(entry);
    });

    it('should update existing entry', async () => {
      const entry1 = createEntry('example.com');
      await store.set('example.com', entry1);

      const entry2 = createEntry('example.com', 120000);
      await store.set('example.com', entry2);

      expect(await store.size()).toBe(1);
      expect((await store.get('example.com'))?.ttlMs).toBe(120000);
    });

    it('should evict LRU when at capacity', async () => {
      // Fill store to capacity
      for (let i = 0; i < 100; i++) {
        await store.set(`key${i}`, createEntry(`key${i}`));
      }

      expect(await store.size()).toBe(100);

      // Add one more
      await store.set('overflow', createEntry('overflow'));

      expect(await store.size()).toBe(100);
      expect(await store.has('overflow')).toBe(true);
      // First key should be evicted
      expect(await store.has('key0')).toBe(false);
    });

    it('should not evict when updating existing key', async () => {
      for (let i = 0; i < 100; i++) {
        await store.set(`key${i}`, createEntry(`key${i}`));
      }

      // Update existing key
      await store.set('key50', createEntry('key50', 120000));

      expect(await store.size()).toBe(100);
      expect(await store.has('key0')).toBe(true);
    });

    it('should handle rapid sets', async () => {
      const promises = Array.from({ length: 50 }, (_, i) =>
        store.set(`key${i}`, createEntry(`key${i}`))
      );

      await Promise.all(promises);
      expect(await store.size()).toBe(50);
    });
  });

  describe('delete', () => {
    it('should return true for existing key', async () => {
      await store.set('example.com', createEntry('example.com'));
      const result = await store.delete('example.com');

      expect(result).toBe(true);
      expect(await store.has('example.com')).toBe(false);
    });

    it('should return false for non-existent key', async () => {
      const result = await store.delete('nonexistent');
      expect(result).toBe(false);
    });

    it('should update size', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key2', createEntry('key2'));

      expect(await store.size()).toBe(2);

      await store.delete('key1');

      expect(await store.size()).toBe(1);
    });

    it('should only delete specified key', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key2', createEntry('key2'));

      await store.delete('key1');

      expect(await store.has('key1')).toBe(false);
      expect(await store.has('key2')).toBe(true);
    });
  });

  describe('has', () => {
    it('should return true for existing key', async () => {
      await store.set('example.com', createEntry('example.com'));
      expect(await store.has('example.com')).toBe(true);
    });

    it('should return false for non-existent key', async () => {
      expect(await store.has('nonexistent')).toBe(false);
    });

    it('should return false after delete', async () => {
      await store.set('example.com', createEntry('example.com'));
      await store.delete('example.com');
      expect(await store.has('example.com')).toBe(false);
    });
  });

  describe('keys', () => {
    it('should return empty array for empty store', async () => {
      const keys = await store.keys();
      expect(keys).toEqual([]);
    });

    it('should return all keys', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key2', createEntry('key2'));
      await store.set('key3', createEntry('key3'));

      const keys = await store.keys();

      expect(keys).toHaveLength(3);
      expect(keys).toContain('key1');
      expect(keys).toContain('key2');
      expect(keys).toContain('key3');
    });
  });

  describe('size', () => {
    it('should return 0 for empty store', async () => {
      expect(await store.size()).toBe(0);
    });

    it('should track additions', async () => {
      await store.set('key1', createEntry('key1'));
      expect(await store.size()).toBe(1);

      await store.set('key2', createEntry('key2'));
      expect(await store.size()).toBe(2);
    });

    it('should track deletions', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key2', createEntry('key2'));

      await store.delete('key1');

      expect(await store.size()).toBe(1);
    });

    it('should not increment for same key update', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key1', createEntry('key1', 120000));

      expect(await store.size()).toBe(1);
    });
  });

  describe('clear', () => {
    it('should remove all entries', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key2', createEntry('key2'));
      await store.set('key3', createEntry('key3'));

      await store.clear();

      expect(await store.size()).toBe(0);
      expect(await store.has('key1')).toBe(false);
      expect(await store.has('key2')).toBe(false);
      expect(await store.has('key3')).toBe(false);
    });

    it('should be safe to call on empty store', async () => {
      await store.clear();
      expect(await store.size()).toBe(0);
    });
  });

  describe('close', () => {
    it('should clear all data', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key2', createEntry('key2'));

      await store.close();

      expect(await store.size()).toBe(0);
    });

    it('should be safe to call multiple times', async () => {
      await store.close();
      await store.close();
      await store.close();
    });
  });

  describe('pruneExpired', () => {
    it('should remove expired entries', async () => {
      const now = Date.now();

      // Create expired entry
      const expiredEntry: CachedEntry = {
        dsn: 'expired.com',
        endpoints: [],
        resolvedAt: now - 10000,
        expiresAt: now - 5000, // Already expired
        ttlMs: 5000,
        hitCount: 0,
      };

      // Create valid entry
      const validEntry: CachedEntry = {
        dsn: 'valid.com',
        endpoints: [],
        resolvedAt: now,
        expiresAt: now + 60000, // Expires in future
        ttlMs: 60000,
        hitCount: 0,
      };

      await store.set('expired.com', expiredEntry);
      await store.set('valid.com', validEntry);

      const pruned = await store.pruneExpired();

      expect(pruned).toBe(1);
      expect(await store.has('expired.com')).toBe(false);
      expect(await store.has('valid.com')).toBe(true);
    });

    it('should return 0 when no expired entries', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key2', createEntry('key2'));

      const pruned = await store.pruneExpired();
      expect(pruned).toBe(0);
    });

    it('should use provided timestamp', async () => {
      const entry = createEntry('example.com', 10000);
      await store.set('example.com', entry);

      // Prune with future timestamp
      const futureTime = Date.now() + 20000;
      const pruned = await store.pruneExpired(futureTime);

      expect(pruned).toBe(1);
    });
  });

  describe('entries', () => {
    it('should return all entries', async () => {
      await store.set('key1', createEntry('key1'));
      await store.set('key2', createEntry('key2'));

      const entries = await store.entries();

      expect(entries).toHaveLength(2);
      expect(entries.map((e) => e.dsn)).toContain('key1');
      expect(entries.map((e) => e.dsn)).toContain('key2');
    });

    it('should return empty array for empty store', async () => {
      const entries = await store.entries();
      expect(entries).toEqual([]);
    });
  });

  describe('boundary conditions', () => {
    it('should handle empty string key', async () => {
      await store.set('', createEntry(''));
      expect(await store.has('')).toBe(true);
      expect((await store.get(''))?.dsn).toBe('');
    });

    it('should handle special characters in key', async () => {
      const specialKey = 'api:user@example.com:path/to/resource?query=1';
      await store.set(specialKey, createEntry(specialKey));
      expect(await store.has(specialKey)).toBe(true);
    });

    it('should handle unicode characters in key', async () => {
      const unicodeKey = 'api.例え.com';
      await store.set(unicodeKey, createEntry(unicodeKey));
      expect(await store.has(unicodeKey)).toBe(true);
    });

    it('should handle very long keys', async () => {
      const longKey = 'a'.repeat(1000);
      await store.set(longKey, createEntry(longKey));
      expect(await store.has(longKey)).toBe(true);
    });

    it('should handle store with maxEntries = 1', async () => {
      const smallStore = new MemoryStore(1);

      await smallStore.set('key1', createEntry('key1'));
      expect(await smallStore.size()).toBe(1);

      await smallStore.set('key2', createEntry('key2'));
      expect(await smallStore.size()).toBe(1);
      expect(await smallStore.has('key1')).toBe(false);
      expect(await smallStore.has('key2')).toBe(true);

      await smallStore.close();
    });

    it('should handle entry with many endpoints', async () => {
      const manyEndpoints: ResolvedEndpoint[] = Array.from({ length: 100 }, (_, i) => ({
        host: `10.0.0.${i}`,
        port: 80,
        healthy: true,
      }));

      const entry: CachedEntry = {
        dsn: 'example.com',
        endpoints: manyEndpoints,
        resolvedAt: Date.now(),
        expiresAt: Date.now() + 60000,
        ttlMs: 60000,
        hitCount: 0,
      };

      await store.set('example.com', entry);
      const retrieved = await store.get('example.com');
      expect(retrieved?.endpoints).toHaveLength(100);
    });
  });

  describe('concurrent operations', () => {
    it('should handle concurrent sets to different keys', async () => {
      const operations = Array.from({ length: 50 }, (_, i) =>
        store.set(`key${i}`, createEntry(`key${i}`))
      );

      await Promise.all(operations);
      expect(await store.size()).toBe(50);
    });

    it('should handle concurrent sets to same key', async () => {
      const operations = Array.from({ length: 10 }, (_, i) =>
        store.set('shared', createEntry('shared', 60000 + i * 1000))
      );

      await Promise.all(operations);
      expect(await store.size()).toBe(1);
    });

    it('should handle mixed concurrent operations', async () => {
      await store.set('key', createEntry('key'));

      const operations = [
        store.get('key'),
        store.set('key2', createEntry('key2')),
        store.has('key'),
        store.delete('key'),
        store.set('key3', createEntry('key3')),
      ];

      await Promise.all(operations);
      expect(await store.has('key')).toBe(false);
      expect(await store.has('key2')).toBe(true);
      expect(await store.has('key3')).toBe(true);
    });
  });

  describe('state transitions', () => {
    it('should transition: empty -> populated -> cleared -> empty', async () => {
      expect(await store.size()).toBe(0);

      await store.set('key', createEntry('key'));
      expect(await store.size()).toBe(1);

      await store.clear();
      expect(await store.size()).toBe(0);
    });

    it('should transition: populated -> deleted -> repopulated', async () => {
      await store.set('key', createEntry('key'));
      expect(await store.has('key')).toBe(true);

      await store.delete('key');
      expect(await store.has('key')).toBe(false);

      await store.set('key', createEntry('key'));
      expect(await store.has('key')).toBe(true);
    });

    it('should transition: at capacity -> evict -> stable', async () => {
      // Fill to capacity
      for (let i = 0; i < 100; i++) {
        await store.set(`key${i}`, createEntry(`key${i}`));
      }
      expect(await store.size()).toBe(100);

      // Add more entries - should evict and maintain capacity
      for (let i = 100; i < 150; i++) {
        await store.set(`key${i}`, createEntry(`key${i}`));
      }
      expect(await store.size()).toBe(100);
    });
  });
});

describe('createMemoryStore factory', () => {
  it('should create store with default maxEntries', async () => {
    const store = createMemoryStore();
    expect(store).toBeInstanceOf(MemoryStore);
    await store.close();
  });

  it('should create store with custom maxEntries', async () => {
    const store = createMemoryStore(500);
    expect(store).toBeInstanceOf(MemoryStore);

    // Verify custom limit
    for (let i = 0; i < 550; i++) {
      await store.set(`key${i}`, {
        dsn: `key${i}`,
        endpoints: [],
        resolvedAt: Date.now(),
        expiresAt: Date.now() + 60000,
        ttlMs: 60000,
        hitCount: 0,
      });
    }

    expect(await store.size()).toBe(500);
    await store.close();
  });
});
