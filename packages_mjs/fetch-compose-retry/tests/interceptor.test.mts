/**
 * Tests for fetch-compose-retry interceptor
 *
 * Test coverage includes:
 * - Statement coverage: All executable statements
 * - Decision/Branch coverage: All boolean decisions (if/else)
 * - Path coverage: Success paths, retry paths, failure paths
 * - Boundary testing: Edge cases for retries and delays
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { retryInterceptor, type RetryInterceptorOptions } from '../src/interceptor.mjs';
import type { Dispatcher } from 'undici';

describe('retryInterceptor', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('creation', () => {
    it('should return a DispatcherComposeInterceptor function', () => {
      const interceptor = retryInterceptor();
      expect(typeof interceptor).toBe('function');
    });

    it('should accept options', () => {
      const options: RetryInterceptorOptions = {
        maxRetries: 5,
        baseDelayMs: 500,
        maxDelayMs: 10000,
      };
      const interceptor = retryInterceptor(options);
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('method filtering', () => {
    it('should pass through non-retryable methods immediately', async () => {
      const interceptor = retryInterceptor();
      const mockDispatch = vi.fn().mockReturnValue(true);
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/test',
        origin: 'https://example.com',
      };
      const handler = createMockHandler();

      dispatch(opts, handler);

      expect(mockDispatch).toHaveBeenCalledWith(opts, handler);
    });

    it('should wrap retryable methods', async () => {
      const interceptor = retryInterceptor();
      const mockDispatch = vi.fn().mockReturnValue(true);
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };
      const handler = createMockHandler();

      dispatch(opts, handler);

      // Should have been called with a wrapped handler
      expect(mockDispatch).toHaveBeenCalled();
      const [, wrappedHandler] = mockDispatch.mock.calls[0];
      expect(wrappedHandler).not.toBe(handler);
    });
  });

  describe('success path', () => {
    it('should pass through on 2xx response', async () => {
      const onSuccess = vi.fn();
      const interceptor = retryInterceptor({ onSuccess });
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        // Simulate successful response
        handler.onHeaders?.(200, [], () => {}, 'OK');
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };
      const handler = createMockHandler();

      dispatch(opts, handler);

      expect(handler.onHeaders).toHaveBeenCalledWith(200, [], expect.any(Function), 'OK');
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  describe('retry on status', () => {
    it('should retry on 429 status', async () => {
      vi.spyOn(Math, 'random').mockReturnValue(0.5);
      const onRetry = vi.fn();
      const interceptor = retryInterceptor({
        maxRetries: 3,
        baseDelayMs: 100,
        jitterFactor: 0,
        onRetry,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        if (callCount === 1) {
          // First call: return 429
          handler.onHeaders?.(429, [], () => {}, 'Too Many Requests');
        } else {
          // Second call: return 200
          handler.onHeaders?.(200, [], () => {}, 'OK');
        }
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };
      const handler = createMockHandler();

      dispatch(opts, handler);

      // Wait for retry timeout
      await vi.advanceTimersByTimeAsync(200);

      expect(onRetry).toHaveBeenCalled();
      expect(callCount).toBe(2);
    });

    it('should retry on 500 status', async () => {
      const interceptor = retryInterceptor({
        maxRetries: 3,
        baseDelayMs: 100,
        jitterFactor: 0,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        if (callCount === 1) {
          handler.onHeaders?.(500, [], () => {}, 'Internal Server Error');
        } else {
          handler.onHeaders?.(200, [], () => {}, 'OK');
        }
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(200);

      expect(callCount).toBe(2);
    });

    it('should retry on 502 status', async () => {
      const interceptor = retryInterceptor({
        maxRetries: 2,
        baseDelayMs: 100,
        jitterFactor: 0,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        handler.onHeaders?.(502, [], () => {}, 'Bad Gateway');
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(1000);

      expect(callCount).toBe(3); // initial + 2 retries
    });

    it('should retry on 503 status', async () => {
      const interceptor = retryInterceptor({
        maxRetries: 1,
        baseDelayMs: 100,
        jitterFactor: 0,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        handler.onHeaders?.(503, [], () => {}, 'Service Unavailable');
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(500);

      expect(callCount).toBe(2);
    });

    it('should retry on 504 status', async () => {
      const interceptor = retryInterceptor({
        maxRetries: 1,
        baseDelayMs: 100,
        jitterFactor: 0,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        handler.onHeaders?.(504, [], () => {}, 'Gateway Timeout');
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(500);

      expect(callCount).toBe(2);
    });

    it('should not retry on 4xx client errors', async () => {
      const interceptor = retryInterceptor({ maxRetries: 3 });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        handler.onHeaders?.(400, [], () => {}, 'Bad Request');
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };
      const handler = createMockHandler();

      dispatch(opts, handler);
      await vi.advanceTimersByTimeAsync(1000);

      expect(callCount).toBe(1);
      expect(handler.onHeaders).toHaveBeenCalledWith(400, [], expect.any(Function), 'Bad Request');
    });
  });

  describe('Retry-After header', () => {
    it('should respect Retry-After header in seconds', async () => {
      const interceptor = retryInterceptor({
        maxRetries: 3,
        respectRetryAfter: true,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        if (callCount === 1) {
          // Return 429 with Retry-After header
          handler.onHeaders?.(429, ['retry-after', '2'], () => {}, 'Too Many Requests');
        } else {
          handler.onHeaders?.(200, [], () => {}, 'OK');
        }
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());

      // Should wait for Retry-After time
      await vi.advanceTimersByTimeAsync(2500);

      expect(callCount).toBe(2);
    });
  });

  describe('retry on error', () => {
    it('should retry on network errors', async () => {
      const onRetry = vi.fn();
      const interceptor = retryInterceptor({
        maxRetries: 2,
        baseDelayMs: 100,
        jitterFactor: 0,
        onRetry,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        if (callCount === 1) {
          const error = new Error('ECONNRESET');
          (error as Error & { code: string }).code = 'ECONNRESET';
          handler.onError?.(error);
        } else {
          handler.onHeaders?.(200, [], () => {}, 'OK');
        }
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(500);

      expect(callCount).toBe(2);
      expect(onRetry).toHaveBeenCalled();
    });

    it('should not retry on non-retryable errors', async () => {
      const interceptor = retryInterceptor({ maxRetries: 3 });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        handler.onError?.(new Error('validation error'));
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };
      const handler = createMockHandler();

      dispatch(opts, handler);
      await vi.advanceTimersByTimeAsync(1000);

      expect(callCount).toBe(1);
      expect(handler.onError).toHaveBeenCalled();
    });
  });

  describe('max retries', () => {
    it('should not exceed maxRetries', async () => {
      const interceptor = retryInterceptor({
        maxRetries: 2,
        baseDelayMs: 100,
        jitterFactor: 0,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        handler.onHeaders?.(503, [], () => {}, 'Service Unavailable');
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(5000);

      expect(callCount).toBe(3); // initial + 2 retries
    });
  });

  describe('callbacks', () => {
    it('should call onRetry callback before each retry', async () => {
      const onRetry = vi.fn();
      const interceptor = retryInterceptor({
        maxRetries: 2,
        baseDelayMs: 100,
        jitterFactor: 0,
        onRetry,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        if (callCount <= 2) {
          handler.onHeaders?.(503, [], () => {}, 'Service Unavailable');
        } else {
          handler.onHeaders?.(200, [], () => {}, 'OK');
        }
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(1000);

      expect(onRetry).toHaveBeenCalledTimes(2);
      expect(onRetry).toHaveBeenCalledWith(expect.any(Error), 1, expect.any(Number));
      expect(onRetry).toHaveBeenCalledWith(expect.any(Error), 2, expect.any(Number));
    });

    it('should call onSuccess callback on success', async () => {
      const onSuccess = vi.fn();
      const interceptor = retryInterceptor({ onSuccess });

      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        handler.onHeaders?.(200, [], () => {}, 'OK');
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());

      expect(onSuccess).toHaveBeenCalledWith(0, expect.any(Number));
    });

    it('should call onSuccess with retry count after retries', async () => {
      const onSuccess = vi.fn();
      const interceptor = retryInterceptor({
        maxRetries: 2,
        baseDelayMs: 100,
        jitterFactor: 0,
        onSuccess,
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        if (callCount === 1) {
          handler.onHeaders?.(503, [], () => {}, 'Service Unavailable');
        } else {
          handler.onHeaders?.(200, [], () => {}, 'OK');
        }
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(500);

      expect(onSuccess).toHaveBeenCalledWith(1, expect.any(Number));
    });
  });

  describe('custom retry configuration', () => {
    it('should use custom retryOnStatus list', async () => {
      const interceptor = retryInterceptor({
        maxRetries: 2,
        baseDelayMs: 100,
        jitterFactor: 0,
        retryOnStatus: [418],
      });

      let callCount = 0;
      const mockDispatch = vi.fn().mockImplementation((opts, handler) => {
        callCount++;
        if (callCount === 1) {
          handler.onHeaders?.(418, [], () => {}, "I'm a teapot");
        } else {
          handler.onHeaders?.(200, [], () => {}, 'OK');
        }
        return true;
      });
      const dispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://example.com',
      };

      dispatch(opts, createMockHandler());
      await vi.advanceTimersByTimeAsync(500);

      expect(callCount).toBe(2);
    });
  });
});

/**
 * Helper to create a mock handler
 */
function createMockHandler(): Dispatcher.DispatchHandlers {
  return {
    onConnect: vi.fn(),
    onHeaders: vi.fn(),
    onData: vi.fn(),
    onComplete: vi.fn(),
    onError: vi.fn(),
    onUpgrade: vi.fn(),
  };
}
