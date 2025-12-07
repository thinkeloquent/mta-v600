/**
 * Tests for config utilities
 *
 * Coverage includes:
 * - calculateBackoffDelay with various inputs
 * - isRetryableError with different error types
 * - isRetryableStatus with various status codes
 * - mergeConfig with partial configs
 * - generateRequestId uniqueness
 * - sleep with abort signal
 */

import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import {
  calculateBackoffDelay,
  isRetryableError,
  isRetryableStatus,
  mergeConfig,
  generateRequestId,
  sleep,
  DEFAULT_RETRY_CONFIG,
  DEFAULT_CONFIG,
} from '../src/config.mjs';
import type { RateLimiterConfig, RetryConfig } from '../src/types.mjs';

describe('config utilities', () => {
  describe('calculateBackoffDelay', () => {
    const baseConfig: RetryConfig = {
      baseDelayMs: 1000,
      maxDelayMs: 30000,
      jitterFactor: 0,
    };

    it('should return base delay for attempt 0 with no jitter', () => {
      const delay = calculateBackoffDelay(0, baseConfig);
      expect(delay).toBe(1000);
    });

    it('should double delay for each attempt (exponential)', () => {
      const delays = [0, 1, 2, 3].map((attempt) =>
        calculateBackoffDelay(attempt, baseConfig)
      );

      expect(delays[0]).toBe(1000);
      expect(delays[1]).toBe(2000);
      expect(delays[2]).toBe(4000);
      expect(delays[3]).toBe(8000);
    });

    it('should cap delay at maxDelayMs', () => {
      const delay = calculateBackoffDelay(10, baseConfig);
      expect(delay).toBe(30000);
    });

    it('should apply jitter within expected range', () => {
      const configWithJitter: RetryConfig = {
        baseDelayMs: 1000,
        maxDelayMs: 30000,
        jitterFactor: 0.5,
      };

      const samples = Array.from({ length: 100 }, () =>
        calculateBackoffDelay(0, configWithJitter)
      );

      const min = Math.min(...samples);
      const max = Math.max(...samples);

      expect(min).toBeGreaterThanOrEqual(500);
      expect(max).toBeLessThanOrEqual(1500);
    });

    it('should use defaults when config values are missing', () => {
      const delay = calculateBackoffDelay(0, {});
      expect(delay).toBeGreaterThan(0);
    });

    it('should handle edge case: attempt = 0', () => {
      const delay = calculateBackoffDelay(0, baseConfig);
      expect(delay).toBe(1000);
    });

    it('should handle edge case: very large attempt number', () => {
      const delay = calculateBackoffDelay(100, baseConfig);
      expect(delay).toBe(30000);
    });

    it('should never return negative delay', () => {
      for (let i = 0; i < 100; i++) {
        const delay = calculateBackoffDelay(i, DEFAULT_RETRY_CONFIG);
        expect(delay).toBeGreaterThanOrEqual(0);
      }
    });

    it('should return integer values', () => {
      const delay = calculateBackoffDelay(1, {
        baseDelayMs: 1000,
        maxDelayMs: 30000,
        jitterFactor: 0.5,
      });
      expect(Number.isInteger(delay)).toBe(true);
    });
  });

  describe('isRetryableError', () => {
    const config: RetryConfig = {
      retryOnErrors: ['ECONNRESET', 'ETIMEDOUT', 'ENOTFOUND'],
    };

    it('should return true for error with matching code', () => {
      const error = Object.assign(new Error('Connection reset'), {
        code: 'ECONNRESET',
      });
      expect(isRetryableError(error, config)).toBe(true);
    });

    it('should return false for error with non-matching code', () => {
      const error = Object.assign(new Error('Access denied'), {
        code: 'EACCES',
      });
      expect(isRetryableError(error, config)).toBe(false);
    });

    it('should return true for network-related error messages', () => {
      const networkErrors = [
        new Error('Network failure'),
        new Error('Request timeout'),
        new Error('ECONNRESET'),
        new Error('Socket hung up'),
      ];

      for (const error of networkErrors) {
        expect(isRetryableError(error, config)).toBe(true);
      }
    });

    it('should return false for non-retryable errors', () => {
      const error = new Error('Invalid JSON');
      expect(isRetryableError(error, config)).toBe(false);
    });

    it('should use default config when retryOnErrors is missing', () => {
      const error = Object.assign(new Error('Timeout'), { code: 'ETIMEDOUT' });
      expect(isRetryableError(error, {})).toBe(true);
    });

    it('should be case-insensitive for message matching', () => {
      const error = new Error('NETWORK ERROR OCCURRED');
      expect(isRetryableError(error, config)).toBe(true);
    });
  });

  describe('isRetryableStatus', () => {
    const config: RetryConfig = {
      retryOnStatus: [429, 500, 502, 503, 504],
    };

    it('should return true for retryable status codes', () => {
      expect(isRetryableStatus(429, config)).toBe(true);
      expect(isRetryableStatus(500, config)).toBe(true);
      expect(isRetryableStatus(502, config)).toBe(true);
      expect(isRetryableStatus(503, config)).toBe(true);
      expect(isRetryableStatus(504, config)).toBe(true);
    });

    it('should return false for non-retryable status codes', () => {
      expect(isRetryableStatus(200, config)).toBe(false);
      expect(isRetryableStatus(201, config)).toBe(false);
      expect(isRetryableStatus(400, config)).toBe(false);
      expect(isRetryableStatus(401, config)).toBe(false);
      expect(isRetryableStatus(403, config)).toBe(false);
      expect(isRetryableStatus(404, config)).toBe(false);
    });

    it('should use default config when retryOnStatus is missing', () => {
      expect(isRetryableStatus(429, {})).toBe(true);
      expect(isRetryableStatus(200, {})).toBe(false);
    });

    it('should handle boundary status codes', () => {
      expect(isRetryableStatus(0, config)).toBe(false);
      expect(isRetryableStatus(-1, config)).toBe(false);
      expect(isRetryableStatus(999, config)).toBe(false);
    });
  });

  describe('mergeConfig', () => {
    it('should merge with defaults', () => {
      const config: RateLimiterConfig = {
        id: 'test',
        static: { maxRequests: 100, intervalMs: 1000 },
      };

      const merged = mergeConfig(config);

      expect(merged.id).toBe('test');
      expect(merged.maxQueueSize).toBe(Infinity);
      expect(merged.concurrency).toBe(1);
      expect(merged.retry).toBeDefined();
    });

    it('should preserve user-provided values', () => {
      const config: RateLimiterConfig = {
        id: 'test',
        maxQueueSize: 50,
        concurrency: 5,
        static: { maxRequests: 10, intervalMs: 1000 },
      };

      const merged = mergeConfig(config);

      expect(merged.maxQueueSize).toBe(50);
      expect(merged.concurrency).toBe(5);
    });

    it('should merge retry config with defaults', () => {
      const config: RateLimiterConfig = {
        id: 'test',
        retry: {
          maxRetries: 5,
          baseDelayMs: 2000,
        },
      };

      const merged = mergeConfig(config);

      expect(merged.retry?.maxRetries).toBe(5);
      expect(merged.retry?.baseDelayMs).toBe(2000);
      expect(merged.retry?.maxDelayMs).toBe(DEFAULT_RETRY_CONFIG.maxDelayMs);
    });

    it('should handle empty config', () => {
      const config: RateLimiterConfig = { id: 'test' };
      const merged = mergeConfig(config);

      expect(merged.id).toBe('test');
      expect(merged.retry).toEqual(DEFAULT_RETRY_CONFIG);
    });
  });

  describe('generateRequestId', () => {
    it('should generate unique IDs', () => {
      const ids = new Set<string>();
      for (let i = 0; i < 1000; i++) {
        ids.add(generateRequestId());
      }
      expect(ids.size).toBe(1000);
    });

    it('should start with "req_" prefix', () => {
      const id = generateRequestId();
      expect(id).toMatch(/^req_/);
    });

    it('should contain timestamp and random component', () => {
      const id = generateRequestId();
      expect(id).toMatch(/^req_\d+_[a-z0-9]+$/);
    });

    it('should generate IDs of consistent length', () => {
      const ids = Array.from({ length: 100 }, () => generateRequestId());
      const lengths = new Set(ids.map((id) => id.length));

      // All IDs should be roughly the same length (±2 chars due to timestamp)
      expect(lengths.size).toBeLessThanOrEqual(3);
    });
  });

  describe('sleep', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should resolve after specified delay', async () => {
      const promise = sleep(1000);

      jest.advanceTimersByTime(999);
      expect(jest.getTimerCount()).toBe(1);

      jest.advanceTimersByTime(1);
      await promise;
    });

    it('should reject if already aborted', async () => {
      const controller = new AbortController();
      controller.abort();

      await expect(sleep(1000, controller.signal)).rejects.toThrow('Aborted');
    });

    it('should reject when aborted during sleep', async () => {
      const controller = new AbortController();
      const promise = sleep(1000, controller.signal);

      jest.advanceTimersByTime(500);
      controller.abort();

      await expect(promise).rejects.toThrow('Aborted');
    });

    it('should handle zero delay', async () => {
      const promise = sleep(0);
      jest.advanceTimersByTime(0);
      await promise;
    });
  });

  describe('DEFAULT_RETRY_CONFIG', () => {
    it('should have sensible defaults', () => {
      expect(DEFAULT_RETRY_CONFIG.maxRetries).toBe(3);
      expect(DEFAULT_RETRY_CONFIG.baseDelayMs).toBe(1000);
      expect(DEFAULT_RETRY_CONFIG.maxDelayMs).toBe(30000);
      expect(DEFAULT_RETRY_CONFIG.jitterFactor).toBe(0.5);
      expect(DEFAULT_RETRY_CONFIG.retryOnErrors).toContain('ECONNRESET');
      expect(DEFAULT_RETRY_CONFIG.retryOnStatus).toContain(429);
    });
  });

  describe('DEFAULT_CONFIG', () => {
    it('should have sensible defaults', () => {
      expect(DEFAULT_CONFIG.maxQueueSize).toBe(Infinity);
      expect(DEFAULT_CONFIG.concurrency).toBe(1);
      expect(DEFAULT_CONFIG.retry).toBeDefined();
    });
  });
});
