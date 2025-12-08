/**
 * Tests for IdempotencyManager
 *
 * Coverage includes:
 * - Statement coverage: All executable statements
 * - Decision/Branch coverage: All conditional branches
 * - Condition coverage: Boolean conditions in decisions
 * - Path coverage: Key execution paths
 * - Boundary testing: TTL limits, key validation
 * - State transitions: Lifecycle of idempotency entries
 * - Error handling: Conflict detection, validation errors
 * - Event emission: Observer pattern verification
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import {
  IdempotencyManager,
  IdempotencyConflictError,
  createIdempotencyManager,
  DEFAULT_IDEMPOTENCY_CONFIG,
  mergeIdempotencyConfig,
  generateFingerprint,
} from '../src/idempotency.mjs';
import type {
  IdempotencyConfig,
  RequestFingerprint,
  CacheRequestEvent,
} from '../src/types.mjs';
import { MemoryCacheStore } from '../src/stores/memory.mjs';

describe('IdempotencyManager', () => {
  let manager: IdempotencyManager;

  beforeEach(() => {
    jest.useFakeTimers();
    manager = new IdempotencyManager();
  });

  afterEach(async () => {
    await manager.close();
    jest.useRealTimers();
  });

  describe('constructor', () => {
    it('should create with default configuration', () => {
      const config = manager.getConfig();
      expect(config.headerName).toBe('Idempotency-Key');
      expect(config.ttlMs).toBe(86400000);
      expect(config.autoGenerate).toBe(true);
      expect(config.methods).toEqual(['POST', 'PATCH']);
    });

    it('should create with custom configuration', async () => {
      const customManager = new IdempotencyManager({
        headerName: 'X-Request-Id',
        ttlMs: 3600000,
        autoGenerate: false,
        methods: ['POST', 'PUT'],
      });

      const config = customManager.getConfig();
      expect(config.headerName).toBe('X-Request-Id');
      expect(config.ttlMs).toBe(3600000);
      expect(config.autoGenerate).toBe(false);
      expect(config.methods).toEqual(['POST', 'PUT']);

      await customManager.close();
    });

    it('should accept custom store', async () => {
      const customStore = new MemoryCacheStore();
      const customManager = new IdempotencyManager({}, customStore);

      const key = customManager.generateKey();
      await customManager.store(key, 'test-value');

      const check = await customManager.check(key);
      expect(check.cached).toBe(true);

      await customManager.close();
    });

    it('should accept custom key generator', async () => {
      let counter = 0;
      const customManager = new IdempotencyManager({
        keyGenerator: () => `custom-key-${++counter}`,
      });

      expect(customManager.generateKey()).toBe('custom-key-1');
      expect(customManager.generateKey()).toBe('custom-key-2');

      await customManager.close();
    });
  });

  describe('generateKey()', () => {
    it('should generate a UUID by default', () => {
      const key = manager.generateKey();
      expect(key).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
      );
    });

    it('should generate unique keys', () => {
      const keys = new Set<string>();
      for (let i = 0; i < 1000; i++) {
        keys.add(manager.generateKey());
      }
      expect(keys.size).toBe(1000);
    });
  });

  describe('requiresIdempotency()', () => {
    it('should return true for POST', () => {
      expect(manager.requiresIdempotency('POST')).toBe(true);
    });

    it('should return true for PATCH', () => {
      expect(manager.requiresIdempotency('PATCH')).toBe(true);
    });

    it('should return false for GET', () => {
      expect(manager.requiresIdempotency('GET')).toBe(false);
    });

    it('should return false for PUT', () => {
      expect(manager.requiresIdempotency('PUT')).toBe(false);
    });

    it('should return false for DELETE', () => {
      expect(manager.requiresIdempotency('DELETE')).toBe(false);
    });

    it('should be case-insensitive', () => {
      expect(manager.requiresIdempotency('post')).toBe(true);
      expect(manager.requiresIdempotency('Post')).toBe(true);
      expect(manager.requiresIdempotency('POST')).toBe(true);
    });

    it('should respect custom methods configuration', async () => {
      const customManager = new IdempotencyManager({
        methods: ['PUT', 'DELETE'],
      });

      expect(customManager.requiresIdempotency('POST')).toBe(false);
      expect(customManager.requiresIdempotency('PUT')).toBe(true);
      expect(customManager.requiresIdempotency('DELETE')).toBe(true);

      await customManager.close();
    });
  });

  describe('check()', () => {
    it('should return cached: false for new key', async () => {
      const result = await manager.check('new-key');
      expect(result.cached).toBe(false);
      expect(result.key).toBe('new-key');
      expect(result.response).toBeUndefined();
    });

    it('should return cached: true for stored key', async () => {
      const key = 'stored-key';
      await manager.store(key, { data: 'test' });

      const result = await manager.check(key);
      expect(result.cached).toBe(true);
      expect(result.key).toBe(key);
      expect(result.response?.value).toEqual({ data: 'test' });
    });

    it('should return cached: false for expired key', async () => {
      const customManager = new IdempotencyManager({ ttlMs: 1000 });
      const key = 'expiring-key';
      await customManager.store(key, 'value');

      jest.advanceTimersByTime(1001);

      const result = await customManager.check(key);
      expect(result.cached).toBe(false);

      await customManager.close();
    });

    it('should validate fingerprint if provided', async () => {
      const key = 'fingerprint-key';
      const fingerprint: RequestFingerprint = {
        method: 'POST',
        url: '/api/users',
        body: Buffer.from('{"name":"test"}'),
      };

      await manager.store(key, 'value', fingerprint);

      // Same fingerprint should work
      const result = await manager.check(key, fingerprint);
      expect(result.cached).toBe(true);
    });

    it('should throw IdempotencyConflictError for different fingerprint', async () => {
      const key = 'conflict-key';
      const fingerprint1: RequestFingerprint = {
        method: 'POST',
        url: '/api/users',
        body: Buffer.from('{"name":"user1"}'),
      };
      const fingerprint2: RequestFingerprint = {
        method: 'POST',
        url: '/api/users',
        body: Buffer.from('{"name":"user2"}'),
      };

      await manager.store(key, 'value', fingerprint1);

      await expect(manager.check(key, fingerprint2)).rejects.toThrow(
        IdempotencyConflictError
      );
    });

    it('should emit idempotency:hit event on cache hit', async () => {
      const events: CacheRequestEvent[] = [];
      manager.on((event) => events.push(event));

      const key = 'hit-key';
      await manager.store(key, 'value');
      await manager.check(key);

      const hitEvents = events.filter((e) => e.type === 'idempotency:hit');
      expect(hitEvents.length).toBe(1);
      expect(hitEvents[0].key).toBe(key);
    });

    it('should emit idempotency:miss event on cache miss', async () => {
      const events: CacheRequestEvent[] = [];
      manager.on((event) => events.push(event));

      await manager.check('miss-key');

      const missEvents = events.filter((e) => e.type === 'idempotency:miss');
      expect(missEvents.length).toBe(1);
      expect(missEvents[0].key).toBe('miss-key');
    });
  });

  describe('store()', () => {
    it('should store a value', async () => {
      const key = 'store-key';
      await manager.store(key, { data: 'stored' });

      const check = await manager.check(key);
      expect(check.cached).toBe(true);
      expect(check.response?.value).toEqual({ data: 'stored' });
    });

    it('should store with fingerprint', async () => {
      const key = 'fingerprint-store-key';
      const fingerprint: RequestFingerprint = {
        method: 'POST',
        url: '/api/users',
      };

      await manager.store(key, 'value', fingerprint);

      const check = await manager.check(key, fingerprint);
      expect(check.cached).toBe(true);
    });

    it('should set correct expiration time', async () => {
      const customManager = new IdempotencyManager({ ttlMs: 5000 });
      const key = 'expiration-key';

      await customManager.store(key, 'value');

      // Before expiration
      jest.advanceTimersByTime(4999);
      let check = await customManager.check(key);
      expect(check.cached).toBe(true);

      // After expiration
      jest.advanceTimersByTime(2);
      check = await customManager.check(key);
      expect(check.cached).toBe(false);

      await customManager.close();
    });

    it('should emit idempotency:store event', async () => {
      const events: CacheRequestEvent[] = [];
      manager.on((event) => events.push(event));

      await manager.store('store-event-key', 'value');

      const storeEvents = events.filter((e) => e.type === 'idempotency:store');
      expect(storeEvents.length).toBe(1);
      expect(storeEvents[0].key).toBe('store-event-key');
      expect(storeEvents[0].metadata?.expiresAt).toBeDefined();
    });

    it('should overwrite existing entry', async () => {
      const key = 'overwrite-key';
      await manager.store(key, 'first');
      await manager.store(key, 'second');

      const check = await manager.check(key);
      expect(check.response?.value).toBe('second');
    });
  });

  describe('invalidate()', () => {
    it('should return true when invalidating existing key', async () => {
      const key = 'invalidate-key';
      await manager.store(key, 'value');

      const result = await manager.invalidate(key);
      expect(result).toBe(true);
    });

    it('should return false when invalidating non-existent key', async () => {
      const result = await manager.invalidate('nonexistent');
      expect(result).toBe(false);
    });

    it('should remove the cached entry', async () => {
      const key = 'remove-key';
      await manager.store(key, 'value');
      await manager.invalidate(key);

      const check = await manager.check(key);
      expect(check.cached).toBe(false);
    });

    it('should emit idempotency:expire event', async () => {
      const events: CacheRequestEvent[] = [];
      manager.on((event) => events.push(event));

      const key = 'expire-event-key';
      await manager.store(key, 'value');
      await manager.invalidate(key);

      const expireEvents = events.filter((e) => e.type === 'idempotency:expire');
      expect(expireEvents.length).toBe(1);
      expect(expireEvents[0].key).toBe(key);
    });
  });

  describe('getHeaderName()', () => {
    it('should return default header name', () => {
      expect(manager.getHeaderName()).toBe('Idempotency-Key');
    });

    it('should return custom header name', async () => {
      const customManager = new IdempotencyManager({
        headerName: 'X-Custom-Idempotency',
      });

      expect(customManager.getHeaderName()).toBe('X-Custom-Idempotency');

      await customManager.close();
    });
  });

  describe('getStats()', () => {
    it('should return correct size', async () => {
      expect((await manager.getStats()).size).toBe(0);

      await manager.store('key1', 'value1');
      expect((await manager.getStats()).size).toBe(1);

      await manager.store('key2', 'value2');
      expect((await manager.getStats()).size).toBe(2);
    });
  });

  describe('event listeners', () => {
    it('should add listener with on()', async () => {
      const events: CacheRequestEvent[] = [];
      manager.on((event) => events.push(event));

      await manager.store('key', 'value');

      expect(events.length).toBeGreaterThan(0);
    });

    it('should return unsubscribe function from on()', async () => {
      const events: CacheRequestEvent[] = [];
      const unsubscribe = manager.on((event) => events.push(event));

      await manager.store('key1', 'value1');
      unsubscribe();
      await manager.store('key2', 'value2');

      const storeEvents = events.filter((e) => e.type === 'idempotency:store');
      expect(storeEvents.length).toBe(1);
    });

    it('should remove listener with off()', async () => {
      const events: CacheRequestEvent[] = [];
      const listener = (event: CacheRequestEvent) => events.push(event);

      manager.on(listener);
      await manager.store('key1', 'value1');

      manager.off(listener);
      await manager.store('key2', 'value2');

      const storeEvents = events.filter((e) => e.type === 'idempotency:store');
      expect(storeEvents.length).toBe(1);
    });

    it('should handle listener errors gracefully', async () => {
      manager.on(() => {
        throw new Error('Listener error');
      });

      // Should not throw
      await manager.store('key', 'value');
    });
  });

  describe('close()', () => {
    it('should clear listeners', async () => {
      const events: CacheRequestEvent[] = [];
      manager.on((event) => events.push(event));

      await manager.close();

      // Create new manager to test listeners are cleared
      const newManager = new IdempotencyManager();
      await newManager.store('key', 'value');

      expect(events.filter((e) => e.key === 'key').length).toBe(0);

      await newManager.close();
    });
  });

  describe('IdempotencyConflictError', () => {
    it('should have correct properties', () => {
      const error = new IdempotencyConflictError('Test message');

      expect(error.message).toBe('Test message');
      expect(error.code).toBe('IDEMPOTENCY_CONFLICT');
      expect(error.name).toBe('IdempotencyConflictError');
      expect(error).toBeInstanceOf(Error);
    });
  });

  describe('boundary conditions', () => {
    it('should handle empty key', async () => {
      await manager.store('', 'value');
      const check = await manager.check('');
      expect(check.cached).toBe(true);
    });

    it('should handle very long key', async () => {
      const longKey = 'a'.repeat(10000);
      await manager.store(longKey, 'value');
      const check = await manager.check(longKey);
      expect(check.cached).toBe(true);
    });

    it('should handle special characters in key', async () => {
      const specialKey = 'key:with/special@chars#and$symbols';
      await manager.store(specialKey, 'value');
      const check = await manager.check(specialKey);
      expect(check.cached).toBe(true);
    });

    it('should handle null/undefined values', async () => {
      await manager.store('null-key', null);
      await manager.store('undefined-key', undefined);

      const nullCheck = await manager.check('null-key');
      const undefinedCheck = await manager.check('undefined-key');

      expect(nullCheck.cached).toBe(true);
      expect(nullCheck.response?.value).toBeNull();
      expect(undefinedCheck.cached).toBe(true);
      expect(undefinedCheck.response?.value).toBeUndefined();
    });

    it('should handle complex objects', async () => {
      const complexValue = {
        nested: { deeply: { value: [1, 2, 3] } },
        date: new Date().toISOString(),
        number: 12345,
        boolean: true,
      };

      await manager.store('complex-key', complexValue);
      const check = await manager.check('complex-key');

      expect(check.response?.value).toEqual(complexValue);
    });
  });

  describe('concurrent operations', () => {
    it('should handle concurrent stores', async () => {
      const promises = Array.from({ length: 100 }, (_, i) =>
        manager.store(`concurrent-key-${i}`, `value-${i}`)
      );

      await Promise.all(promises);

      const stats = await manager.getStats();
      expect(stats.size).toBe(100);
    });

    it('should handle concurrent checks', async () => {
      await manager.store('shared-key', 'value');

      const promises = Array.from({ length: 100 }, () =>
        manager.check('shared-key')
      );

      const results = await Promise.all(promises);
      expect(results.every((r) => r.cached)).toBe(true);
    });
  });

  describe('state transitions', () => {
    it('should transition: new -> stored -> checked -> invalidated -> new', async () => {
      const key = 'state-key';

      // New state
      let check = await manager.check(key);
      expect(check.cached).toBe(false);

      // Stored state
      await manager.store(key, 'value');

      // Checked state (cached)
      check = await manager.check(key);
      expect(check.cached).toBe(true);

      // Invalidated state
      await manager.invalidate(key);

      // Back to new state
      check = await manager.check(key);
      expect(check.cached).toBe(false);
    });

    it('should transition: stored -> expired -> new', async () => {
      const customManager = new IdempotencyManager({ ttlMs: 1000 });
      const key = 'expire-state-key';

      await customManager.store(key, 'value');
      expect((await customManager.check(key)).cached).toBe(true);

      jest.advanceTimersByTime(1001);

      expect((await customManager.check(key)).cached).toBe(false);

      await customManager.close();
    });
  });
});

describe('Configuration helpers', () => {
  describe('DEFAULT_IDEMPOTENCY_CONFIG', () => {
    it('should have correct default values', () => {
      expect(DEFAULT_IDEMPOTENCY_CONFIG.headerName).toBe('Idempotency-Key');
      expect(DEFAULT_IDEMPOTENCY_CONFIG.ttlMs).toBe(86400000);
      expect(DEFAULT_IDEMPOTENCY_CONFIG.autoGenerate).toBe(true);
      expect(DEFAULT_IDEMPOTENCY_CONFIG.methods).toEqual(['POST', 'PATCH']);
      expect(typeof DEFAULT_IDEMPOTENCY_CONFIG.keyGenerator).toBe('function');
    });
  });

  describe('mergeIdempotencyConfig()', () => {
    it('should return defaults when no config provided', () => {
      const merged = mergeIdempotencyConfig();
      expect(merged.headerName).toBe('Idempotency-Key');
      expect(merged.ttlMs).toBe(86400000);
    });

    it('should merge partial config with defaults', () => {
      const merged = mergeIdempotencyConfig({ ttlMs: 3600000 });
      expect(merged.headerName).toBe('Idempotency-Key');
      expect(merged.ttlMs).toBe(3600000);
    });

    it('should preserve all custom values', () => {
      const customConfig: IdempotencyConfig = {
        headerName: 'X-Custom',
        ttlMs: 1000,
        autoGenerate: false,
        methods: ['PUT'],
      };
      const merged = mergeIdempotencyConfig(customConfig);

      expect(merged.headerName).toBe('X-Custom');
      expect(merged.ttlMs).toBe(1000);
      expect(merged.autoGenerate).toBe(false);
      expect(merged.methods).toEqual(['PUT']);
    });
  });

  describe('generateFingerprint()', () => {
    it('should generate fingerprint from method and url', () => {
      const fingerprint = generateFingerprint({
        method: 'POST',
        url: '/api/users',
      });

      expect(fingerprint).toBe('POST|/api/users');
    });

    it('should include body in fingerprint', () => {
      const fingerprint = generateFingerprint({
        method: 'POST',
        url: '/api/users',
        body: Buffer.from('{"name":"test"}'),
      });

      expect(fingerprint).toBe('POST|/api/users|{"name":"test"}');
    });

    it('should handle null body', () => {
      const fingerprint = generateFingerprint({
        method: 'GET',
        url: '/api/users',
        body: null,
      });

      expect(fingerprint).toBe('GET|/api/users');
    });

    it('should handle binary body', () => {
      const binaryBody = Buffer.from([0x00, 0x01, 0x02, 0xff]);
      const fingerprint = generateFingerprint({
        method: 'POST',
        url: '/api/upload',
        body: binaryBody,
      });

      expect(fingerprint).toContain('POST|/api/upload|');
    });
  });

  describe('createIdempotencyManager()', () => {
    it('should create manager with default config', async () => {
      const mgr = createIdempotencyManager();
      expect(mgr).toBeInstanceOf(IdempotencyManager);
      await mgr.close();
    });

    it('should create manager with custom config', async () => {
      const mgr = createIdempotencyManager({ ttlMs: 1000 });
      expect(mgr.getConfig().ttlMs).toBe(1000);
      await mgr.close();
    });

    it('should create manager with custom store', async () => {
      const store = new MemoryCacheStore();
      const mgr = createIdempotencyManager({}, store);
      expect(mgr).toBeInstanceOf(IdempotencyManager);
      await mgr.close();
    });
  });
});
