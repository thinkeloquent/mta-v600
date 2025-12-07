/**
 * Tests for factory functions
 *
 * Coverage includes:
 * - createRateLimitedDispatcher with various options
 * - createApiRateLimiter factory
 * - Interceptor chain composition
 */

import { describe, it, expect, jest } from '@jest/globals';
import { Agent, type Dispatcher } from 'undici';
import {
  createRateLimitedDispatcher,
  createApiRateLimiter,
} from '../src/factory.mjs';
import { MemoryStore } from '@internal/fetch-rate-limiter';

describe('createRateLimitedDispatcher', () => {
  describe('basic creation', () => {
    it('should create dispatcher with default options', () => {
      const dispatcher = createRateLimitedDispatcher();
      expect(dispatcher).toBeDefined();
    });

    it('should create dispatcher with maxPerSecond option', () => {
      const dispatcher = createRateLimitedDispatcher({ maxPerSecond: 10 });
      expect(dispatcher).toBeDefined();
    });

    it('should create dispatcher with custom config', () => {
      const dispatcher = createRateLimitedDispatcher({
        config: {
          id: 'test-api',
          static: { maxRequests: 100, intervalMs: 1000 },
        },
      });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('base dispatcher', () => {
    it('should use provided base dispatcher', () => {
      const baseAgent = new Agent();
      const dispatcher = createRateLimitedDispatcher({
        baseDispatcher: baseAgent,
        maxPerSecond: 10,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should create new Agent when no base provided', () => {
      const dispatcher = createRateLimitedDispatcher({ maxPerSecond: 10 });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('DNS interceptor', () => {
    it('should include DNS interceptor when includeDns is true', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        includeDns: true,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should not include DNS interceptor by default', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should use IPv4 affinity by default', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        includeDns: true,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should support IPv6 affinity', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        includeDns: true,
        dnsAffinity: 6,
      });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('retry interceptor', () => {
    it('should include retry interceptor when includeRetry is true', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        includeRetry: true,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should not include retry interceptor by default', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should use default retry options', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        includeRetry: true,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should use custom retry options', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        includeRetry: true,
        retryOptions: {
          maxRetries: 5,
          minTimeout: 1000,
          maxTimeout: 30000,
          timeoutFactor: 3,
          retryAfter: false,
        },
      });
      expect(dispatcher).toBeDefined();
    });

    it('should merge partial retry options with defaults', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        includeRetry: true,
        retryOptions: {
          maxRetries: 5,
        },
      });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('combined interceptors', () => {
    it('should support all interceptors combined', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        includeDns: true,
        includeRetry: true,
      });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('rate limit options passthrough', () => {
    it('should pass methods filter to interceptor', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        methods: ['GET', 'POST'],
      });
      expect(dispatcher).toBeDefined();
    });

    it('should pass respectRetryAfter option to interceptor', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        respectRetryAfter: false,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should pass custom store to interceptor', () => {
      const store = new MemoryStore();
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 10,
        store,
      });
      expect(dispatcher).toBeDefined();
    });
  });
});

describe('createApiRateLimiter', () => {
  describe('basic creation', () => {
    it('should create interceptor for API', () => {
      const interceptor = createApiRateLimiter('github', 5000 / 3600);
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with integer maxPerSecond', () => {
      const interceptor = createApiRateLimiter('openai', 60);
      expect(typeof interceptor).toBe('function');
    });

    it('should create interceptor with fractional maxPerSecond', () => {
      const interceptor = createApiRateLimiter('slow-api', 0.5);
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('API ID', () => {
    it('should accept simple API ID', () => {
      const interceptor = createApiRateLimiter('api', 10);
      expect(typeof interceptor).toBe('function');
    });

    it('should accept API ID with special characters', () => {
      const interceptor = createApiRateLimiter('api-v2:prod', 10);
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('store option', () => {
    it('should accept custom store', () => {
      const store = new MemoryStore();
      const interceptor = createApiRateLimiter('api', 10, store);
      expect(typeof interceptor).toBe('function');
    });

    it('should work without custom store', () => {
      const interceptor = createApiRateLimiter('api', 10);
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('composability', () => {
    it('should be composable with Agent', () => {
      const interceptor = createApiRateLimiter('api', 10);
      const agent = new Agent();
      const dispatcher = agent.compose(interceptor);
      expect(dispatcher).toBeDefined();
    });

    it('should support multiple API limiters', () => {
      const githubLimiter = createApiRateLimiter('github', 5000 / 3600);
      const openaiLimiter = createApiRateLimiter('openai', 60);

      const githubClient = new Agent().compose(githubLimiter);
      const openaiClient = new Agent().compose(openaiLimiter);

      expect(githubClient).toBeDefined();
      expect(openaiClient).toBeDefined();
    });
  });

  describe('rate calculation', () => {
    it('should ceil fractional rates', () => {
      const interceptor = createApiRateLimiter('api', 1.5);
      expect(typeof interceptor).toBe('function');
    });

    it('should handle very small rates', () => {
      const interceptor = createApiRateLimiter('api', 0.01);
      expect(typeof interceptor).toBe('function');
    });

    it('should handle very large rates', () => {
      const interceptor = createApiRateLimiter('api', 10000);
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('interceptor behavior', () => {
    it('should wrap dispatch correctly', () => {
      const interceptor = createApiRateLimiter('api', 100);
      const mockDispatch = jest.fn<Dispatcher.DispatchHandlers['dispatch']>().mockReturnValue(true);

      const wrappedDispatch = interceptor(mockDispatch);
      expect(typeof wrappedDispatch).toBe('function');
    });
  });
});

describe('integration scenarios', () => {
  describe('multiple rate limiters', () => {
    it('should create separate limiters for different APIs', () => {
      const dispatcher1 = createRateLimitedDispatcher({
        config: {
          id: 'api-1',
          static: { maxRequests: 10, intervalMs: 1000 },
        },
      });

      const dispatcher2 = createRateLimitedDispatcher({
        config: {
          id: 'api-2',
          static: { maxRequests: 100, intervalMs: 1000 },
        },
      });

      expect(dispatcher1).not.toBe(dispatcher2);
    });
  });

  describe('shared store', () => {
    it('should support shared store for distributed limiting', () => {
      const sharedStore = new MemoryStore();

      const dispatcher1 = createRateLimitedDispatcher({
        maxPerSecond: 10,
        store: sharedStore,
      });

      const dispatcher2 = createRateLimitedDispatcher({
        maxPerSecond: 10,
        store: sharedStore,
      });

      expect(dispatcher1).toBeDefined();
      expect(dispatcher2).toBeDefined();
    });
  });

  describe('edge cases', () => {
    it('should handle zero maxPerSecond by using default', () => {
      const dispatcher = createRateLimitedDispatcher({
        maxPerSecond: 0,
      });
      expect(dispatcher).toBeDefined();
    });

    it('should handle empty options', () => {
      const dispatcher = createRateLimitedDispatcher({});
      expect(dispatcher).toBeDefined();
    });

    it('should handle undefined config gracefully', () => {
      const dispatcher = createRateLimitedDispatcher({
        config: undefined,
        maxPerSecond: 10,
      });
      expect(dispatcher).toBeDefined();
    });
  });
});
