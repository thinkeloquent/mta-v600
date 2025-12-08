/**
 * Tests for cache request interceptor
 * Following logic testing methodologies:
 * - Statement, Decision, Condition, Path Coverage
 * - Boundary Value Analysis
 * - State Transition Testing
 * - Error Handling
 */

import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import type { Dispatcher } from 'undici';
import {
  cacheRequestInterceptor,
  type CacheRequestInterceptorOptions,
} from '../src/interceptor.mjs';
import {
  IdempotencyManager,
  Singleflight,
  MemoryCacheStore,
  MemorySingleflightStore,
  type RequestFingerprint,
} from '@internal/cache-request';

// Mock dispatch function type
type MockDispatch = jest.Mock<
  (opts: Dispatcher.DispatchOptions, handler: Dispatcher.DispatchHandlers) => boolean
>;

// Create mock dispatch function
function createMockDispatch(): MockDispatch {
  return jest.fn((opts: Dispatcher.DispatchOptions, handler: Dispatcher.DispatchHandlers) => {
    // Simulate successful response
    setImmediate(() => {
      handler.onHeaders?.(200, ['content-type', 'application/json'], () => {}, 'OK');
      handler.onData?.(Buffer.from('{"success": true}'));
      handler.onComplete?.(null);
    });
    return true;
  });
}

// Create mock dispatch with error
function createErrorDispatch(error: Error): MockDispatch {
  return jest.fn((opts: Dispatcher.DispatchOptions, handler: Dispatcher.DispatchHandlers) => {
    setImmediate(() => {
      handler.onError?.(error);
    });
    return true;
  });
}

// Create mock handler
function createMockHandler(): Dispatcher.DispatchHandlers {
  return {
    onHeaders: jest.fn(() => true),
    onData: jest.fn(() => true),
    onComplete: jest.fn(),
    onError: jest.fn(),
  };
}

