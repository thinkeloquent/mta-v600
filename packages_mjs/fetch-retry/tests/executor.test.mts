/**
 * Tests for fetch-retry executor
 *
 * Test coverage includes:
 * - Statement coverage: All executable statements
 * - Decision/Branch coverage: All boolean decisions (if/else)
 * - Loop testing: Zero iterations, one iteration, many iterations
 * - Path coverage: Success paths, retry paths, failure paths
 * - State transition testing: Attempt states and transitions
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  RetryExecutor,
  createRetryExecutor,
  retry,
  createRetryWrapper,
} from '../src/executor.mjs';
import type { RetryConfig, RetryEvent, RetryOptions } from '../src/types.mjs';

describe('RetryExecutor', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('constructor', () => {
    it('should create executor with default config', () => {
      const executor = new RetryExecutor();
      const config = executor.getConfig();
      expect(config.maxRetries).toBe(3);
      expect(config.baseDelayMs).toBe(1000);
    });

    it('should create executor with custom config', () => {
      const executor = new RetryExecutor({ maxRetries: 5, baseDelayMs: 500 });
      const config = executor.getConfig();
      expect(config.maxRetries).toBe(5);
      expect(config.baseDelayMs).toBe(500);
    });

    it('should generate unique ID if not provided', () => {
      const executor = new RetryExecutor();
      expect(executor.getId()).toMatch(/^retry-/);
    });

    it('should use provided ID', () => {
      const executor = new RetryExecutor({ id: 'custom-id' });
      expect(executor.getId()).toBe('custom-id');
    });
  });

  describe('execute - success path', () => {
    it('should return result on immediate success', async () => {
      const executor = new RetryExecutor();
      const fn = vi.fn().mockResolvedValue('success');

      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      const result = await resultPromise;

      expect(result.result).toBe('success');
      expect(result.retries).toBe(0);
      expect(result.totalTimeMs).toBeGreaterThanOrEqual(0);
      expect(result.delayTimeMs).toBe(0);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should track timing correctly', async () => {
      const executor = new RetryExecutor();
      const fn = vi.fn().mockResolvedValue('success');

      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      const result = await resultPromise;

      expect(result.totalTimeMs).toBeGreaterThanOrEqual(0);
    });
  });

  describe('execute - retry path', () => {
    it('should retry on retryable error', async () => {
      const executor = new RetryExecutor({ maxRetries: 3, baseDelayMs: 100, jitterFactor: 0 });
      const fn = vi
        .fn()
        .mockRejectedValueOnce(new Error('connection error'))
        .mockResolvedValue('success');

      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      const result = await resultPromise;

      expect(result.result).toBe('success');
      expect(result.retries).toBe(1);
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should retry multiple times', async () => {
      const executor = new RetryExecutor({ maxRetries: 5, baseDelayMs: 100, jitterFactor: 0 });
      const fn = vi
        .fn()
        .mockRejectedValueOnce(new Error('network error'))
        .mockRejectedValueOnce(new Error('timeout'))
        .mockRejectedValueOnce(new Error('connection failed'))
        .mockResolvedValue('success');

      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      const result = await resultPromise;

      expect(result.result).toBe('success');
      expect(result.retries).toBe(3);
      expect(fn).toHaveBeenCalledTimes(4);
    });

    it('should track delay time across retries', async () => {
      vi.spyOn(Math, 'random').mockReturnValue(0.5);
      const executor = new RetryExecutor({ maxRetries: 3, baseDelayMs: 100, jitterFactor: 0 });
      const fn = vi
        .fn()
        .mockRejectedValueOnce(new Error('network error'))
        .mockResolvedValue('success');

      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      const result = await resultPromise;

      expect(result.delayTimeMs).toBeGreaterThan(0);
    });
  });

  describe('execute - failure path', () => {
    it('should throw after exhausting retries', async () => {
      const executor = new RetryExecutor({ maxRetries: 2, baseDelayMs: 100, jitterFactor: 0 });
      const fn = vi.fn().mockRejectedValue(new Error('network error'));

      const resultPromise = executor.execute(fn);

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.runAllTimersAsync(),
        expect(resultPromise).rejects.toThrow('network error'),
      ]);
      expect(fn).toHaveBeenCalledTimes(3); // initial + 2 retries
    });

    it('should throw immediately for non-retryable errors', async () => {
      const executor = new RetryExecutor({ maxRetries: 3 });
      const fn = vi.fn().mockRejectedValue(new Error('validation error'));

      const resultPromise = executor.execute(fn);

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.runAllTimersAsync(),
        expect(resultPromise).rejects.toThrow('validation error'),
      ]);
      expect(fn).toHaveBeenCalledTimes(1);
    });
  });

  describe('execute - abort handling', () => {
    it('should abort if signal is already aborted', async () => {
      const executor = new RetryExecutor();
      const controller = new AbortController();
      controller.abort();

      const fn = vi.fn().mockResolvedValue('success');
      const resultPromise = executor.execute(fn, { signal: controller.signal });

      await expect(resultPromise).rejects.toThrow('Retry aborted');
      expect(fn).not.toHaveBeenCalled();
    });

    it('should abort during retry wait', async () => {
      const executor = new RetryExecutor({ maxRetries: 3, baseDelayMs: 1000, jitterFactor: 0 });
      const controller = new AbortController();
      const fn = vi.fn().mockRejectedValue(new Error('network error'));

      const resultPromise = executor.execute(fn, { signal: controller.signal });

      // Let first attempt fail
      await vi.advanceTimersByTimeAsync(0);

      // Abort during wait
      controller.abort();

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.advanceTimersByTimeAsync(500),
        expect(resultPromise).rejects.toThrow(),
      ]);
    });
  });

  describe('execute - custom shouldRetry', () => {
    it('should use custom shouldRetry predicate', async () => {
      const executor = new RetryExecutor({ maxRetries: 3, baseDelayMs: 100, jitterFactor: 0 });
      const customShouldRetry = vi.fn().mockReturnValue(false);
      const fn = vi.fn().mockRejectedValue(new Error('network error'));

      const resultPromise = executor.execute(fn, { shouldRetry: customShouldRetry });

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.runAllTimersAsync(),
        expect(resultPromise).rejects.toThrow('network error'),
      ]);
      expect(customShouldRetry).toHaveBeenCalledWith(expect.any(Error), 0);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should retry when custom shouldRetry returns true', async () => {
      const executor = new RetryExecutor({ maxRetries: 3, baseDelayMs: 100, jitterFactor: 0 });
      const customShouldRetry = vi.fn().mockReturnValue(true);
      const fn = vi
        .fn()
        .mockRejectedValueOnce(new Error('custom error'))
        .mockResolvedValue('success');

      const resultPromise = executor.execute(fn, { shouldRetry: customShouldRetry });
      await vi.runAllTimersAsync();
      const result = await resultPromise;

      expect(result.result).toBe('success');
      expect(customShouldRetry).toHaveBeenCalled();
    });
  });

  describe('execute - maxRetries override', () => {
    it('should use maxRetries from options', async () => {
      const executor = new RetryExecutor({ maxRetries: 1, baseDelayMs: 100, jitterFactor: 0 });
      const fn = vi.fn().mockRejectedValue(new Error('network error'));

      const resultPromise = executor.execute(fn, { maxRetries: 5 });

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.runAllTimersAsync(),
        expect(resultPromise).rejects.toThrow('network error'),
      ]);
      expect(fn).toHaveBeenCalledTimes(6); // initial + 5 retries
    });
  });

  describe('event emission', () => {
    it('should emit attempt:start event', async () => {
      const executor = new RetryExecutor();
      const events: RetryEvent[] = [];
      executor.on((e) => events.push(e));

      const fn = vi.fn().mockResolvedValue('success');
      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      await resultPromise;

      expect(events).toContainEqual(
        expect.objectContaining({ type: 'attempt:start', attempt: 0 })
      );
    });

    it('should emit attempt:success event', async () => {
      const executor = new RetryExecutor();
      const events: RetryEvent[] = [];
      executor.on((e) => events.push(e));

      const fn = vi.fn().mockResolvedValue('success');
      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      await resultPromise;

      expect(events).toContainEqual(
        expect.objectContaining({
          type: 'attempt:success',
          attempt: 0,
          durationMs: expect.any(Number),
        })
      );
    });

    it('should emit attempt:fail event', async () => {
      const executor = new RetryExecutor({ maxRetries: 1, baseDelayMs: 100, jitterFactor: 0 });
      const events: RetryEvent[] = [];
      executor.on((e) => events.push(e));

      const fn = vi.fn().mockRejectedValue(new Error('validation error'));
      const resultPromise = executor.execute(fn);

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.runAllTimersAsync(),
        resultPromise.catch(() => {}), // Catch the expected rejection
      ]);

      expect(events).toContainEqual(
        expect.objectContaining({
          type: 'attempt:fail',
          attempt: 0,
          willRetry: false,
        })
      );
    });

    it('should emit retry:wait event', async () => {
      const executor = new RetryExecutor({ maxRetries: 2, baseDelayMs: 100, jitterFactor: 0 });
      const events: RetryEvent[] = [];
      executor.on((e) => events.push(e));

      const fn = vi
        .fn()
        .mockRejectedValueOnce(new Error('network error'))
        .mockResolvedValue('success');

      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      await resultPromise;

      expect(events).toContainEqual(
        expect.objectContaining({
          type: 'retry:wait',
          attempt: 0,
          delayMs: expect.any(Number),
        })
      );
    });

    it('should emit retry:abort event', async () => {
      const executor = new RetryExecutor();
      const events: RetryEvent[] = [];
      executor.on((e) => events.push(e));
      const controller = new AbortController();
      controller.abort();

      const fn = vi.fn().mockResolvedValue('success');
      try {
        await executor.execute(fn, { signal: controller.signal });
      } catch {
        // Expected
      }

      expect(events).toContainEqual(
        expect.objectContaining({
          type: 'retry:abort',
          reason: 'Aborted by signal',
        })
      );
    });

    it('should include metadata in events', async () => {
      const executor = new RetryExecutor();
      const events: RetryEvent[] = [];
      executor.on((e) => events.push(e));

      const fn = vi.fn().mockResolvedValue('success');
      const metadata = { requestId: '123' };
      const resultPromise = executor.execute(fn, { metadata });
      await vi.runAllTimersAsync();
      await resultPromise;

      expect(events[0].metadata).toEqual(metadata);
    });

    it('should ignore listener errors', async () => {
      const executor = new RetryExecutor();
      executor.on(() => {
        throw new Error('Listener error');
      });

      const fn = vi.fn().mockResolvedValue('success');
      const resultPromise = executor.execute(fn);
      await vi.runAllTimersAsync();
      const result = await resultPromise;

      expect(result.result).toBe('success');
    });
  });

  describe('event listener management', () => {
    it('should add listener with on()', () => {
      const executor = new RetryExecutor();
      const listener = vi.fn();
      executor.on(listener);

      // Trigger an event by executing
      executor.execute(() => Promise.resolve('success'));

      expect(listener).toHaveBeenCalled();
    });

    it('should return unsubscribe function from on()', async () => {
      const executor = new RetryExecutor();
      const listener = vi.fn();
      const unsubscribe = executor.on(listener);

      unsubscribe();

      const resultPromise = executor.execute(() => Promise.resolve('success'));
      await vi.runAllTimersAsync();
      await resultPromise;

      expect(listener).not.toHaveBeenCalled();
    });

    it('should remove listener with off()', async () => {
      const executor = new RetryExecutor();
      const listener = vi.fn();
      executor.on(listener);
      executor.off(listener);

      const resultPromise = executor.execute(() => Promise.resolve('success'));
      await vi.runAllTimersAsync();
      await resultPromise;

      expect(listener).not.toHaveBeenCalled();
    });
  });

  describe('getConfig', () => {
    it('should return copy of config', () => {
      const executor = new RetryExecutor({ maxRetries: 5 });
      const config1 = executor.getConfig();
      const config2 = executor.getConfig();

      expect(config1).not.toBe(config2);
      expect(config1).toEqual(config2);
    });
  });
});

describe('createRetryExecutor', () => {
  it('should create executor with config', () => {
    const executor = createRetryExecutor({ maxRetries: 5 });
    expect(executor.getConfig().maxRetries).toBe(5);
  });

  it('should create executor without config', () => {
    const executor = createRetryExecutor();
    expect(executor.getConfig().maxRetries).toBe(3);
  });
});

describe('retry convenience function', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should retry function with config', async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new Error('network error'))
      .mockResolvedValue('success');

    const resultPromise = retry(fn, { maxRetries: 3, baseDelayMs: 100, jitterFactor: 0 });
    await vi.runAllTimersAsync();
    const result = await resultPromise;

    expect(result.result).toBe('success');
    expect(result.retries).toBe(1);
  });

  it('should work without config', async () => {
    const fn = vi.fn().mockResolvedValue('success');

    const resultPromise = retry(fn);
    await vi.runAllTimersAsync();
    const result = await resultPromise;

    expect(result.result).toBe('success');
  });
});

describe('createRetryWrapper', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should create reusable wrapper', async () => {
    const withRetry = createRetryWrapper({ maxRetries: 2, baseDelayMs: 100, jitterFactor: 0 });

    const fn1 = vi.fn().mockResolvedValue('result1');
    const fn2 = vi.fn().mockResolvedValue('result2');

    const promise1 = withRetry(fn1);
    await vi.runAllTimersAsync();
    const result1 = await promise1;

    const promise2 = withRetry(fn2);
    await vi.runAllTimersAsync();
    const result2 = await promise2;

    expect(result1.result).toBe('result1');
    expect(result2.result).toBe('result2');
  });

  it('should accept per-call options', async () => {
    const withRetry = createRetryWrapper({ maxRetries: 1, baseDelayMs: 100, jitterFactor: 0 });
    const fn = vi.fn().mockRejectedValue(new Error('network error'));

    const resultPromise = withRetry(fn, { maxRetries: 3 });

    // Run timers and check result together to avoid unhandled rejection
    await Promise.all([
      vi.runAllTimersAsync(),
      expect(resultPromise).rejects.toThrow('network error'),
    ]);
    expect(fn).toHaveBeenCalledTimes(4); // initial + 3 overridden retries
  });
});

describe('edge cases and boundary conditions', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('zero retries', () => {
    it('should not retry when maxRetries is 0', async () => {
      const executor = new RetryExecutor({ maxRetries: 0 });
      const fn = vi.fn().mockRejectedValue(new Error('network error'));

      const resultPromise = executor.execute(fn);

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.runAllTimersAsync(),
        expect(resultPromise).rejects.toThrow('network error'),
      ]);
      expect(fn).toHaveBeenCalledTimes(1);
    });
  });

  describe('single retry', () => {
    it('should retry exactly once when maxRetries is 1', async () => {
      const executor = new RetryExecutor({ maxRetries: 1, baseDelayMs: 100, jitterFactor: 0 });
      const fn = vi.fn().mockRejectedValue(new Error('network error'));

      const resultPromise = executor.execute(fn);

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.runAllTimersAsync(),
        expect(resultPromise).rejects.toThrow('network error'),
      ]);
      expect(fn).toHaveBeenCalledTimes(2);
    });
  });

  describe('concurrent executions', () => {
    it('should handle multiple concurrent executions independently', async () => {
      const executor = new RetryExecutor({ maxRetries: 2, baseDelayMs: 100, jitterFactor: 0 });

      const fn1 = vi.fn().mockResolvedValue('result1');
      const fn2 = vi.fn().mockResolvedValue('result2');

      const promise1 = executor.execute(fn1);
      const promise2 = executor.execute(fn2);

      await vi.runAllTimersAsync();

      const [result1, result2] = await Promise.all([promise1, promise2]);

      expect(result1.result).toBe('result1');
      expect(result2.result).toBe('result2');
    });
  });

  describe('error types', () => {
    it('should handle non-Error thrown values', async () => {
      const executor = new RetryExecutor({ maxRetries: 1 });
      // Non-Error thrown values are now handled - treated as non-retryable
      const fn = vi.fn().mockRejectedValue('string error');

      const resultPromise = executor.execute(fn);

      // Run timers and check result together to avoid unhandled rejection
      await Promise.all([
        vi.runAllTimersAsync(),
        expect(resultPromise).rejects.toBe('string error'),
      ]);
    });
  });
});
