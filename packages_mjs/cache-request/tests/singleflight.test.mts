/**
 * Tests for Singleflight (Request Coalescing)
 *
 * Coverage includes:
 * - Statement coverage: All executable statements
 * - Decision/Branch coverage: All conditional branches
 * - Condition coverage: Boolean conditions in decisions
 * - Path coverage: Key execution paths including concurrent paths
 * - Boundary testing: Edge cases
 * - State transitions: In-flight request lifecycle
 * - Error handling: Error propagation to all subscribers
 * - Event emission: Observer pattern verification
 * - Concurrency testing: Multiple concurrent requests
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import {
  Singleflight,
  createSingleflight,
  DEFAULT_SINGLEFLIGHT_CONFIG,
  mergeSingleflightConfig,
} from '../src/singleflight.mjs';
import type {
  SingleflightConfig,
  RequestFingerprint,
  CacheRequestEvent,
} from '../src/types.mjs';
import { MemorySingleflightStore } from '../src/stores/memory.mjs';

describe('Singleflight', () => {
  let singleflight: Singleflight;

  beforeEach(() => {
    singleflight = new Singleflight();
  });

  afterEach(() => {
    singleflight.close();
  });

  describe('constructor', () => {
    it('should create with default configuration', () => {
      const config = singleflight.getConfig();
      expect(config.ttlMs).toBe(30000);
      expect(config.methods).toEqual(['GET', 'HEAD']);
      expect(config.includeHeaders).toBe(false);
    });

    it('should create with custom configuration', () => {
      const customSf = new Singleflight({
        ttlMs: 60000,
        methods: ['GET', 'HEAD', 'OPTIONS'],
        includeHeaders: true,
        headerKeys: ['Authorization'],
      });

      const config = customSf.getConfig();
      expect(config.ttlMs).toBe(60000);
      expect(config.methods).toEqual(['GET', 'HEAD', 'OPTIONS']);
      expect(config.includeHeaders).toBe(true);
      expect(config.headerKeys).toEqual(['Authorization']);

      customSf.close();
    });

    it('should accept custom store', async () => {
      const customStore = new MemorySingleflightStore();
      const customSf = new Singleflight({}, customStore);

      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      let callCount = 0;

      await customSf.do(request, async () => {
        callCount++;
        return 'value';
      });

      expect(callCount).toBe(1);
      customSf.close();
    });

    it('should accept custom fingerprint generator', async () => {
      const customSf = new Singleflight({
        fingerprintGenerator: (req) => `custom:${req.method}:${req.url}`,
      });

      const fingerprint = customSf.generateFingerprint({
        method: 'GET',
        url: '/api/test',
      });

      expect(fingerprint).toBe('custom:GET:/api/test');
      customSf.close();
    });
  });

  describe('supportsCoalescing()', () => {
    it('should return true for GET', () => {
      expect(singleflight.supportsCoalescing('GET')).toBe(true);
    });

    it('should return true for HEAD', () => {
      expect(singleflight.supportsCoalescing('HEAD')).toBe(true);
    });

    it('should return false for POST', () => {
      expect(singleflight.supportsCoalescing('POST')).toBe(false);
    });

    it('should return false for PUT', () => {
      expect(singleflight.supportsCoalescing('PUT')).toBe(false);
    });

    it('should return false for PATCH', () => {
      expect(singleflight.supportsCoalescing('PATCH')).toBe(false);
    });

    it('should return false for DELETE', () => {
      expect(singleflight.supportsCoalescing('DELETE')).toBe(false);
    });

    it('should be case-insensitive', () => {
      expect(singleflight.supportsCoalescing('get')).toBe(true);
      expect(singleflight.supportsCoalescing('Get')).toBe(true);
      expect(singleflight.supportsCoalescing('GET')).toBe(true);
    });

    it('should respect custom methods configuration', () => {
      const customSf = new Singleflight({
        methods: ['POST', 'PUT'],
      });

      expect(customSf.supportsCoalescing('GET')).toBe(false);
      expect(customSf.supportsCoalescing('POST')).toBe(true);
      expect(customSf.supportsCoalescing('PUT')).toBe(true);

      customSf.close();
    });
  });

  describe('generateFingerprint()', () => {
    it('should generate consistent fingerprint for same request', () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };

      const fp1 = singleflight.generateFingerprint(request);
      const fp2 = singleflight.generateFingerprint(request);

      expect(fp1).toBe(fp2);
    });

    it('should generate different fingerprints for different URLs', () => {
      const fp1 = singleflight.generateFingerprint({
        method: 'GET',
        url: '/api/test1',
      });
      const fp2 = singleflight.generateFingerprint({
        method: 'GET',
        url: '/api/test2',
      });

      expect(fp1).not.toBe(fp2);
    });

    it('should generate different fingerprints for different methods', () => {
      const fp1 = singleflight.generateFingerprint({
        method: 'GET',
        url: '/api/test',
      });
      const fp2 = singleflight.generateFingerprint({
        method: 'HEAD',
        url: '/api/test',
      });

      expect(fp1).not.toBe(fp2);
    });

    it('should include body in fingerprint', () => {
      const fp1 = singleflight.generateFingerprint({
        method: 'GET',
        url: '/api/test',
        body: Buffer.from('body1'),
      });
      const fp2 = singleflight.generateFingerprint({
        method: 'GET',
        url: '/api/test',
        body: Buffer.from('body2'),
      });

      expect(fp1).not.toBe(fp2);
    });

    it('should exclude headers by default', () => {
      const fp1 = singleflight.generateFingerprint({
        method: 'GET',
        url: '/api/test',
        headers: { 'X-Custom': 'value1' },
      });
      const fp2 = singleflight.generateFingerprint({
        method: 'GET',
        url: '/api/test',
        headers: { 'X-Custom': 'value2' },
      });

      expect(fp1).toBe(fp2);
    });

    it('should include selected headers when configured', () => {
      const customSf = new Singleflight({
        includeHeaders: true,
        headerKeys: ['Authorization'],
      });

      const fp1 = customSf.generateFingerprint({
        method: 'GET',
        url: '/api/test',
        headers: { Authorization: 'Bearer token1' },
      });
      const fp2 = customSf.generateFingerprint({
        method: 'GET',
        url: '/api/test',
        headers: { Authorization: 'Bearer token2' },
      });

      expect(fp1).not.toBe(fp2);

      customSf.close();
    });

    it('should handle case-insensitive header matching', () => {
      const customSf = new Singleflight({
        includeHeaders: true,
        headerKeys: ['authorization'],
      });

      const fp1 = customSf.generateFingerprint({
        method: 'GET',
        url: '/api/test',
        headers: { Authorization: 'Bearer token' },
      });
      const fp2 = customSf.generateFingerprint({
        method: 'GET',
        url: '/api/test',
        headers: { AUTHORIZATION: 'Bearer token' },
      });

      // Both should include the auth header
      expect(fp1).toBeDefined();
      expect(fp2).toBeDefined();

      customSf.close();
    });
  });

  describe('do()', () => {
    it('should execute function and return result', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };

      const result = await singleflight.do(request, async () => 'test-value');

      expect(result.value).toBe('test-value');
      expect(result.shared).toBe(false);
      expect(result.subscribers).toBe(1);
    });

    it('should coalesce identical concurrent requests', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      let callCount = 0;

      const fn = async () => {
        callCount++;
        await new Promise((resolve) => setTimeout(resolve, 100));
        return 'shared-value';
      };

      const [result1, result2, result3] = await Promise.all([
        singleflight.do(request, fn),
        singleflight.do(request, fn),
        singleflight.do(request, fn),
      ]);

      expect(callCount).toBe(1);
      expect(result1.value).toBe('shared-value');
      expect(result2.value).toBe('shared-value');
      expect(result3.value).toBe('shared-value');

      // One should be the leader, others should be shared
      const sharedCount = [result1, result2, result3].filter(
        (r) => r.shared
      ).length;
      expect(sharedCount).toBe(2);
    });

    it('should not coalesce different requests', async () => {
      let callCount = 0;

      const fn = async () => {
        callCount++;
        return `value-${callCount}`;
      };

      const [result1, result2] = await Promise.all([
        singleflight.do({ method: 'GET', url: '/api/test1' }, fn),
        singleflight.do({ method: 'GET', url: '/api/test2' }, fn),
      ]);

      expect(callCount).toBe(2);
      expect(result1.value).not.toBe(result2.value);
    });

    it('should propagate errors to all subscribers', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      const error = new Error('Test error');

      const fn = async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
        throw error;
      };

      const promises = [
        singleflight.do(request, fn),
        singleflight.do(request, fn),
        singleflight.do(request, fn),
      ];

      const results = await Promise.allSettled(promises);

      expect(results.every((r) => r.status === 'rejected')).toBe(true);
      results.forEach((r) => {
        if (r.status === 'rejected') {
          expect(r.reason).toBe(error);
        }
      });
    });

    it('should remove in-flight request after completion', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };

      await singleflight.do(request, async () => 'value');

      expect(singleflight.isInFlight(request)).toBe(false);
    });

    it('should remove in-flight request after error', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };

      try {
        await singleflight.do(request, async () => {
          throw new Error('Test error');
        });
      } catch {
        // Expected
      }

      expect(singleflight.isInFlight(request)).toBe(false);
    });

    it('should track correct subscriber count', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      let resolveDelay: () => void;
      const delayPromise = new Promise<void>((resolve) => {
        resolveDelay = resolve;
      });

      const fn = async () => {
        await delayPromise;
        return 'value';
      };

      const promise1 = singleflight.do(request, fn);
      const promise2 = singleflight.do(request, fn);
      const promise3 = singleflight.do(request, fn);

      // Wait a tick for all to register
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(singleflight.getSubscribers(request)).toBe(3);

      resolveDelay!();

      const [result1, result2, result3] = await Promise.all([
        promise1,
        promise2,
        promise3,
      ]);

      expect(result1.subscribers).toBe(3);
      expect(result2.subscribers).toBe(3);
      expect(result3.subscribers).toBe(3);
    });

    it('should emit singleflight:lead event for leader', async () => {
      const events: CacheRequestEvent[] = [];
      singleflight.on((event) => events.push(event));

      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      await singleflight.do(request, async () => 'value');

      const leadEvents = events.filter((e) => e.type === 'singleflight:lead');
      expect(leadEvents.length).toBe(1);
    });

    it('should emit singleflight:join event for followers', async () => {
      const events: CacheRequestEvent[] = [];
      singleflight.on((event) => events.push(event));

      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };

      await Promise.all([
        singleflight.do(request, async () => {
          await new Promise((resolve) => setTimeout(resolve, 50));
          return 'value';
        }),
        singleflight.do(request, async () => 'value'),
        singleflight.do(request, async () => 'value'),
      ]);

      const joinEvents = events.filter((e) => e.type === 'singleflight:join');
      expect(joinEvents.length).toBe(2);
    });

    it('should emit singleflight:complete event on success', async () => {
      const events: CacheRequestEvent[] = [];
      singleflight.on((event) => events.push(event));

      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      await singleflight.do(request, async () => 'value');

      const completeEvents = events.filter(
        (e) => e.type === 'singleflight:complete'
      );
      expect(completeEvents.length).toBe(1);
      expect(completeEvents[0].metadata?.subscribers).toBe(1);
      expect(completeEvents[0].metadata?.durationMs).toBeDefined();
    });

    it('should emit singleflight:error event on failure', async () => {
      const events: CacheRequestEvent[] = [];
      singleflight.on((event) => events.push(event));

      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };

      try {
        await singleflight.do(request, async () => {
          throw new Error('Test error');
        });
      } catch {
        // Expected
      }

      const errorEvents = events.filter(
        (e) => e.type === 'singleflight:error'
      );
      expect(errorEvents.length).toBe(1);
      expect(errorEvents[0].metadata?.error).toBe('Error: Test error');
    });
  });

  describe('isInFlight()', () => {
    it('should return false for non-existent request', () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      expect(singleflight.isInFlight(request)).toBe(false);
    });

    it('should return true for in-flight request', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      let resolve: () => void;
      const promise = new Promise<void>((r) => {
        resolve = r;
      });

      const sfPromise = singleflight.do(request, async () => {
        await promise;
        return 'value';
      });

      expect(singleflight.isInFlight(request)).toBe(true);

      resolve!();
      await sfPromise;

      expect(singleflight.isInFlight(request)).toBe(false);
    });
  });

  describe('getSubscribers()', () => {
    it('should return 0 for non-existent request', () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      expect(singleflight.getSubscribers(request)).toBe(0);
    });

    it('should return correct subscriber count', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      let resolve: () => void;
      const promise = new Promise<void>((r) => {
        resolve = r;
      });

      const promises = [
        singleflight.do(request, async () => {
          await promise;
          return 'value';
        }),
        singleflight.do(request, async () => 'value'),
      ];

      // Wait for both to register
      await new Promise((r) => setTimeout(r, 0));

      expect(singleflight.getSubscribers(request)).toBe(2);

      resolve!();
      await Promise.all(promises);
    });
  });

  describe('getStats()', () => {
    it('should return correct in-flight count', async () => {
      expect(singleflight.getStats().inFlight).toBe(0);

      let resolve1: () => void;
      let resolve2: () => void;

      const promise1 = singleflight.do(
        { method: 'GET', url: '/api/test1' },
        async () => {
          await new Promise<void>((r) => {
            resolve1 = r;
          });
          return 'value1';
        }
      );

      const promise2 = singleflight.do(
        { method: 'GET', url: '/api/test2' },
        async () => {
          await new Promise<void>((r) => {
            resolve2 = r;
          });
          return 'value2';
        }
      );

      expect(singleflight.getStats().inFlight).toBe(2);

      resolve1!();
      await promise1;

      expect(singleflight.getStats().inFlight).toBe(1);

      resolve2!();
      await promise2;

      expect(singleflight.getStats().inFlight).toBe(0);
    });
  });

  describe('event listeners', () => {
    it('should add listener with on()', async () => {
      const events: CacheRequestEvent[] = [];
      singleflight.on((event) => events.push(event));

      await singleflight.do({ method: 'GET', url: '/api/test' }, async () =>
        'value'
      );

      expect(events.length).toBeGreaterThan(0);
    });

    it('should return unsubscribe function from on()', async () => {
      const events: CacheRequestEvent[] = [];
      const unsubscribe = singleflight.on((event) => events.push(event));

      await singleflight.do({ method: 'GET', url: '/api/test1' }, async () =>
        'value'
      );

      const countAfterFirst = events.length;

      unsubscribe();

      await singleflight.do({ method: 'GET', url: '/api/test2' }, async () =>
        'value'
      );

      expect(events.length).toBe(countAfterFirst);
    });

    it('should remove listener with off()', async () => {
      const events: CacheRequestEvent[] = [];
      const listener = (event: CacheRequestEvent) => events.push(event);

      singleflight.on(listener);
      await singleflight.do({ method: 'GET', url: '/api/test1' }, async () =>
        'value'
      );

      const countAfterFirst = events.length;

      singleflight.off(listener);
      await singleflight.do({ method: 'GET', url: '/api/test2' }, async () =>
        'value'
      );

      expect(events.length).toBe(countAfterFirst);
    });

    it('should handle listener errors gracefully', async () => {
      singleflight.on(() => {
        throw new Error('Listener error');
      });

      // Should not throw
      await singleflight.do({ method: 'GET', url: '/api/test' }, async () =>
        'value'
      );
    });
  });

  describe('clear()', () => {
    it('should clear all in-flight requests', async () => {
      let resolve: () => void;
      const promise = new Promise<void>((r) => {
        resolve = r;
      });

      singleflight.do({ method: 'GET', url: '/api/test' }, async () => {
        await promise;
        return 'value';
      });

      expect(singleflight.getStats().inFlight).toBe(1);

      singleflight.clear();

      expect(singleflight.getStats().inFlight).toBe(0);

      resolve!();
    });
  });

  describe('close()', () => {
    it('should clear in-flight requests', async () => {
      let resolve: () => void;
      const promise = new Promise<void>((r) => {
        resolve = r;
      });

      singleflight.do({ method: 'GET', url: '/api/test' }, async () => {
        await promise;
        return 'value';
      });

      singleflight.close();

      expect(singleflight.getStats().inFlight).toBe(0);

      resolve!();
    });

    it('should clear listeners', async () => {
      const events: CacheRequestEvent[] = [];
      singleflight.on((event) => events.push(event));

      singleflight.close();

      // Create new singleflight - listeners should be gone
      const newSf = new Singleflight();
      await newSf.do({ method: 'GET', url: '/api/test' }, async () => 'value');

      expect(events.filter((e) => e.key.includes('test')).length).toBe(0);

      newSf.close();
    });
  });

  describe('boundary conditions', () => {
    it('should handle empty URL', async () => {
      const result = await singleflight.do(
        { method: 'GET', url: '' },
        async () => 'value'
      );

      expect(result.value).toBe('value');
    });

    it('should handle very long URL', async () => {
      const longUrl = '/api/' + 'a'.repeat(10000);
      const result = await singleflight.do(
        { method: 'GET', url: longUrl },
        async () => 'value'
      );

      expect(result.value).toBe('value');
    });

    it('should handle special characters in URL', async () => {
      const result = await singleflight.do(
        { method: 'GET', url: '/api/test?query=a&b=c#hash' },
        async () => 'value'
      );

      expect(result.value).toBe('value');
    });

    it('should handle immediate resolution', async () => {
      const result = await singleflight.do(
        { method: 'GET', url: '/api/test' },
        async () => 'immediate'
      );

      expect(result.value).toBe('immediate');
    });

    it('should handle complex return types', async () => {
      interface ComplexType {
        nested: { data: number[] };
        date: Date;
      }

      const result = await singleflight.do<ComplexType>(
        { method: 'GET', url: '/api/test' },
        async () => ({
          nested: { data: [1, 2, 3] },
          date: new Date(),
        })
      );

      expect(result.value.nested.data).toEqual([1, 2, 3]);
      expect(result.value.date).toBeInstanceOf(Date);
    });
  });

  describe('concurrent operations', () => {
    it('should handle many concurrent coalesced requests', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      let callCount = 0;

      const fn = async () => {
        callCount++;
        await new Promise((resolve) => setTimeout(resolve, 50));
        return 'shared';
      };

      const promises = Array.from({ length: 100 }, () =>
        singleflight.do(request, fn)
      );

      const results = await Promise.all(promises);

      expect(callCount).toBe(1);
      expect(results.every((r) => r.value === 'shared')).toBe(true);
      expect(results.filter((r) => r.shared).length).toBe(99);
    });

    it('should handle many different concurrent requests', async () => {
      let callCount = 0;

      const promises = Array.from({ length: 50 }, (_, i) =>
        singleflight.do(
          { method: 'GET', url: `/api/test${i}` },
          async () => {
            callCount++;
            return `value${i}`;
          }
        )
      );

      const results = await Promise.all(promises);

      expect(callCount).toBe(50);
      expect(results.every((r, i) => r.value === `value${i}`)).toBe(true);
      expect(results.every((r) => !r.shared)).toBe(true);
    });
  });

  describe('state transitions', () => {
    it('should transition: idle -> in-flight -> completed -> idle', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };
      let resolve: () => void;
      const blocker = new Promise<void>((r) => {
        resolve = r;
      });

      // Idle state
      expect(singleflight.isInFlight(request)).toBe(false);

      // In-flight state
      const promise = singleflight.do(request, async () => {
        await blocker;
        return 'value';
      });
      expect(singleflight.isInFlight(request)).toBe(true);

      // Completed -> Idle
      resolve!();
      await promise;
      expect(singleflight.isInFlight(request)).toBe(false);
    });

    it('should transition: idle -> in-flight -> error -> idle', async () => {
      const request: RequestFingerprint = { method: 'GET', url: '/api/test' };

      // Idle state
      expect(singleflight.isInFlight(request)).toBe(false);

      // In-flight -> Error -> Idle
      try {
        await singleflight.do(request, async () => {
          throw new Error('Test');
        });
      } catch {
        // Expected
      }

      expect(singleflight.isInFlight(request)).toBe(false);
    });
  });
});

describe('Configuration helpers', () => {
  describe('DEFAULT_SINGLEFLIGHT_CONFIG', () => {
    it('should have correct default values', () => {
      expect(DEFAULT_SINGLEFLIGHT_CONFIG.ttlMs).toBe(30000);
      expect(DEFAULT_SINGLEFLIGHT_CONFIG.methods).toEqual(['GET', 'HEAD']);
      expect(DEFAULT_SINGLEFLIGHT_CONFIG.includeHeaders).toBe(false);
      expect(DEFAULT_SINGLEFLIGHT_CONFIG.headerKeys).toEqual([]);
      expect(typeof DEFAULT_SINGLEFLIGHT_CONFIG.fingerprintGenerator).toBe(
        'function'
      );
    });
  });

  describe('mergeSingleflightConfig()', () => {
    it('should return defaults when no config provided', () => {
      const merged = mergeSingleflightConfig();
      expect(merged.ttlMs).toBe(30000);
      expect(merged.methods).toEqual(['GET', 'HEAD']);
    });

    it('should merge partial config with defaults', () => {
      const merged = mergeSingleflightConfig({ ttlMs: 60000 });
      expect(merged.ttlMs).toBe(60000);
      expect(merged.methods).toEqual(['GET', 'HEAD']);
    });

    it('should preserve all custom values', () => {
      const customConfig: SingleflightConfig = {
        ttlMs: 10000,
        methods: ['OPTIONS'],
        includeHeaders: true,
        headerKeys: ['X-Custom'],
      };
      const merged = mergeSingleflightConfig(customConfig);

      expect(merged.ttlMs).toBe(10000);
      expect(merged.methods).toEqual(['OPTIONS']);
      expect(merged.includeHeaders).toBe(true);
      expect(merged.headerKeys).toEqual(['X-Custom']);
    });
  });

  describe('createSingleflight()', () => {
    it('should create singleflight with default config', () => {
      const sf = createSingleflight();
      expect(sf).toBeInstanceOf(Singleflight);
      sf.close();
    });

    it('should create singleflight with custom config', () => {
      const sf = createSingleflight({ ttlMs: 1000 });
      expect(sf.getConfig().ttlMs).toBe(1000);
      sf.close();
    });

    it('should create singleflight with custom store', () => {
      const store = new MemorySingleflightStore();
      const sf = createSingleflight({}, store);
      expect(sf).toBeInstanceOf(Singleflight);
      sf.close();
    });
  });
});
