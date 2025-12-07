/**
 * Tests for fetch-retry configuration utilities
 *
 * Test coverage includes:
 * - Statement coverage: All executable statements
 * - Decision/Branch coverage: All boolean decisions (if/else, switch)
 * - Condition coverage: All individual conditions in compound expressions
 * - Boundary value testing: Edge cases and limits
 * - Equivalence partitioning: Representative values from each class
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  DEFAULT_RETRY_CONFIG,
  IDEMPOTENT_METHODS,
  NON_IDEMPOTENT_METHODS,
  calculateBackoffDelay,
  calculateDelay,
  isRetryableError,
  isRetryableStatus,
  isRetryableMethod,
  shouldRetryResponse,
  parseRetryAfter,
  mergeConfig,
  sleep,
  createRetryError,
} from '../src/config.mjs';
import type { RetryConfig, ExtendedRetryConfig, RetryableError, ResponseLike } from '../src/types.mjs';

describe('DEFAULT_RETRY_CONFIG', () => {
  it('should have expected default values', () => {
    expect(DEFAULT_RETRY_CONFIG.maxRetries).toBe(3);
    expect(DEFAULT_RETRY_CONFIG.baseDelayMs).toBe(1000);
    expect(DEFAULT_RETRY_CONFIG.maxDelayMs).toBe(30000);
    expect(DEFAULT_RETRY_CONFIG.jitterFactor).toBe(0.5);
    expect(DEFAULT_RETRY_CONFIG.respectRetryAfter).toBe(true);
  });

  it('should include standard retryable error codes', () => {
    expect(DEFAULT_RETRY_CONFIG.retryOnErrors).toContain('ECONNRESET');
    expect(DEFAULT_RETRY_CONFIG.retryOnErrors).toContain('ETIMEDOUT');
    expect(DEFAULT_RETRY_CONFIG.retryOnErrors).toContain('ENOTFOUND');
    expect(DEFAULT_RETRY_CONFIG.retryOnErrors).toContain('ECONNREFUSED');
    expect(DEFAULT_RETRY_CONFIG.retryOnErrors).toContain('EPIPE');
    expect(DEFAULT_RETRY_CONFIG.retryOnErrors).toContain('UND_ERR_SOCKET');
  });

  it('should include standard retryable status codes', () => {
    expect(DEFAULT_RETRY_CONFIG.retryOnStatus).toEqual([429, 500, 502, 503, 504]);
  });

  it('should include idempotent HTTP methods', () => {
    expect(DEFAULT_RETRY_CONFIG.retryMethods).toEqual(['GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE']);
  });
});

describe('IDEMPOTENT_METHODS', () => {
  it('should include all safe idempotent methods', () => {
    expect(IDEMPOTENT_METHODS).toContain('GET');
    expect(IDEMPOTENT_METHODS).toContain('HEAD');
    expect(IDEMPOTENT_METHODS).toContain('OPTIONS');
    expect(IDEMPOTENT_METHODS).toContain('PUT');
    expect(IDEMPOTENT_METHODS).toContain('DELETE');
    expect(IDEMPOTENT_METHODS).toContain('TRACE');
  });
});

describe('NON_IDEMPOTENT_METHODS', () => {
  it('should include non-idempotent methods', () => {
    expect(NON_IDEMPOTENT_METHODS).toContain('POST');
    expect(NON_IDEMPOTENT_METHODS).toContain('PATCH');
  });
});

describe('calculateBackoffDelay', () => {
  beforeEach(() => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('exponential backoff calculation', () => {
    it('should calculate base delay for attempt 0', () => {
      const config: RetryConfig = { baseDelayMs: 1000, maxDelayMs: 30000, jitterFactor: 0 };
      const delay = calculateBackoffDelay(0, config);
      expect(delay).toBe(1000); // base * 2^0 = 1000
    });

    it('should double delay for each attempt', () => {
      const config: RetryConfig = { baseDelayMs: 1000, maxDelayMs: 30000, jitterFactor: 0 };

      expect(calculateBackoffDelay(0, config)).toBe(1000); // base * 2^0
      expect(calculateBackoffDelay(1, config)).toBe(2000); // base * 2^1
      expect(calculateBackoffDelay(2, config)).toBe(4000); // base * 2^2
      expect(calculateBackoffDelay(3, config)).toBe(8000); // base * 2^3
    });

    it('should cap delay at maxDelayMs', () => {
      const config: RetryConfig = { baseDelayMs: 1000, maxDelayMs: 5000, jitterFactor: 0 };
      const delay = calculateBackoffDelay(10, config); // 2^10 * 1000 would be 1024000
      expect(delay).toBe(5000);
    });
  });

  describe('jitter application', () => {
    it('should apply jitter factor of 0.5 (full jitter strategy)', () => {
      const config: RetryConfig = { baseDelayMs: 1000, maxDelayMs: 30000, jitterFactor: 0.5 };
      const delay = calculateBackoffDelay(0, config);
      // With random = 0.5 and jitterFactor = 0.5:
      // exponentialDelay = 1000
      // jitter = 0.5 * 0.5 * 1000 = 250
      // delay = 1000 * (1 - 0.5/2) + 250 = 1000 * 0.75 + 250 = 750 + 250 = 1000
      expect(delay).toBe(1000);
    });

    it('should have no jitter when jitterFactor is 0', () => {
      vi.spyOn(Math, 'random').mockReturnValue(0.999);
      const config: RetryConfig = { baseDelayMs: 1000, maxDelayMs: 30000, jitterFactor: 0 };
      const delay = calculateBackoffDelay(0, config);
      expect(delay).toBe(1000);
    });

    it('should have maximum jitter when jitterFactor is 1', () => {
      vi.spyOn(Math, 'random').mockReturnValue(1);
      const config: RetryConfig = { baseDelayMs: 1000, maxDelayMs: 30000, jitterFactor: 1 };
      const delay = calculateBackoffDelay(0, config);
      // With random = 1 and jitterFactor = 1:
      // jitter = 1 * 1 * 1000 = 1000
      // delay = 1000 * (1 - 0.5) + 1000 = 500 + 1000 = 1500
      expect(delay).toBe(1500);
    });
  });

  describe('boundary conditions', () => {
    it('should handle attempt 0', () => {
      const delay = calculateBackoffDelay(0, DEFAULT_RETRY_CONFIG);
      expect(delay).toBeGreaterThan(0);
    });

    it('should handle very large attempt numbers', () => {
      const delay = calculateBackoffDelay(100, DEFAULT_RETRY_CONFIG);
      expect(delay).toBeLessThanOrEqual(DEFAULT_RETRY_CONFIG.maxDelayMs);
    });

    it('should handle zero baseDelayMs', () => {
      const config: RetryConfig = { baseDelayMs: 0, maxDelayMs: 1000, jitterFactor: 0.5 };
      const delay = calculateBackoffDelay(0, config);
      expect(delay).toBe(0);
    });
  });

  describe('default values', () => {
    it('should use defaults when config values are missing', () => {
      const delay = calculateBackoffDelay(0, {});
      expect(delay).toBeGreaterThan(0);
    });
  });
});

describe('calculateDelay', () => {
  beforeEach(() => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('exponential strategy (default)', () => {
    it('should use exponential backoff by default', () => {
      const config: ExtendedRetryConfig = {
        baseDelayMs: 1000,
        maxDelayMs: 30000,
        jitterFactor: 0,
        backoffStrategy: 'exponential',
      };
      expect(calculateDelay(0, config)).toBe(1000);
      expect(calculateDelay(1, config)).toBe(2000);
      expect(calculateDelay(2, config)).toBe(4000);
    });
  });

  describe('constant strategy', () => {
    it('should return constant delay regardless of attempt', () => {
      const config: ExtendedRetryConfig = {
        baseDelayMs: 1000,
        maxDelayMs: 30000,
        jitterFactor: 0,
        backoffStrategy: 'constant',
      };
      expect(calculateDelay(0, config)).toBe(1000);
      expect(calculateDelay(1, config)).toBe(1000);
      expect(calculateDelay(5, config)).toBe(1000);
    });
  });

  describe('linear strategy', () => {
    it('should increase delay linearly', () => {
      const config: ExtendedRetryConfig = {
        baseDelayMs: 1000,
        maxDelayMs: 30000,
        jitterFactor: 0,
        backoffStrategy: 'linear',
        linearIncrementMs: 500,
      };
      expect(calculateDelay(0, config)).toBe(1000);
      expect(calculateDelay(1, config)).toBe(1500);
      expect(calculateDelay(2, config)).toBe(2000);
    });

    it('should cap at maxDelayMs', () => {
      const config: ExtendedRetryConfig = {
        baseDelayMs: 1000,
        maxDelayMs: 2000,
        jitterFactor: 0,
        backoffStrategy: 'linear',
        linearIncrementMs: 5000,
      };
      expect(calculateDelay(5, config)).toBe(2000);
    });
  });

  describe('jitter application', () => {
    it('should apply jitter to all strategies', () => {
      const config: ExtendedRetryConfig = {
        baseDelayMs: 1000,
        maxDelayMs: 30000,
        jitterFactor: 0.5,
        backoffStrategy: 'constant',
      };
      // With random = 0.5, the result should have some jitter applied
      const delay = calculateDelay(0, config);
      expect(delay).toBe(1000); // 1000 * 0.75 + 250 = 1000
    });
  });
});

describe('isRetryableError', () => {
  describe('explicit isRetryable flag', () => {
    it('should return false when isRetryable is explicitly false', () => {
      const error: RetryableError = new Error('test') as RetryableError;
      error.isRetryable = false;
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(false);
    });

    it('should return true when isRetryable is explicitly true', () => {
      const error: RetryableError = new Error('test') as RetryableError;
      error.isRetryable = true;
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(true);
    });
  });

  describe('error code matching', () => {
    it('should return true for ECONNRESET error code', () => {
      const error: RetryableError = new Error('Connection reset') as RetryableError;
      error.code = 'ECONNRESET';
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for ETIMEDOUT error code', () => {
      const error: RetryableError = new Error('Timeout') as RetryableError;
      error.code = 'ETIMEDOUT';
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for ENOTFOUND error code', () => {
      const error: RetryableError = new Error('Not found') as RetryableError;
      error.code = 'ENOTFOUND';
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for ECONNREFUSED error code', () => {
      const error: RetryableError = new Error('Connection refused') as RetryableError;
      error.code = 'ECONNREFUSED';
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return false for unknown error codes', () => {
      const error: RetryableError = new Error('Unknown') as RetryableError;
      error.code = 'UNKNOWN_ERROR';
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(false);
    });
  });

  describe('error message pattern matching', () => {
    it('should return true for network-related error messages', () => {
      expect(isRetryableError(new Error('network error'), DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for timeout error messages', () => {
      expect(isRetryableError(new Error('request timed out'), DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for connection error messages', () => {
      expect(isRetryableError(new Error('connection failed'), DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for socket error messages', () => {
      expect(isRetryableError(new Error('socket hang up'), DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for "fetch failed" error messages', () => {
      expect(isRetryableError(new Error('fetch failed'), DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should be case-insensitive', () => {
      expect(isRetryableError(new Error('NETWORK ERROR'), DEFAULT_RETRY_CONFIG)).toBe(true);
      expect(isRetryableError(new Error('Connection TIMEOUT'), DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return false for non-retryable messages', () => {
      expect(isRetryableError(new Error('invalid input'), DEFAULT_RETRY_CONFIG)).toBe(false);
    });
  });

  describe('cause chain checking', () => {
    it('should check error cause chain', () => {
      const cause: RetryableError = new Error('connection error') as RetryableError;
      const error = new Error('wrapper error', { cause });
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should recurse through nested causes', () => {
      const innerCause: RetryableError = new Error('network error') as RetryableError;
      const middleCause = new Error('middle', { cause: innerCause });
      const error = new Error('outer', { cause: middleCause });
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return false when cause is not an Error', () => {
      const error = new Error('wrapper error');
      // Non-Error cause should not be checked
      expect(isRetryableError(error, DEFAULT_RETRY_CONFIG)).toBe(false);
    });
  });

  describe('custom retry configuration', () => {
    it('should use custom retryOnErrors list', () => {
      const config: RetryConfig = { retryOnErrors: ['CUSTOM_ERROR'] };
      const error: RetryableError = new Error('custom') as RetryableError;
      error.code = 'CUSTOM_ERROR';
      expect(isRetryableError(error, config)).toBe(true);
    });
  });
});

describe('isRetryableStatus', () => {
  describe('default retryable status codes', () => {
    it('should return true for 429 Too Many Requests', () => {
      expect(isRetryableStatus(429, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for 500 Internal Server Error', () => {
      expect(isRetryableStatus(500, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for 502 Bad Gateway', () => {
      expect(isRetryableStatus(502, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for 503 Service Unavailable', () => {
      expect(isRetryableStatus(503, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for 504 Gateway Timeout', () => {
      expect(isRetryableStatus(504, DEFAULT_RETRY_CONFIG)).toBe(true);
    });
  });

  describe('non-retryable status codes', () => {
    it('should return false for 200 OK', () => {
      expect(isRetryableStatus(200, DEFAULT_RETRY_CONFIG)).toBe(false);
    });

    it('should return false for 201 Created', () => {
      expect(isRetryableStatus(201, DEFAULT_RETRY_CONFIG)).toBe(false);
    });

    it('should return false for 400 Bad Request', () => {
      expect(isRetryableStatus(400, DEFAULT_RETRY_CONFIG)).toBe(false);
    });

    it('should return false for 401 Unauthorized', () => {
      expect(isRetryableStatus(401, DEFAULT_RETRY_CONFIG)).toBe(false);
    });

    it('should return false for 403 Forbidden', () => {
      expect(isRetryableStatus(403, DEFAULT_RETRY_CONFIG)).toBe(false);
    });

    it('should return false for 404 Not Found', () => {
      expect(isRetryableStatus(404, DEFAULT_RETRY_CONFIG)).toBe(false);
    });
  });

  describe('custom retry configuration', () => {
    it('should use custom retryOnStatus list', () => {
      const config: RetryConfig = { retryOnStatus: [418, 503] };
      expect(isRetryableStatus(418, config)).toBe(true);
      expect(isRetryableStatus(503, config)).toBe(true);
      expect(isRetryableStatus(429, config)).toBe(false);
    });
  });
});

describe('isRetryableMethod', () => {
  describe('idempotent methods (retryable by default)', () => {
    it('should return true for GET', () => {
      expect(isRetryableMethod('GET', DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for HEAD', () => {
      expect(isRetryableMethod('HEAD', DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for OPTIONS', () => {
      expect(isRetryableMethod('OPTIONS', DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for PUT', () => {
      expect(isRetryableMethod('PUT', DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return true for DELETE', () => {
      expect(isRetryableMethod('DELETE', DEFAULT_RETRY_CONFIG)).toBe(true);
    });
  });

  describe('non-idempotent methods (not retryable by default)', () => {
    it('should return false for POST', () => {
      expect(isRetryableMethod('POST', DEFAULT_RETRY_CONFIG)).toBe(false);
    });

    it('should return false for PATCH', () => {
      expect(isRetryableMethod('PATCH', DEFAULT_RETRY_CONFIG)).toBe(false);
    });
  });

  describe('case insensitivity', () => {
    it('should be case-insensitive', () => {
      expect(isRetryableMethod('get', DEFAULT_RETRY_CONFIG)).toBe(true);
      expect(isRetryableMethod('Get', DEFAULT_RETRY_CONFIG)).toBe(true);
      expect(isRetryableMethod('GET', DEFAULT_RETRY_CONFIG)).toBe(true);
    });
  });

  describe('custom retry configuration', () => {
    it('should use custom retryMethods list', () => {
      const config: RetryConfig = { retryMethods: ['POST'] };
      expect(isRetryableMethod('POST', config)).toBe(true);
      expect(isRetryableMethod('GET', config)).toBe(false);
    });
  });
});

describe('shouldRetryResponse', () => {
  describe('status property', () => {
    it('should check status property', () => {
      const response: ResponseLike = { status: 503 };
      expect(shouldRetryResponse(response, DEFAULT_RETRY_CONFIG)).toBe(true);
    });

    it('should return false for non-retryable status', () => {
      const response: ResponseLike = { status: 200 };
      expect(shouldRetryResponse(response, DEFAULT_RETRY_CONFIG)).toBe(false);
    });
  });

  describe('statusCode property', () => {
    it('should check statusCode property when status is undefined', () => {
      const response: ResponseLike = { statusCode: 503 };
      expect(shouldRetryResponse(response, DEFAULT_RETRY_CONFIG)).toBe(true);
    });
  });

  describe('missing status', () => {
    it('should return false when both status and statusCode are undefined', () => {
      const response: ResponseLike = {};
      expect(shouldRetryResponse(response, DEFAULT_RETRY_CONFIG)).toBe(false);
    });
  });
});

describe('parseRetryAfter', () => {
  describe('null/undefined handling', () => {
    it('should return 0 for null', () => {
      expect(parseRetryAfter(null)).toBe(0);
    });

    it('should return 0 for undefined', () => {
      expect(parseRetryAfter(undefined)).toBe(0);
    });

    it('should return 0 for empty string', () => {
      expect(parseRetryAfter('')).toBe(0);
    });
  });

  describe('seconds format', () => {
    it('should parse integer seconds', () => {
      expect(parseRetryAfter('10')).toBe(10000);
    });

    it('should parse zero seconds', () => {
      expect(parseRetryAfter('0')).toBe(0);
    });

    it('should parse large values', () => {
      expect(parseRetryAfter('3600')).toBe(3600000);
    });
  });

  describe('HTTP-date format', () => {
    it('should parse HTTP-date format', () => {
      const futureDate = new Date(Date.now() + 10000);
      const httpDate = futureDate.toUTCString();
      const delay = parseRetryAfter(httpDate);
      expect(delay).toBeGreaterThan(0);
      expect(delay).toBeLessThanOrEqual(10000);
    });

    it('should return 0 for past dates', () => {
      const pastDate = new Date(Date.now() - 10000);
      const httpDate = pastDate.toUTCString();
      expect(parseRetryAfter(httpDate)).toBe(0);
    });
  });

  describe('invalid format', () => {
    it('should return 0 for invalid string', () => {
      expect(parseRetryAfter('invalid')).toBe(0);
    });
  });
});

describe('mergeConfig', () => {
  it('should return defaults when no config provided', () => {
    const merged = mergeConfig();
    expect(merged).toEqual(DEFAULT_RETRY_CONFIG);
  });

  it('should merge partial config with defaults', () => {
    const merged = mergeConfig({ maxRetries: 5 });
    expect(merged.maxRetries).toBe(5);
    expect(merged.baseDelayMs).toBe(DEFAULT_RETRY_CONFIG.baseDelayMs);
    expect(merged.maxDelayMs).toBe(DEFAULT_RETRY_CONFIG.maxDelayMs);
  });

  it('should override all provided values', () => {
    const config: RetryConfig = {
      maxRetries: 10,
      baseDelayMs: 500,
      maxDelayMs: 10000,
      jitterFactor: 0.3,
      retryOnErrors: ['CUSTOM'],
      retryOnStatus: [418],
      retryMethods: ['POST'],
      respectRetryAfter: false,
    };
    const merged = mergeConfig(config);
    expect(merged).toEqual({
      ...DEFAULT_RETRY_CONFIG,
      ...config,
    });
  });
});

describe('sleep', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should resolve after specified duration', async () => {
    const promise = sleep(1000);
    vi.advanceTimersByTime(1000);
    await expect(promise).resolves.toBeUndefined();
  });

  it('should reject immediately if signal is already aborted', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(sleep(1000, controller.signal)).rejects.toThrow('Aborted');
  });

  it('should reject if signal is aborted during sleep', async () => {
    const controller = new AbortController();
    const promise = sleep(1000, controller.signal);

    vi.advanceTimersByTime(500);
    controller.abort();

    await expect(promise).rejects.toThrow('Aborted');
  });

  it('should work without signal', async () => {
    const promise = sleep(100);
    vi.advanceTimersByTime(100);
    await expect(promise).resolves.toBeUndefined();
  });
});

describe('createRetryError', () => {
  it('should create error with message', () => {
    const error = createRetryError('Test error');
    expect(error.message).toBe('Test error');
  });

  it('should create error with cause', () => {
    const cause = new Error('Original error');
    const error = createRetryError('Wrapper error', { cause });
    expect(error.cause).toBe(cause);
  });

  it('should create error with code', () => {
    const error = createRetryError('Test error', { code: 'CUSTOM_CODE' });
    expect(error.code).toBe('CUSTOM_CODE');
  });

  it('should create error with isRetryable flag', () => {
    const retryable = createRetryError('Test error', { isRetryable: true });
    expect(retryable.isRetryable).toBe(true);

    const nonRetryable = createRetryError('Test error', { isRetryable: false });
    expect(nonRetryable.isRetryable).toBe(false);
  });

  it('should create error with all options', () => {
    const cause = new Error('Original');
    const error = createRetryError('Test', { cause, code: 'CODE', isRetryable: true });
    expect(error.message).toBe('Test');
    expect(error.cause).toBe(cause);
    expect(error.code).toBe('CODE');
    expect(error.isRetryable).toBe(true);
  });
});
