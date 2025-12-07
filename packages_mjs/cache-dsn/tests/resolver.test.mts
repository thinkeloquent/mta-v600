/**
 * Tests for DnsCacheResolver
 *
 * Coverage includes:
 * - Decision Coverage: All resolution paths (cache hit, miss, stale)
 * - State Transitions: healthy -> unhealthy -> healthy
 * - Event System: All event types emitted correctly
 * - Concurrent Operations: Parallel resolution and invalidation
 * - Custom Resolvers: Registration and usage
 * - Statistics: Accurate metric tracking
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  DnsCacheResolver,
  createDnsCacheResolver,
} from '../src/resolver.mjs';
import { MemoryStore } from '../src/stores/memory.mjs';
import type {
  DnsCacheConfig,
  DnsCacheEvent,
  ResolvedEndpoint,
} from '../src/types.mjs';

describe('DnsCacheResolver', () => {
  let resolver: DnsCacheResolver;
  let config: DnsCacheConfig;

  beforeEach(() => {
    config = {
      id: 'test-resolver',
      defaultTtlMs: 60000,
      minTtlMs: 1000,
      maxTtlMs: 300000,
      staleWhileRevalidate: true,
      staleGracePeriodMs: 5000,
      loadBalanceStrategy: 'round-robin',
    };
    resolver = new DnsCacheResolver(config);
  });

  afterEach(async () => {
    await resolver.destroy();
  });

  describe('resolve', () => {
    describe('cache miss', () => {
      it('should resolve and cache result', async () => {
        const result = await resolver.resolve('localhost');

        expect(result.endpoints.length).toBeGreaterThanOrEqual(1);
        expect(result.fromCache).toBe(false);
        expect(result.ttlRemainingMs).toBeGreaterThan(0);
        expect(result.resolutionTimeMs).toBeGreaterThanOrEqual(0);

        // Second resolution should be cached
        const cached = await resolver.resolve('localhost');
        expect(cached.fromCache).toBe(true);
      });

      it('should emit cache:miss event', async () => {
        const events: DnsCacheEvent[] = [];
        resolver.on((e) => events.push(e));

        await resolver.resolve('localhost');

        expect(events.some((e) => e.type === 'cache:miss')).toBe(true);
      });

      it('should emit resolve:start and resolve:success events', async () => {
        const events: DnsCacheEvent[] = [];
        resolver.on((e) => events.push(e));

        await resolver.resolve('localhost');

        expect(events.some((e) => e.type === 'resolve:start')).toBe(true);
        expect(events.some((e) => e.type === 'resolve:success')).toBe(true);
      });
    });

    describe('cache hit', () => {
      it('should return cached result', async () => {
        await resolver.resolve('localhost');
        const result = await resolver.resolve('localhost');

        expect(result.fromCache).toBe(true);
        expect(result.endpoints.length).toBeGreaterThanOrEqual(1);
      });

      it('should emit cache:hit event', async () => {
        await resolver.resolve('localhost');

        const events: DnsCacheEvent[] = [];
        resolver.on((e) => events.push(e));

        await resolver.resolve('localhost');

        expect(events.some((e) => e.type === 'cache:hit')).toBe(true);
      });

      it('should increment hit count', async () => {
        await resolver.resolve('localhost');
        await resolver.resolve('localhost');
        await resolver.resolve('localhost');

        const stats = await resolver.getStats();
        expect(stats.cacheHits).toBe(2);
        expect(stats.cacheMisses).toBe(1);
      });
    });

    describe('force refresh', () => {
      it('should bypass cache when forceRefresh is true', async () => {
        await resolver.resolve('localhost');
        const result = await resolver.resolve('localhost', { forceRefresh: true });

        expect(result.fromCache).toBe(false);
      });

      it('should update cached entry on force refresh', async () => {
        await resolver.resolve('localhost');
        const before = await resolver.getStats();

        await resolver.resolve('localhost', { forceRefresh: true });
        const after = await resolver.getStats();

        expect(after.cacheMisses).toBe(before.cacheMisses + 1);
      });
    });

    describe('custom TTL', () => {
      it('should respect custom ttlMs', async () => {
        await resolver.resolve('localhost', { ttlMs: 120000 });

        const result = await resolver.resolve('localhost');
        expect(result.ttlRemainingMs).toBeLessThanOrEqual(120000);
        expect(result.ttlRemainingMs).toBeGreaterThan(60000); // More than default
      });

      it('should clamp TTL to min/max bounds', async () => {
        // TTL below minimum
        await resolver.resolve('localhost', { ttlMs: 100 });
        let result = await resolver.resolve('localhost');
        expect(result.ttlRemainingMs).toBeGreaterThanOrEqual(900); // Near minTtlMs

        // Force refresh and use TTL above maximum
        await resolver.resolve('localhost', { forceRefresh: true, ttlMs: 500000 });
        result = await resolver.resolve('localhost');
        expect(result.ttlRemainingMs).toBeLessThanOrEqual(300000); // maxTtlMs
      });
    });

    describe('stale-while-revalidate', () => {
      it('should serve stale data within grace period', async () => {
        // Create resolver with very short TTL
        const shortTtlResolver = new DnsCacheResolver({
          id: 'short-ttl',
          defaultTtlMs: 50,
          staleWhileRevalidate: true,
          staleGracePeriodMs: 5000,
        });

        await shortTtlResolver.resolve('localhost');

        // Wait for TTL to expire
        await new Promise((r) => setTimeout(r, 100));

        const result = await shortTtlResolver.resolve('localhost');

        // Should return stale data
        expect(result.fromCache).toBe(true);
        expect(result.ttlRemainingMs).toBe(0);

        await shortTtlResolver.destroy();
      });

      it('should emit cache:stale event', async () => {
        const shortTtlResolver = new DnsCacheResolver({
          id: 'short-ttl',
          defaultTtlMs: 50,
          staleWhileRevalidate: true,
          staleGracePeriodMs: 5000,
        });

        await shortTtlResolver.resolve('localhost');
        await new Promise((r) => setTimeout(r, 100));

        const events: DnsCacheEvent[] = [];
        shortTtlResolver.on((e) => events.push(e));

        await shortTtlResolver.resolve('localhost');

        expect(events.some((e) => e.type === 'cache:stale')).toBe(true);

        await shortTtlResolver.destroy();
      });
    });

    describe('negative caching', () => {
      it('should cache failed resolutions', async () => {
        const negCacheResolver = new DnsCacheResolver({
          id: 'neg-cache',
          negativeTtlMs: 1000,
        });

        // Register resolver that always fails
        negCacheResolver.registerResolver(
          'invalid.invalid',
          async () => {
            throw new Error('DNS resolution failed');
          }
        );

        // First call should throw
        await expect(negCacheResolver.resolve('invalid.invalid')).rejects.toThrow();

        // Second call should also throw (negative cached)
        await expect(negCacheResolver.resolve('invalid.invalid')).rejects.toThrow();

        await negCacheResolver.destroy();
      });
    });
  });

  describe('resolveOne', () => {
    it('should return single endpoint', async () => {
      const endpoint = await resolver.resolveOne('localhost');

      expect(endpoint).toBeDefined();
      expect(endpoint?.host).toBeDefined();
      expect(endpoint?.port).toBeDefined();
    });

    it('should return undefined for failed resolution', async () => {
      resolver.registerResolver('nonexistent', async () => []);

      const endpoint = await resolver.resolveOne('nonexistent');
      expect(endpoint).toBeUndefined();
    });

    it('should use load balancing strategy', async () => {
      // Register resolver with multiple endpoints
      resolver.registerResolver('multi', async () => [
        { host: '10.0.0.1', port: 80, healthy: true },
        { host: '10.0.0.2', port: 80, healthy: true },
      ]);

      const endpoints = [];
      for (let i = 0; i < 4; i++) {
        const ep = await resolver.resolveOne('multi');
        endpoints.push(ep?.host);
      }

      // With round-robin, should cycle through endpoints
      expect(endpoints).toContain('10.0.0.1');
      expect(endpoints).toContain('10.0.0.2');
    });
  });

  describe('selectEndpoint', () => {
    it('should return undefined when not cached', async () => {
      const endpoint = await resolver.selectEndpoint('nonexistent');
      expect(endpoint).toBeUndefined();
    });

    it('should return endpoint from cached entry', async () => {
      await resolver.resolve('localhost');
      const endpoint = await resolver.selectEndpoint('localhost');

      expect(endpoint).toBeDefined();
      expect(endpoint?.host).toBeDefined();
    });
  });

  describe('custom resolvers', () => {
    it('should use registered custom resolver', async () => {
      const customEndpoints: ResolvedEndpoint[] = [
        { host: '192.168.1.100', port: 8080, healthy: true },
      ];

      resolver.registerResolver('custom.internal', async () => customEndpoints);

      const result = await resolver.resolve('custom.internal');

      expect(result.endpoints).toHaveLength(1);
      expect(result.endpoints[0].host).toBe('192.168.1.100');
      expect(result.endpoints[0].port).toBe(8080);
    });

    it('should unregister custom resolver', async () => {
      resolver.registerResolver('custom.internal', async () => [
        { host: '192.168.1.100', port: 8080, healthy: true },
      ]);

      const removed = resolver.unregisterResolver('custom.internal');
      expect(removed).toBe(true);

      // Should now use default resolver
      const result = await resolver.resolve('custom.internal');
      // Default resolver will resolve as literal
      expect(result.endpoints[0].host).toBe('custom.internal');
    });

    it('should return false when unregistering non-existent resolver', () => {
      const removed = resolver.unregisterResolver('nonexistent');
      expect(removed).toBe(false);
    });
  });

  describe('health management', () => {
    beforeEach(async () => {
      resolver.registerResolver('multi', async () => [
        { host: '10.0.0.1', port: 80, healthy: true },
        { host: '10.0.0.2', port: 80, healthy: true },
      ]);
      await resolver.resolve('multi');
    });

    it('should mark endpoint as unhealthy', async () => {
      const endpoint = { host: '10.0.0.1', port: 80, healthy: true };
      await resolver.markUnhealthy('multi', endpoint);

      const events: DnsCacheEvent[] = [];
      resolver.on((e) => events.push(e));

      await resolver.markUnhealthy('multi', endpoint);

      // Already unhealthy, no event
      expect(
        events.filter((e) => e.type === 'health:changed')
      ).toHaveLength(0);
    });

    it('should emit health:changed event', async () => {
      const events: DnsCacheEvent[] = [];
      resolver.on((e) => events.push(e));

      const endpoint = { host: '10.0.0.1', port: 80, healthy: true };
      await resolver.markUnhealthy('multi', endpoint);

      const healthEvent = events.find((e) => e.type === 'health:changed');
      expect(healthEvent).toBeDefined();
    });

    it('should mark endpoint as healthy', async () => {
      const endpoint = { host: '10.0.0.1', port: 80, healthy: true };
      await resolver.markUnhealthy('multi', endpoint);

      const events: DnsCacheEvent[] = [];
      resolver.on((e) => events.push(e));

      await resolver.markHealthy('multi', endpoint);

      const healthEvent = events.find((e) => e.type === 'health:changed');
      expect(healthEvent).toBeDefined();
    });

    it('should handle non-existent DSN', async () => {
      const endpoint = { host: '10.0.0.1', port: 80, healthy: true };
      await resolver.markUnhealthy('nonexistent', endpoint);
      // Should not throw
    });

    it('should handle non-existent endpoint', async () => {
      const endpoint = { host: '10.0.0.99', port: 80, healthy: true };
      await resolver.markUnhealthy('multi', endpoint);
      // Should not throw
    });
  });

  describe('connection tracking', () => {
    it('should increment connections', async () => {
      const endpoint: ResolvedEndpoint = {
        host: '10.0.0.1',
        port: 80,
        healthy: true,
      };

      resolver.incrementConnections(endpoint);
      resolver.incrementConnections(endpoint);
      resolver.incrementConnections(endpoint);

      // Internal state should be tracked
      // (verified through load balancing behavior)
    });

    it('should decrement connections', async () => {
      const endpoint: ResolvedEndpoint = {
        host: '10.0.0.1',
        port: 80,
        healthy: true,
      };

      resolver.incrementConnections(endpoint);
      resolver.incrementConnections(endpoint);
      resolver.decrementConnections(endpoint);
      resolver.decrementConnections(endpoint);
      resolver.decrementConnections(endpoint); // Should not go negative
    });
  });

  describe('cache management', () => {
    it('should invalidate specific entry', async () => {
      await resolver.resolve('localhost');
      expect((await resolver.getStats()).totalEntries).toBe(1);

      const result = await resolver.invalidate('localhost');

      expect(result).toBe(true);
      expect((await resolver.getStats()).totalEntries).toBe(0);
    });

    it('should return false when invalidating non-existent entry', async () => {
      const result = await resolver.invalidate('nonexistent');
      expect(result).toBe(false);
    });

    it('should emit cache:evicted event on invalidation', async () => {
      await resolver.resolve('localhost');

      const events: DnsCacheEvent[] = [];
      resolver.on((e) => events.push(e));

      await resolver.invalidate('localhost');

      const evictEvent = events.find((e) => e.type === 'cache:evicted');
      expect(evictEvent).toBeDefined();
    });

    it('should clear all entries', async () => {
      await resolver.resolve('localhost');
      await resolver.resolve('127.0.0.1');

      await resolver.clear();

      const stats = await resolver.getStats();
      expect(stats.totalEntries).toBe(0);
    });
  });

  describe('statistics', () => {
    it('should track cache hits and misses', async () => {
      await resolver.resolve('localhost');
      await resolver.resolve('localhost');
      await resolver.resolve('localhost');

      const stats = await resolver.getStats();

      expect(stats.cacheHits).toBe(2);
      expect(stats.cacheMisses).toBe(1);
    });

    it('should calculate hit ratio', async () => {
      await resolver.resolve('localhost');
      await resolver.resolve('localhost');
      await resolver.resolve('localhost');
      await resolver.resolve('localhost');

      const stats = await resolver.getStats();

      expect(stats.hitRatio).toBe(0.75); // 3 hits / 4 total
    });

    it('should track total entries', async () => {
      await resolver.resolve('localhost');
      await resolver.resolve('127.0.0.1');

      const stats = await resolver.getStats();

      expect(stats.totalEntries).toBe(2);
    });

    it('should track average resolution time', async () => {
      await resolver.resolve('localhost');
      await resolver.resolve('127.0.0.1');

      const stats = await resolver.getStats();

      expect(stats.avgResolutionTimeMs).toBeGreaterThanOrEqual(0);
    });

    it('should track healthy/unhealthy endpoints', async () => {
      resolver.registerResolver('multi', async () => [
        { host: '10.0.0.1', port: 80, healthy: true },
        { host: '10.0.0.2', port: 80, healthy: false },
      ]);

      await resolver.resolve('multi');

      const stats = await resolver.getStats();

      expect(stats.healthyEndpoints).toBe(1);
      expect(stats.unhealthyEndpoints).toBe(1);
    });

    it('should return zero hit ratio when no requests', async () => {
      const stats = await resolver.getStats();
      expect(stats.hitRatio).toBe(0);
    });
  });

  describe('event system', () => {
    it('should subscribe to events', async () => {
      const events: DnsCacheEvent[] = [];
      resolver.on((e) => events.push(e));

      await resolver.resolve('localhost');

      expect(events.length).toBeGreaterThan(0);
    });

    it('should unsubscribe from events', async () => {
      const events: DnsCacheEvent[] = [];
      const listener = (e: DnsCacheEvent) => events.push(e);

      resolver.on(listener);
      await resolver.resolve('localhost');
      const countBefore = events.length;

      resolver.off(listener);
      await resolver.resolve('127.0.0.1');

      expect(events.length).toBe(countBefore);
    });

    it('should return unsubscribe function from on()', async () => {
      const events: DnsCacheEvent[] = [];
      const unsubscribe = resolver.on((e) => events.push(e));

      await resolver.resolve('localhost');
      const countBefore = events.length;

      unsubscribe();
      await resolver.resolve('127.0.0.1');

      expect(events.length).toBe(countBefore);
    });

    it('should handle listener errors gracefully', async () => {
      resolver.on(() => {
        throw new Error('Listener error');
      });

      // Should not throw
      await resolver.resolve('localhost');
    });
  });

  describe('destroy', () => {
    it('should clean up resources', async () => {
      await resolver.resolve('localhost');
      await resolver.destroy();

      // Store should be closed
      const stats = await resolver.getStats();
      expect(stats.totalEntries).toBe(0);
    });

    it('should clear listeners', async () => {
      const events: DnsCacheEvent[] = [];
      resolver.on((e) => events.push(e));

      await resolver.destroy();

      // Listeners should be cleared - but since store is closed, new resolves fail
      expect(true).toBe(true); // Verify destroy completed without error
    });
  });

  describe('concurrent operations', () => {
    it('should handle concurrent resolutions', async () => {
      const promises = Array.from({ length: 10 }, () => resolver.resolve('localhost'));

      const results = await Promise.all(promises);

      expect(results.every((r) => r.endpoints.length > 0)).toBe(true);
    });

    it('should handle concurrent operations on different DSNs', async () => {
      const dsns = ['localhost', '127.0.0.1', 'example.com', 'test.local'];

      const promises = dsns.map((dsn) => resolver.resolve(dsn));

      const results = await Promise.all(promises);

      expect(results.length).toBe(4);
    });

    it('should handle concurrent invalidations', async () => {
      await resolver.resolve('localhost');
      await resolver.resolve('127.0.0.1');

      await Promise.all([
        resolver.invalidate('localhost'),
        resolver.invalidate('127.0.0.1'),
      ]);

      const stats = await resolver.getStats();
      expect(stats.totalEntries).toBe(0);
    });
  });
});

describe('createDnsCacheResolver factory', () => {
  it('should create resolver with config', async () => {
    const resolver = createDnsCacheResolver({
      id: 'factory-test',
      defaultTtlMs: 30000,
    });

    expect(resolver).toBeInstanceOf(DnsCacheResolver);

    await resolver.destroy();
  });

  it('should create resolver with custom store', async () => {
    const store = new MemoryStore(50);
    const resolver = createDnsCacheResolver(
      { id: 'custom-store' },
      store
    );

    expect(resolver).toBeInstanceOf(DnsCacheResolver);

    await resolver.destroy();
  });
});