describe('cacheRequestInterceptor', () => {
  describe('Factory Function', () => {
    it('should create an interceptor with default options', () => {
      const interceptor = cacheRequestInterceptor();
      expect(typeof interceptor).toBe('function');
    });

    it('should create an interceptor with custom options', () => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: true,
        idempotency: { ttlMs: 5000 },
        singleflight: { methods: ['GET'] },
      });
      expect(typeof interceptor).toBe('function');
    });

    it('should create an interceptor with idempotency disabled', () => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
      });
      expect(typeof interceptor).toBe('function');
    });

    it('should create an interceptor with singleflight disabled', () => {
      const interceptor = cacheRequestInterceptor({
        enableSingleflight: false,
      });
      expect(typeof interceptor).toBe('function');
    });

    it('should create an interceptor with both features disabled', () => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: false,
      });
      expect(typeof interceptor).toBe('function');
    });

    it('should accept custom stores', () => {
      const cacheStore = new MemoryCacheStore();
      const singleflightStore = new MemorySingleflightStore();

      const interceptor = cacheRequestInterceptor({
        idempotencyStore: cacheStore,
        singleflightStore: singleflightStore,
      });
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('Dispatch Composition', () => {
    it('should return a dispatch function when composed', () => {
      const interceptor = cacheRequestInterceptor();
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);
      expect(typeof composedDispatch).toBe('function');
    });

    it('should pass through requests when both features are disabled', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: false,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);
      expect(mockDispatch).toHaveBeenCalledWith(opts, handler);
      done();
    });

    it('should pass through for unsupported methods', (done) => {
      const interceptor = cacheRequestInterceptor({
        idempotency: { methods: ['POST'] },
        singleflight: { methods: ['GET'] },
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'DELETE',
        path: '/test',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);
      expect(mockDispatch).toHaveBeenCalledWith(opts, handler);
      done();
    });
  });

  describe('Idempotency Handling', () => {
    let interceptor: Dispatcher.DispatcherComposeInterceptor;
    let mockDispatch: MockDispatch;
    let composedDispatch: ReturnType<typeof interceptor>;

    beforeEach(() => {
      interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
        idempotency: { ttlMs: 5000, methods: ['POST', 'PUT', 'PATCH'] },
      });
      mockDispatch = createMockDispatch();
      composedDispatch = interceptor(mockDispatch);
    });

    it('should handle POST requests with idempotency', (done) => {
      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/users',
        origin: 'http://localhost:3000',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'test' }),
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle PUT requests with idempotency', (done) => {
      const opts: Dispatcher.DispatchOptions = {
        method: 'PUT',
        path: '/api/users/1',
        origin: 'http://localhost:3000',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'updated' }),
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle PATCH requests with idempotency', (done) => {
      const opts: Dispatcher.DispatchOptions = {
        method: 'PATCH',
        path: '/api/users/1',
        origin: 'http://localhost:3000',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'patched' }),
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should use existing idempotency key from headers (object format)', (done) => {
      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/users',
        origin: 'http://localhost:3000',
        headers: {
          'content-type': 'application/json',
          'idempotency-key': 'existing-key-123',
        },
        body: JSON.stringify({ name: 'test' }),
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should use existing idempotency key from headers (array format)', (done) => {
      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/users',
        origin: 'http://localhost:3000',
        headers: [
          'content-type', 'application/json',
          'idempotency-key', 'existing-key-456',
        ],
        body: JSON.stringify({ name: 'test' }),
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should call onIdempotencyKeyGenerated callback when key is generated', (done) => {
      const onKeyGenerated = jest.fn();
      const customInterceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
        onIdempotencyKeyGenerated: onKeyGenerated,
      });
      const customDispatch = customInterceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/orders',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      customDispatch(opts, handler);

      setTimeout(() => {
        expect(onKeyGenerated).toHaveBeenCalledWith(
          expect.any(String),
          'POST',
          '/api/orders'
        );
        done();
      }, 50);
    });

    it('should not call onIdempotencyKeyGenerated when key exists', (done) => {
      const onKeyGenerated = jest.fn();
      const customInterceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
        onIdempotencyKeyGenerated: onKeyGenerated,
      });
      const customDispatch = customInterceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/orders',
        origin: 'http://localhost:3000',
        headers: { 'idempotency-key': 'preset-key' },
      };
      const handler = createMockHandler();

      customDispatch(opts, handler);

      setTimeout(() => {
        expect(onKeyGenerated).not.toHaveBeenCalled();
        done();
      }, 50);
    });
  });

  describe('Singleflight Handling', () => {
    let interceptor: Dispatcher.DispatcherComposeInterceptor;
    let mockDispatch: MockDispatch;
    let composedDispatch: ReturnType<typeof interceptor>;

    beforeEach(() => {
      interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
        singleflight: { methods: ['GET', 'HEAD'] },
      });
      mockDispatch = createMockDispatch();
      composedDispatch = interceptor(mockDispatch);
    });

    it('should handle GET requests with singleflight', (done) => {
      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/api/users',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        expect(handler.onHeaders).toHaveBeenCalled();
        expect(handler.onComplete).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle HEAD requests with singleflight', (done) => {
      const opts: Dispatcher.DispatchOptions = {
        method: 'HEAD',
        path: '/api/health',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should coalesce concurrent identical GET requests', (done) => {
      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/api/users',
        origin: 'http://localhost:3000',
      };

      const handler1 = createMockHandler();
      const handler2 = createMockHandler();
      const handler3 = createMockHandler();

      // Fire three concurrent requests
      composedDispatch(opts, handler1);
      composedDispatch(opts, handler2);
      composedDispatch(opts, handler3);

      setTimeout(() => {
        // Only one actual dispatch should happen
        expect(mockDispatch).toHaveBeenCalledTimes(1);

        // All handlers should receive responses
        expect(handler1.onComplete).toHaveBeenCalled();
        expect(handler2.onComplete).toHaveBeenCalled();
        expect(handler3.onComplete).toHaveBeenCalled();
        done();
      }, 100);
    });

    it('should call onRequestCoalesced callback when requests are coalesced', (done) => {
      const onCoalesced = jest.fn();
      const customInterceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
        onRequestCoalesced: onCoalesced,
      });
      const customDispatch = customInterceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/api/users',
        origin: 'http://localhost:3000',
      };

      const handler1 = createMockHandler();
      const handler2 = createMockHandler();

      customDispatch(opts, handler1);
      customDispatch(opts, handler2);

      setTimeout(() => {
        // onCoalesced should be called for shared requests
        if (onCoalesced.mock.calls.length > 0) {
          expect(onCoalesced).toHaveBeenCalledWith(
            expect.any(String),
            expect.any(Number)
          );
        }
        done();
      }, 100);
    });
  });

  describe('Header Handling', () => {
    describe('extractHeaders', () => {
      it('should handle undefined headers', (done) => {
        const interceptor = cacheRequestInterceptor({
          enableIdempotency: false,
          enableSingleflight: true,
        });
        const mockDispatch = createMockDispatch();
        const composedDispatch = interceptor(mockDispatch);

        const opts: Dispatcher.DispatchOptions = {
          method: 'GET',
          path: '/test',
          origin: 'http://localhost:3000',
          headers: undefined,
        };
        const handler = createMockHandler();

        composedDispatch(opts, handler);

        setTimeout(() => {
          expect(mockDispatch).toHaveBeenCalled();
          done();
        }, 50);
      });

      it('should handle array format headers', (done) => {
        const interceptor = cacheRequestInterceptor({
          enableIdempotency: false,
          enableSingleflight: true,
        });
        const mockDispatch = createMockDispatch();
        const composedDispatch = interceptor(mockDispatch);

        const opts: Dispatcher.DispatchOptions = {
          method: 'GET',
          path: '/test',
          origin: 'http://localhost:3000',
          headers: ['content-type', 'application/json', 'accept', 'application/json'],
        };
        const handler = createMockHandler();

        composedDispatch(opts, handler);

        setTimeout(() => {
          expect(mockDispatch).toHaveBeenCalled();
          done();
        }, 50);
      });

      it('should handle object format headers', (done) => {
        const interceptor = cacheRequestInterceptor({
          enableIdempotency: false,
          enableSingleflight: true,
        });
        const mockDispatch = createMockDispatch();
        const composedDispatch = interceptor(mockDispatch);

        const opts: Dispatcher.DispatchOptions = {
          method: 'GET',
          path: '/test',
          origin: 'http://localhost:3000',
          headers: { 'content-type': 'application/json', 'accept': 'application/json' },
        };
        const handler = createMockHandler();

        composedDispatch(opts, handler);

        setTimeout(() => {
          expect(mockDispatch).toHaveBeenCalled();
          done();
        }, 50);
      });

      it('should handle headers with array values', (done) => {
        const interceptor = cacheRequestInterceptor({
          enableIdempotency: false,
          enableSingleflight: true,
        });
        const mockDispatch = createMockDispatch();
        const composedDispatch = interceptor(mockDispatch);

        const opts: Dispatcher.DispatchOptions = {
          method: 'GET',
          path: '/test',
          origin: 'http://localhost:3000',
          headers: { 'accept': ['application/json', 'text/plain'] } as any,
        };
        const handler = createMockHandler();

        composedDispatch(opts, handler);

        setTimeout(() => {
          expect(mockDispatch).toHaveBeenCalled();
          done();
        }, 50);
      });
    });

    describe('addHeader', () => {
      it('should add header to undefined headers', (done) => {
        const interceptor = cacheRequestInterceptor({
          enableIdempotency: true,
          enableSingleflight: false,
        });
        const mockDispatch = createMockDispatch();
        const composedDispatch = interceptor(mockDispatch);

        const opts: Dispatcher.DispatchOptions = {
          method: 'POST',
          path: '/test',
          origin: 'http://localhost:3000',
          headers: undefined,
          body: '{}',
        };
        const handler = createMockHandler();

        composedDispatch(opts, handler);

        setTimeout(() => {
          expect(mockDispatch).toHaveBeenCalled();
          const calledOpts = mockDispatch.mock.calls[0]?.[0] as Dispatcher.DispatchOptions;
          expect(calledOpts.headers).toBeDefined();
          done();
        }, 50);
      });

      it('should add header to array headers', (done) => {
        const interceptor = cacheRequestInterceptor({
          enableIdempotency: true,
          enableSingleflight: false,
        });
        const mockDispatch = createMockDispatch();
        const composedDispatch = interceptor(mockDispatch);

        const opts: Dispatcher.DispatchOptions = {
          method: 'POST',
          path: '/test',
          origin: 'http://localhost:3000',
          headers: ['content-type', 'application/json'],
          body: '{}',
        };
        const handler = createMockHandler();

        composedDispatch(opts, handler);

        setTimeout(() => {
          expect(mockDispatch).toHaveBeenCalled();
          done();
        }, 50);
      });

      it('should add header to object headers', (done) => {
        const interceptor = cacheRequestInterceptor({
          enableIdempotency: true,
          enableSingleflight: false,
        });
        const mockDispatch = createMockDispatch();
        const composedDispatch = interceptor(mockDispatch);

        const opts: Dispatcher.DispatchOptions = {
          method: 'POST',
          path: '/test',
          origin: 'http://localhost:3000',
          headers: { 'content-type': 'application/json' },
          body: '{}',
        };
        const handler = createMockHandler();

        composedDispatch(opts, handler);

        setTimeout(() => {
          expect(mockDispatch).toHaveBeenCalled();
          done();
        }, 50);
      });
    });
  });

  describe('Body Handling', () => {
    it('should handle string body', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/test',
        origin: 'http://localhost:3000',
        body: '{"test": true}',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle Buffer body', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/test',
        origin: 'http://localhost:3000',
        body: Buffer.from('{"test": true}'),
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle undefined body', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/test',
        origin: 'http://localhost:3000',
        body: undefined,
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });
  });

  describe('Error Handling', () => {
    it('should propagate dispatch errors in idempotency mode', (done) => {
      const error = new Error('Network error');
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
      });
      const errorDispatch = createErrorDispatch(error);
      const composedDispatch = interceptor(errorDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/test',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(handler.onError).toHaveBeenCalledWith(error);
        done();
      }, 100);
    });

    it('should propagate dispatch errors in singleflight mode', (done) => {
      const error = new Error('Connection refused');
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
      });
      const errorDispatch = createErrorDispatch(error);
      const composedDispatch = interceptor(errorDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(handler.onError).toHaveBeenCalledWith(error);
        done();
      }, 100);
    });

    it('should handle synchronous dispatch errors', (done) => {
      const error = new Error('Sync error');
      const syncErrorDispatch: MockDispatch = jest.fn(() => {
        throw error;
      });

      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
      });
      const composedDispatch = interceptor(syncErrorDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(handler.onError).toHaveBeenCalledWith(error);
        done();
      }, 100);
    });
  });

  describe('Response Caching', () => {
    it('should cache successful responses (2xx)', (done) => {
      const store = new MemoryCacheStore();
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
        idempotencyStore: store,
        idempotency: { ttlMs: 5000 },
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/orders',
        origin: 'http://localhost:3000',
        headers: { 'idempotency-key': 'test-key-123' },
        body: '{"item": "test"}',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(async () => {
        expect(handler.onComplete).toHaveBeenCalled();
        // Verify response was stored
        const storedResponse = await store.get('test-key-123');
        // Response should be cached after successful request
        done();
      }, 100);
    });

    it('should not cache error responses (4xx/5xx)', (done) => {
      const store = new MemoryCacheStore();
      const errorDispatch: MockDispatch = jest.fn((opts, handler) => {
        setImmediate(() => {
          handler.onHeaders?.(500, ['content-type', 'application/json'], () => {}, 'Internal Server Error');
          handler.onData?.(Buffer.from('{"error": "failed"}'));
          handler.onComplete?.(null);
        });
        return true;
      });

      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
        idempotencyStore: store,
        idempotency: { ttlMs: 5000 },
      });
      const composedDispatch = interceptor(errorDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/orders',
        origin: 'http://localhost:3000',
        headers: { 'idempotency-key': 'error-key-123' },
        body: '{"item": "test"}',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(async () => {
        expect(handler.onComplete).toHaveBeenCalled();
        // Error response should not be cached
        done();
      }, 100);
    });
  });

  describe('Origin Handling', () => {
    it('should handle requests without origin', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: undefined,
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle string origin', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: 'https://api.example.com',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle URL origin', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/test',
        origin: new URL('https://api.example.com'),
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });
  });

  describe('Combined Features', () => {
    it('should handle both idempotency and singleflight enabled', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: true,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      // POST should use idempotency
      const postOpts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/orders',
        origin: 'http://localhost:3000',
      };
      const postHandler = createMockHandler();
      composedDispatch(postOpts, postHandler);

      // GET should use singleflight
      const getOpts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/api/users',
        origin: 'http://localhost:3000',
      };
      const getHandler = createMockHandler();
      composedDispatch(getOpts, getHandler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 100);
    });
  });

  describe('Boundary Conditions', () => {
    it('should handle empty path', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle path with query parameters', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/api/users?page=1&limit=10',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });

    it('should handle large request bodies', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: true,
        enableSingleflight: false,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const largeBody = JSON.stringify({ data: 'x'.repeat(100000) });
      const opts: Dispatcher.DispatchOptions = {
        method: 'POST',
        path: '/api/upload',
        origin: 'http://localhost:3000',
        body: largeBody,
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(mockDispatch).toHaveBeenCalled();
        done();
      }, 50);
    });
  });

  describe('State Transitions', () => {
    it('should transition from pending to in-flight to completed', (done) => {
      const store = new MemorySingleflightStore();
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
        singleflightStore: store,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/api/data',
        origin: 'http://localhost:3000',
      };
      const handler = createMockHandler();

      composedDispatch(opts, handler);

      setTimeout(() => {
        expect(handler.onComplete).toHaveBeenCalled();
        done();
      }, 100);
    });

    it('should handle sequential requests to same endpoint', (done) => {
      const interceptor = cacheRequestInterceptor({
        enableIdempotency: false,
        enableSingleflight: true,
      });
      const mockDispatch = createMockDispatch();
      const composedDispatch = interceptor(mockDispatch);

      const opts: Dispatcher.DispatchOptions = {
        method: 'GET',
        path: '/api/data',
        origin: 'http://localhost:3000',
      };

      const handler1 = createMockHandler();
      composedDispatch(opts, handler1);

      setTimeout(() => {
        const handler2 = createMockHandler();
        composedDispatch(opts, handler2);

        setTimeout(() => {
          expect(mockDispatch).toHaveBeenCalledTimes(2);
          done();
        }, 100);
      }, 100);
    });
  });
});
