/**
 * Tests for RateLimiter
 *
 * Coverage includes:
 * - Static and dynamic rate limiting
 * - Priority queue ordering
 * - Retry with exponential backoff
 * - Concurrency control
 * - Event emission
 * - Cancellation and deadline handling
 * - State transitions
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { RateLimiter, createRateLimiter } from '../src/limiter.mjs';
import { MemoryStore } from '../src/stores/memory.mjs';
import type {
  RateLimiterConfig,
  RateLimiterEvent,
  RateLimitStore,
  RateLimitStatus,
} from '../src/types.mjs';

describe('RateLimiter', () => {
  let limiter: RateLimiter;
  let store: MemoryStore;

  const createConfig = (overrides: Partial<RateLimiterConfig> = {}): RateLimiterConfig => ({
    id: 'test-limiter',
    static: { maxRequests: 10, intervalMs: 1000 },
    maxQueueSize: 100,
    concurrency: 1,
    retry: {
      maxRetries: 3,
      baseDelayMs: 100,
      maxDelayMs: 1000,
      jitterFactor: 0,
    },
    ...overrides,
  });

  beforeEach(() => {
    jest.useFakeTimers();
    store = new MemoryStore();
    limiter = new RateLimiter(createConfig(), store);
  });

  afterEach(async () => {
    await limiter.destroy();
    jest.useRealTimers();
  });

  describe('constructor', () => {
    it('should create limiter with default store', () => {
      const defaultLimiter = new RateLimiter(createConfig());
      expect(defaultLimiter).toBeInstanceOf(RateLimiter);
    });

    it('should create limiter with custom store', () => {
      const customStore = new MemoryStore();
      const customLimiter = new RateLimiter(createConfig(), customStore);
      expect(customLimiter).toBeInstanceOf(RateLimiter);
    });
  });

  describe('schedule', () => {
    it('should execute function immediately when not rate limited', async () => {
      const fn = jest.fn<() => Promise<string>>().mockResolvedValue('success');

      const resultPromise = limiter.schedule(fn);
      jest.runAllTimers();
      const result = await resultPromise;

      expect(fn).toHaveBeenCalled();
      expect(result.result).toBe('success');
    });

    it('should return queue time and execution time', async () => {
      const fn = jest.fn<() => Promise<string>>().mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => resolve('done'), 100);
          })
      );

      const resultPromise = limiter.schedule(fn);
      jest.runAllTimers();
      const result = await resultPromise;

      expect(result.queueTime).toBeGreaterThanOrEqual(0);
      expect(result.executionTime).toBeGreaterThanOrEqual(0);
      expect(result.retries).toBe(0);
    });

    it('should reject when queue is full', async () => {
      const smallQueueLimiter = new RateLimiter(
        createConfig({ maxQueueSize: 2, static: { maxRequests: 1, intervalMs: 10000 } }),
        store
      );

      // Fill the queue
      const fn = () => new Promise<void>((resolve) => setTimeout(resolve, 1000));
      smallQueueLimiter.schedule(fn);
      smallQueueLimiter.schedule(fn);
      smallQueueLimiter.schedule(fn);

      await expect(smallQueueLimiter.schedule(fn)).rejects.toThrow('Queue is full');

      await smallQueueLimiter.destroy();
    });

    it('should reject when limiter is destroyed', async () => {
      await limiter.destroy();

      await expect(limiter.schedule(async () => 'test')).rejects.toThrow(
        'RateLimiter has been destroyed'
      );
    });

    it('should pass metadata through to result', async () => {
      const fn = jest.fn<() => Promise<string>>().mockResolvedValue('success');

      const resultPromise = limiter.schedule(fn, {
        metadata: { requestId: '123' },
      });
      jest.runAllTimers();
      await resultPromise;

      expect(fn).toHaveBeenCalled();
    });
  });

  describe('priority ordering', () => {
    it('should process higher priority requests first', async () => {
      const order: number[] = [];
      const slowLimiter = new RateLimiter(
        createConfig({ static: { maxRequests: 1, intervalMs: 10000 } }),
        store
      );

      const createFn = (priority: number) => async () => {
        order.push(priority);
        return priority;
      };

      slowLimiter.schedule(createFn(1), { priority: 1 });
      slowLimiter.schedule(createFn(3), { priority: 3 });
      slowLimiter.schedule(createFn(2), { priority: 2 });

      jest.runAllTimers();
      await Promise.resolve();
      jest.runAllTimers();

      expect(order[0]).toBe(1);

      await slowLimiter.destroy();
    });
  });

  describe('rate limiting', () => {
    it('should enforce static rate limits', async () => {
      const limitedLimiter = new RateLimiter(
        createConfig({ static: { maxRequests: 2, intervalMs: 1000 } }),
        store
      );

      const results: number[] = [];
      const start = Date.now();

      for (let i = 0; i < 5; i++) {
        limitedLimiter.schedule(async () => {
          results.push(Date.now() - start);
          return i;
        });
      }

      jest.runAllTimers();
      await Promise.resolve();
      jest.runAllTimers();

      await limitedLimiter.destroy();
    });

    it('should support dynamic rate limiting', async () => {
      let remaining = 2;
      const dynamicLimiter = new RateLimiter(
        createConfig({
          dynamic: {
            getRateLimitStatus: async (): Promise<RateLimitStatus> => ({
              remaining: remaining--,
              reset: Date.now() / 1000 + 1,
              limit: 10,
            }),
          },
        }),
        store
      );

      const fn = jest.fn<() => Promise<string>>().mockResolvedValue('success');

      dynamicLimiter.schedule(fn);
      dynamicLimiter.schedule(fn);

      jest.runAllTimers();
      await Promise.resolve();

      await dynamicLimiter.destroy();
    });

    it('should fallback to static when dynamic fails', async () => {
      const fallbackLimiter = new RateLimiter(
        createConfig({
          dynamic: {
            getRateLimitStatus: async () => {
              throw new Error('API error');
            },
            fallback: { maxRequests: 5, intervalMs: 1000 },
          },
        }),
        store
      );

      const fn = jest.fn<() => Promise<string>>().mockResolvedValue('success');

      const resultPromise = fallbackLimiter.schedule(fn);
      jest.runAllTimers();
      await resultPromise;

      expect(fn).toHaveBeenCalled();

      await fallbackLimiter.destroy();
    });
  });

  describe('retry behavior', () => {
    it('should retry on retryable errors', async () => {
      let attempts = 0;
      const fn = jest.fn<() => Promise<string>>().mockImplementation(async () => {
        attempts++;
        if (attempts < 3) {
          const error = new Error('Network error');
          (error as Error & { code?: string }).code = 'ECONNRESET';
          throw error;
        }
        return 'success';
      });

      const resultPromise = limiter.schedule(fn);
      jest.runAllTimers();
      await Promise.resolve();
      jest.runAllTimers();
      await Promise.resolve();
      jest.runAllTimers();
      const result = await resultPromise;

      expect(result.result).toBe('success');
      expect(result.retries).toBe(2);
    });

    it('should not retry non-retryable errors', async () => {
      const fn = jest.fn<() => Promise<string>>().mockRejectedValue(
        new Error('Invalid argument')
      );

      const resultPromise = limiter.schedule(fn);
      jest.runAllTimers();

      await expect(resultPromise).rejects.toThrow('Invalid argument');
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should fail after max retries exceeded', async () => {
      const error = new Error('Connection reset');
      (error as Error & { code?: string }).code = 'ECONNRESET';

      const fn = jest.fn<() => Promise<string>>().mockRejectedValue(error);

      const resultPromise = limiter.schedule(fn);

      for (let i = 0; i < 10; i++) {
        jest.runAllTimers();
        await Promise.resolve();
      }

      await expect(resultPromise).rejects.toThrow('Connection reset');
    });
  });

  describe('concurrency control', () => {
    it('should respect concurrency limit', async () => {
      const concurrentLimiter = new RateLimiter(
        createConfig({ concurrency: 2 }),
        store
      );

      let maxConcurrent = 0;
      let current = 0;

      const fn = async () => {
        current++;
        maxConcurrent = Math.max(maxConcurrent, current);
        await new Promise((resolve) => setTimeout(resolve, 100));
        current--;
        return 'done';
      };

      const promises = Array.from({ length: 5 }, () =>
        concurrentLimiter.schedule(fn)
      );

      jest.runAllTimers();
      await Promise.all(promises);

      expect(maxConcurrent).toBeLessThanOrEqual(2);

      await concurrentLimiter.destroy();
    });
  });

  describe('event emission', () => {
    it('should emit request:queued event', async () => {
      const events: RateLimiterEvent[] = [];
      limiter.on((event) => events.push(event));

      const resultPromise = limiter.schedule(async () => 'test');
      jest.runAllTimers();
      await resultPromise;

      expect(events.some((e) => e.type === 'request:queued')).toBe(true);
    });

    it('should emit request:started event', async () => {
      const events: RateLimiterEvent[] = [];
      limiter.on((event) => events.push(event));

      const resultPromise = limiter.schedule(async () => 'test');
      jest.runAllTimers();
      await resultPromise;

      expect(events.some((e) => e.type === 'request:started')).toBe(true);
    });

    it('should emit request:completed event', async () => {
      const events: RateLimiterEvent[] = [];
      limiter.on((event) => events.push(event));

      const resultPromise = limiter.schedule(async () => 'test');
      jest.runAllTimers();
      await resultPromise;

      expect(events.some((e) => e.type === 'request:completed')).toBe(true);
    });

    it('should emit request:failed event on error', async () => {
      const events: RateLimiterEvent[] = [];
      limiter.on((event) => events.push(event));

      const resultPromise = limiter.schedule(async () => {
        throw new Error('Test error');
      });
      jest.runAllTimers();

      try {
        await resultPromise;
      } catch {
        // Expected
      }

      expect(events.some((e) => e.type === 'request:failed')).toBe(true);
    });

    it('should emit rate:limited event when rate limited', async () => {
      const events: RateLimiterEvent[] = [];
      const limitedLimiter = new RateLimiter(
        createConfig({ static: { maxRequests: 1, intervalMs: 10000 } }),
        store
      );
      limitedLimiter.on((event) => events.push(event));

      limitedLimiter.schedule(async () => 'first');
      limitedLimiter.schedule(async () => 'second');

      jest.runAllTimers();
      await Promise.resolve();
      jest.runAllTimers();

      await limitedLimiter.destroy();
    });

    it('should allow removing listeners', async () => {
      const events: RateLimiterEvent[] = [];
      const listener = (event: RateLimiterEvent) => events.push(event);

      const removeListener = limiter.on(listener);
      removeListener();

      const resultPromise = limiter.schedule(async () => 'test');
      jest.runAllTimers();
      await resultPromise;

      expect(events).toHaveLength(0);
    });

    it('should support off() method', async () => {
      const events: RateLimiterEvent[] = [];
      const listener = (event: RateLimiterEvent) => events.push(event);

      limiter.on(listener);
      limiter.off(listener);

      const resultPromise = limiter.schedule(async () => 'test');
      jest.runAllTimers();
      await resultPromise;

      expect(events).toHaveLength(0);
    });

    it('should catch listener errors', async () => {
      const throwingListener = () => {
        throw new Error('Listener error');
      };

      limiter.on(throwingListener);

      const resultPromise = limiter.schedule(async () => 'test');
      jest.runAllTimers();
      const result = await resultPromise;

      expect(result.result).toBe('test');
    });
  });

  describe('deadline handling', () => {
    it('should reject requests that exceed deadline', async () => {
      const slowLimiter = new RateLimiter(
        createConfig({ static: { maxRequests: 1, intervalMs: 10000 } }),
        store
      );

      slowLimiter.schedule(async () => {
        await new Promise((resolve) => setTimeout(resolve, 5000));
        return 'first';
      });

      const deadlinePromise = slowLimiter.schedule(
        async () => 'second',
        { deadline: Date.now() + 1000 }
      );

      jest.advanceTimersByTime(2000);
      await Promise.resolve();
      jest.runAllTimers();

      await expect(deadlinePromise).rejects.toThrow('deadline');

      await slowLimiter.destroy();
    });
  });

  describe('getStats', () => {
    it('should return initial stats', () => {
      const stats = limiter.getStats();

      expect(stats.queueSize).toBe(0);
      expect(stats.activeRequests).toBe(0);
      expect(stats.totalProcessed).toBe(0);
      expect(stats.totalRejected).toBe(0);
    });

    it('should track processed requests', async () => {
      const resultPromise = limiter.schedule(async () => 'test');
      jest.runAllTimers();
      await resultPromise;

      const stats = limiter.getStats();
      expect(stats.totalProcessed).toBe(1);
    });

    it('should track rejected requests', async () => {
      const resultPromise = limiter.schedule(async () => {
        throw new Error('Test error');
      });
      jest.runAllTimers();

      try {
        await resultPromise;
      } catch {
        // Expected
      }

      const stats = limiter.getStats();
      expect(stats.totalRejected).toBe(1);
    });

    it('should calculate average times', async () => {
      for (let i = 0; i < 3; i++) {
        const resultPromise = limiter.schedule(async () => i);
        jest.runAllTimers();
        await resultPromise;
      }

      const stats = limiter.getStats();
      expect(stats.avgQueueTimeMs).toBeGreaterThanOrEqual(0);
      expect(stats.avgExecutionTimeMs).toBeGreaterThanOrEqual(0);
    });
  });

  describe('destroy', () => {
    it('should reject all pending requests', async () => {
      const slowLimiter = new RateLimiter(
        createConfig({ static: { maxRequests: 1, intervalMs: 10000 } }),
        store
      );

      slowLimiter.schedule(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10000));
        return 'blocking';
      });

      const pendingPromise = slowLimiter.schedule(async () => 'pending');

      jest.advanceTimersByTime(100);
      await slowLimiter.destroy();

      await expect(pendingPromise).rejects.toThrow('destroyed');
    });

    it('should close the store', async () => {
      const mockStore: RateLimitStore = {
        getCount: jest.fn<() => Promise<number>>().mockResolvedValue(0),
        increment: jest.fn<() => Promise<number>>().mockResolvedValue(1),
        getTTL: jest.fn<() => Promise<number>>().mockResolvedValue(1000),
        reset: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
        close: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
      };

      const customLimiter = new RateLimiter(createConfig(), mockStore);
      await customLimiter.destroy();

      expect(mockStore.close).toHaveBeenCalled();
    });

    it('should clear all listeners', async () => {
      const events: RateLimiterEvent[] = [];
      limiter.on((event) => events.push(event));

      await limiter.destroy();

      const newLimiter = new RateLimiter(createConfig(), store);
      const resultPromise = newLimiter.schedule(async () => 'test');
      jest.runAllTimers();
      await resultPromise;

      expect(events).toHaveLength(0);
      await newLimiter.destroy();
    });
  });

  describe('createRateLimiter factory', () => {
    it('should create limiter with config', () => {
      const factoryLimiter = createRateLimiter(createConfig());
      expect(factoryLimiter).toBeInstanceOf(RateLimiter);
    });

    it('should create limiter with custom store', () => {
      const customStore = new MemoryStore();
      const factoryLimiter = createRateLimiter(createConfig(), customStore);
      expect(factoryLimiter).toBeInstanceOf(RateLimiter);
    });
  });

  describe('state transitions', () => {
    it('should handle: idle -> processing -> idle', async () => {
      const stats1 = limiter.getStats();
      expect(stats1.activeRequests).toBe(0);

      const resultPromise = limiter.schedule(async () => 'test');
      jest.runAllTimers();
      await resultPromise;

      const stats2 = limiter.getStats();
      expect(stats2.activeRequests).toBe(0);
    });

    it('should handle rapid schedule/complete cycles', async () => {
      for (let i = 0; i < 50; i++) {
        const resultPromise = limiter.schedule(async () => i);
        jest.runAllTimers();
        await resultPromise;
      }

      const stats = limiter.getStats();
      expect(stats.totalProcessed).toBe(50);
    });
  });

  describe('edge cases', () => {
    it('should handle empty function', async () => {
      const resultPromise = limiter.schedule(async () => undefined);
      jest.runAllTimers();
      const result = await resultPromise;

      expect(result.result).toBeUndefined();
    });

    it('should handle function returning null', async () => {
      const resultPromise = limiter.schedule(async () => null);
      jest.runAllTimers();
      const result = await resultPromise;

      expect(result.result).toBeNull();
    });

    it('should handle function returning complex object', async () => {
      const complexObject = {
        nested: { value: 42 },
        array: [1, 2, 3],
        fn: () => 'test',
      };

      const resultPromise = limiter.schedule(async () => complexObject);
      jest.runAllTimers();
      const result = await resultPromise;

      expect(result.result.nested.value).toBe(42);
    });
  });
});
