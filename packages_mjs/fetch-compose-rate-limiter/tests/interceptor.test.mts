/**
 * Tests for rate limit interceptor
 *
 * Coverage includes:
 * - Interceptor creation with various options
 * - Header parsing (Retry-After, X-RateLimit-*)
 * - Method filtering
 * - Integration with undici compose pattern
 */

import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import {
  rateLimitInterceptor,
  type RateLimitInterceptorOptions,
} from '../src/interceptor.mjs';
import type { Dispatcher } from 'undici';

describe('rateLimitInterceptor', () => {
  describe('interceptor creation', () => {
    it('should create interceptor with default options', () => {
      const interceptor = rateLimitInterceptor();
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with maxPerSecond option', () => {
      const interceptor = rateLimitInterceptor({ maxPerSecond: 10 });
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with custom config', () => {
      const interceptor = rateLimitInterceptor({
        config: {
          id: 'test-api',
          static: { maxRequests: 100, intervalMs: 60000 },
        },
      });
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with methods filter', () => {
      const interceptor = rateLimitInterceptor({
        maxPerSecond: 10,
        methods: ['GET', 'POST'],
      });
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with respectRetryAfter option', () => {
      const interceptor = rateLimitInterceptor({
        maxPerSecond: 10,
        respectRetryAfter: false,
      });
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('dispatch wrapping', () => {
    it('should wrap dispatch function', () => {
      const interceptor = rateLimitInterceptor({ maxPerSecond: 10 });
      const mockDispatch = jest.fn<Dispatcher.DispatchHandlers['dispatch']>().mockReturnValue(true);

      const wrappedDispatch = interceptor(mockDispatch);
      expect(typeof wrappedDispatch).toBe('function');
    });

    it('should pass through requests to underlying dispatch', async () => {
      const interceptor = rateLimitInterceptor({ maxPerSecond: 1000 });
      let dispatchCalled = false;

      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
        dispatchCalled = true;
        handler.onHeaders?.(200, [], () => {}, 'OK');
        handler.onComplete?.(null);
        return true;
      };

      const wrappedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'http://localhost',
      };

      const handler: Dispatcher.DispatchHandlers = {
        onHeaders: jest.fn(),
        onData: jest.fn(),
        onComplete: jest.fn(),
        onError: jest.fn(),
      };

      wrappedDispatch(opts, handler);

      // Wait for rate limiter scheduling
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(dispatchCalled).toBe(true);
    });

    it('should filter by methods when specified', async () => {
      const interceptor = rateLimitInterceptor({
        maxPerSecond: 10,
        methods: ['POST'],
      });

      let dispatchCallCount = 0;
      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = () => {
        dispatchCallCount++;
        return true;
      };

      const wrappedDispatch = interceptor(mockDispatch);

      // GET should bypass rate limiting (immediate dispatch)
      wrappedDispatch(
        { method: 'GET', path: '/test', origin: 'http://localhost' },
        { onError: jest.fn() }
      );

      expect(dispatchCallCount).toBe(1);
    });
  });

  describe('parseRetryAfter helper', () => {
    it('should be tested via interceptor behavior with 429 response', async () => {
      const interceptor = rateLimitInterceptor({
        maxPerSecond: 100,
        respectRetryAfter: true,
      });

      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
        // Simulate 429 with Retry-After header
        const headers = ['retry-after', '5'];
        handler.onHeaders?.(429, headers, () => {}, 'Too Many Requests');
        handler.onComplete?.(null);
        return true;
      };

      const wrappedDispatch = interceptor(mockDispatch);
      const headerHandler = jest.fn();

      wrappedDispatch(
        { method: 'GET', path: '/test', origin: 'http://localhost' },
        {
          onHeaders: headerHandler,
          onComplete: jest.fn(),
          onError: jest.fn(),
        }
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(headerHandler).toHaveBeenCalledWith(
        429,
        expect.any(Array),
        expect.any(Function),
        'Too Many Requests'
      );
    });
  });

  describe('header parsing', () => {
    it('should handle X-RateLimit headers', async () => {
      const interceptor = rateLimitInterceptor({
        maxPerSecond: 100,
        respectRetryAfter: true,
      });

      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
        const headers = [
          'x-ratelimit-remaining',
          '99',
          'x-ratelimit-reset',
          String(Math.floor(Date.now() / 1000) + 60),
        ];
        handler.onHeaders?.(200, headers, () => {}, 'OK');
        handler.onComplete?.(null);
        return true;
      };

      const wrappedDispatch = interceptor(mockDispatch);
      const headerHandler = jest.fn();

      wrappedDispatch(
        { method: 'GET', path: '/test', origin: 'http://localhost' },
        {
          onHeaders: headerHandler,
          onComplete: jest.fn(),
          onError: jest.fn(),
        }
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(headerHandler).toHaveBeenCalled();
    });

    it('should handle missing headers gracefully', async () => {
      const interceptor = rateLimitInterceptor({
        maxPerSecond: 100,
        respectRetryAfter: true,
      });

      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
        handler.onHeaders?.(200, null, () => {}, 'OK');
        handler.onComplete?.(null);
        return true;
      };

      const wrappedDispatch = interceptor(mockDispatch);

      wrappedDispatch(
        { method: 'GET', path: '/test', origin: 'http://localhost' },
        {
          onHeaders: jest.fn(),
          onComplete: jest.fn(),
          onError: jest.fn(),
        }
      );

      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    it('should handle Retry-After as HTTP-date format', async () => {
      const interceptor = rateLimitInterceptor({
        maxPerSecond: 100,
        respectRetryAfter: true,
      });

      const futureDate = new Date(Date.now() + 5000).toUTCString();

      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
        const headers = ['retry-after', futureDate];
        handler.onHeaders?.(429, headers, () => {}, 'Too Many Requests');
        handler.onComplete?.(null);
        return true;
      };

      const wrappedDispatch = interceptor(mockDispatch);

      wrappedDispatch(
        { method: 'GET', path: '/test', origin: 'http://localhost' },
        {
          onHeaders: jest.fn(),
          onComplete: jest.fn(),
          onError: jest.fn(),
        }
      );

      await new Promise((resolve) => setTimeout(resolve, 50));
    });
  });

  describe('error handling', () => {
    it('should propagate dispatch errors to handler', async () => {
      const interceptor = rateLimitInterceptor({ maxPerSecond: 100 });

      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
        handler.onError?.(new Error('Connection failed'));
        return true;
      };

      const wrappedDispatch = interceptor(mockDispatch);
      const errorHandler = jest.fn();

      wrappedDispatch(
        { method: 'GET', path: '/test', origin: 'http://localhost' },
        {
          onHeaders: jest.fn(),
          onComplete: jest.fn(),
          onError: errorHandler,
        }
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(errorHandler).toHaveBeenCalled();
    });

    it('should handle dispatch returning false', async () => {
      const interceptor = rateLimitInterceptor({ maxPerSecond: 100 });

      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = () => false;

      const wrappedDispatch = interceptor(mockDispatch);
      const errorHandler = jest.fn();

      wrappedDispatch(
        { method: 'GET', path: '/test', origin: 'http://localhost' },
        {
          onHeaders: jest.fn(),
          onComplete: jest.fn(),
          onError: errorHandler,
        }
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(errorHandler).toHaveBeenCalled();
    });
  });

  describe('metadata tracking', () => {
    it('should include request metadata in rate limiter', async () => {
      const interceptor = rateLimitInterceptor({ maxPerSecond: 100 });

      const mockDispatch: Dispatcher.DispatchHandlers['dispatch'] = (opts, handler) => {
        handler.onHeaders?.(200, [], () => {}, 'OK');
        handler.onComplete?.(null);
        return true;
      };

      const wrappedDispatch = interceptor(mockDispatch);

      wrappedDispatch(
        {
          method: 'POST',
          path: '/api/users',
          origin: 'https://api.example.com',
        },
        {
          onHeaders: jest.fn(),
          onComplete: jest.fn(),
          onError: jest.fn(),
        }
      );

      await new Promise((resolve) => setTimeout(resolve, 50));
    });
  });

  describe('interceptor return value', () => {
    it('should always return true from wrapped dispatch', () => {
      const interceptor = rateLimitInterceptor({ maxPerSecond: 10 });
      const mockDispatch = jest.fn<Dispatcher.DispatchHandlers['dispatch']>().mockReturnValue(true);

      const wrappedDispatch = interceptor(mockDispatch);

      const result = wrappedDispatch(
        { method: 'GET', path: '/test', origin: 'http://localhost' },
        { onError: jest.fn() }
      );

      expect(result).toBe(true);
    });
  });
});
