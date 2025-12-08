/**
 * Tests for cache request factory functions
 * Following logic testing methodologies:
 * - Statement Coverage
 * - Decision Coverage
 * - Function Composition Testing
 * - Integration Testing
 */

import { jest, describe, it, expect, beforeEach } from '@jest/globals';
import { Agent, type Dispatcher } from 'undici';
import {
  createCacheRequestDispatcher,
  createCacheRequestAgent,
  composeCacheRequest,
} from '../src/factory.mjs';
import { cacheRequestInterceptor } from '../src/interceptor.mjs';
import {
  MemoryCacheStore,
  MemorySingleflightStore,
} from '@internal/cache-request';

describe('Factory Functions', () => {
  describe('createCacheRequestDispatcher', () => {
    it('should create a dispatcher from an Agent', () => {
      const baseAgent = new Agent();
      const dispatcher = createCacheRequestDispatcher(baseAgent);

      expect(dispatcher).toBeDefined();
      expect(typeof dispatcher.dispatch).toBe('function');
    });

    it('should create a dispatcher with default options', () => {
      const baseAgent = new Agent();
      const dispatcher = createCacheRequestDispatcher(baseAgent);

      expect(dispatcher).toBeDefined();
    });

    it('should create a dispatcher with custom options', () => {
      const baseAgent = new Agent();
      const dispatcher = createCacheRequestDispatcher(baseAgent, {
        enableIdempotency: true,
        enableSingleflight: true,
        idempotency: { ttlMs: 10000 },
        singleflight: { methods: ['GET'] },
      });

      expect(dispatcher).toBeDefined();
    });

    it('should create a dispatcher with idempotency only', () => {
      const baseAgent = new Agent();
      const dispatcher = createCacheRequestDispatcher(baseAgent, {
        enableIdempotency: true,
        enableSingleflight: false,
      });

      expect(dispatcher).toBeDefined();
    });

    it('should create a dispatcher with singleflight only', () => {
      const baseAgent = new Agent();
      const dispatcher = createCacheRequestDispatcher(baseAgent, {
        enableIdempotency: false,
        enableSingleflight: true,
      });

      expect(dispatcher).toBeDefined();
    });

    it('should create a dispatcher with custom stores', () => {
      const baseAgent = new Agent();
      const cacheStore = new MemoryCacheStore();
      const singleflightStore = new MemorySingleflightStore();

      const dispatcher = createCacheRequestDispatcher(baseAgent, {
        idempotencyStore: cacheStore,
        singleflightStore: singleflightStore,
      });

      expect(dispatcher).toBeDefined();
    });

    it('should create a dispatcher with callbacks', () => {
      const baseAgent = new Agent();
      const onKeyGenerated = jest.fn();
      const onCoalesced = jest.fn();

      const dispatcher = createCacheRequestDispatcher(baseAgent, {
        onIdempotencyKeyGenerated: onKeyGenerated,
        onRequestCoalesced: onCoalesced,
      });

      expect(dispatcher).toBeDefined();
    });

    it('should accept composed dispatcher as base', () => {
      const baseAgent = new Agent();
      const composedBase = baseAgent.compose(
        cacheRequestInterceptor({ enableIdempotency: false, enableSingleflight: false })
      );

      const dispatcher = createCacheRequestDispatcher(composedBase, {
        enableIdempotency: true,
      });

      expect(dispatcher).toBeDefined();
    });
  });

  describe('createCacheRequestAgent', () => {
    it('should create an agent with default options', () => {
      const agent = createCacheRequestAgent();

      expect(agent).toBeDefined();
      expect(typeof agent.dispatch).toBe('function');
    });

    it('should create an agent with custom cache request options', () => {
      const agent = createCacheRequestAgent({
        enableIdempotency: true,
        enableSingleflight: true,
        idempotency: { ttlMs: 30000 },
      });

      expect(agent).toBeDefined();
    });

    it('should create an agent with custom agent options', () => {
      const agent = createCacheRequestAgent(
        { enableIdempotency: true },
        {
          connections: 10,
          keepAliveTimeout: 5000,
          pipelining: 1,
        }
      );

      expect(agent).toBeDefined();
    });

    it('should create an agent with both options', () => {
      const agent = createCacheRequestAgent(
        {
          enableIdempotency: true,
          enableSingleflight: true,
          idempotency: { ttlMs: 60000, methods: ['POST', 'PUT'] },
          singleflight: { methods: ['GET', 'HEAD'] },
        },
        {
          connections: 5,
        }
      );

      expect(agent).toBeDefined();
    });

    it('should create an agent with custom stores', () => {
      const cacheStore = new MemoryCacheStore();
      const singleflightStore = new MemorySingleflightStore();

      const agent = createCacheRequestAgent({
        idempotencyStore: cacheStore,
        singleflightStore: singleflightStore,
      });

      expect(agent).toBeDefined();
    });

    it('should create an agent with event callbacks', () => {
      const onKeyGenerated = jest.fn();
      const onCoalesced = jest.fn();

      const agent = createCacheRequestAgent({
        onIdempotencyKeyGenerated: onKeyGenerated,
        onRequestCoalesced: onCoalesced,
      });

      expect(agent).toBeDefined();
    });

    it('should create an agent with undefined options', () => {
      const agent = createCacheRequestAgent(undefined, undefined);

      expect(agent).toBeDefined();
    });
  });

  describe('composeCacheRequest', () => {
    it('should compose cache request with empty interceptor array', () => {
      const result = composeCacheRequest([]);

      expect(result).toHaveLength(1);
      expect(typeof result[0]).toBe('function');
    });

    it('should compose cache request with single interceptor', () => {
      const otherInterceptor: Dispatcher.DispatcherComposeInterceptor =
        (dispatch) => dispatch;

      const result = composeCacheRequest([otherInterceptor]);

      expect(result).toHaveLength(2);
      expect(typeof result[0]).toBe('function');
      expect(result[1]).toBe(otherInterceptor);
    });

    it('should compose cache request with multiple interceptors', () => {
      const interceptor1: Dispatcher.DispatcherComposeInterceptor =
        (dispatch) => dispatch;
      const interceptor2: Dispatcher.DispatcherComposeInterceptor =
        (dispatch) => dispatch;
      const interceptor3: Dispatcher.DispatcherComposeInterceptor =
        (dispatch) => dispatch;

      const result = composeCacheRequest([interceptor1, interceptor2, interceptor3]);

      expect(result).toHaveLength(4);
      expect(typeof result[0]).toBe('function'); // cache request interceptor
      expect(result[1]).toBe(interceptor1);
      expect(result[2]).toBe(interceptor2);
      expect(result[3]).toBe(interceptor3);
    });

    it('should place cache request interceptor first', () => {
      const otherInterceptor: Dispatcher.DispatcherComposeInterceptor =
        (dispatch) => dispatch;

      const result = composeCacheRequest([otherInterceptor]);

      // First interceptor should be the cache request interceptor
      expect(result[0]).not.toBe(otherInterceptor);
      expect(result[1]).toBe(otherInterceptor);
    });

    it('should compose with custom cache request options', () => {
      const otherInterceptor: Dispatcher.DispatcherComposeInterceptor =
        (dispatch) => dispatch;

      const result = composeCacheRequest([otherInterceptor], {
        enableIdempotency: true,
        enableSingleflight: false,
        idempotency: { ttlMs: 5000 },
      });

      expect(result).toHaveLength(2);
    });

    it('should compose with custom stores', () => {
      const cacheStore = new MemoryCacheStore();
      const singleflightStore = new MemorySingleflightStore();

      const result = composeCacheRequest([], {
        idempotencyStore: cacheStore,
        singleflightStore: singleflightStore,
      });

      expect(result).toHaveLength(1);
    });

    it('should compose with event callbacks', () => {
      const onKeyGenerated = jest.fn();
      const onCoalesced = jest.fn();

      const result = composeCacheRequest([], {
        onIdempotencyKeyGenerated: onKeyGenerated,
        onRequestCoalesced: onCoalesced,
      });

      expect(result).toHaveLength(1);
    });

    it('should compose with undefined options', () => {
      const result = composeCacheRequest([], undefined);

      expect(result).toHaveLength(1);
    });

    it('should work with Agent.compose', () => {
      const agent = new Agent();
      const otherInterceptor: Dispatcher.DispatcherComposeInterceptor =
        (dispatch) => dispatch;

      const interceptorChain = composeCacheRequest([otherInterceptor], {
        enableIdempotency: true,
      });

      const composedAgent = agent.compose(...interceptorChain);

      expect(composedAgent).toBeDefined();
      expect(typeof composedAgent.dispatch).toBe('function');
    });
  });

  describe('Integration Tests', () => {
    it('should chain multiple factory functions', () => {
      const agent1 = createCacheRequestAgent({
        enableIdempotency: true,
        enableSingleflight: false,
      });

      const agent2 = createCacheRequestDispatcher(new Agent(), {
        enableIdempotency: false,
        enableSingleflight: true,
      });

      expect(agent1).toBeDefined();
      expect(agent2).toBeDefined();
    });

    it('should work with spread operator on composeCacheRequest', () => {
      const agent = new Agent();
      const interceptors = composeCacheRequest([], {
        enableIdempotency: true,
        enableSingleflight: true,
      });

      const composed = agent.compose(...interceptors);

      expect(composed).toBeDefined();
    });

    it('should maintain interceptor order in composition', () => {
      const callOrder: string[] = [];

      const firstInterceptor: Dispatcher.DispatcherComposeInterceptor = (dispatch) => {
        return (opts, handler) => {
          callOrder.push('first');
          return dispatch(opts, handler);
        };
      };

      const secondInterceptor: Dispatcher.DispatcherComposeInterceptor = (dispatch) => {
        return (opts, handler) => {
          callOrder.push('second');
          return dispatch(opts, handler);
        };
      };

      const chain = composeCacheRequest([firstInterceptor, secondInterceptor], {
        enableIdempotency: false,
        enableSingleflight: false,
      });

      // Verify chain order
      expect(chain).toHaveLength(3);
      expect(chain[1]).toBe(firstInterceptor);
      expect(chain[2]).toBe(secondInterceptor);
    });
  });

  describe('Type Safety', () => {
    it('should accept valid CacheRequestInterceptorOptions', () => {
      const validOptions = {
        enableIdempotency: true,
        enableSingleflight: true,
        idempotency: {
          ttlMs: 5000,
          methods: ['POST', 'PUT'] as const,
          headerName: 'X-Idempotency-Key',
        },
        singleflight: {
          methods: ['GET', 'HEAD'] as const,
        },
      };

      const dispatcher = createCacheRequestDispatcher(new Agent(), validOptions);
      expect(dispatcher).toBeDefined();
    });

    it('should accept valid Agent.Options', () => {
      const agentOptions: Agent.Options = {
        connections: 10,
        keepAliveTimeout: 5000,
        pipelining: 1,
      };

      const agent = createCacheRequestAgent({}, agentOptions);
      expect(agent).toBeDefined();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty cache request options', () => {
      const agent = createCacheRequestAgent({});
      expect(agent).toBeDefined();
    });

    it('should handle partial idempotency options', () => {
      const agent = createCacheRequestAgent({
        idempotency: { ttlMs: 1000 },
      });
      expect(agent).toBeDefined();
    });

    it('should handle partial singleflight options', () => {
      const agent = createCacheRequestAgent({
        singleflight: { methods: ['GET'] },
      });
      expect(agent).toBeDefined();
    });

    it('should handle both features disabled', () => {
      const agent = createCacheRequestAgent({
        enableIdempotency: false,
        enableSingleflight: false,
      });
      expect(agent).toBeDefined();
    });

    it('should handle composeCacheRequest with all options', () => {
      const cacheStore = new MemoryCacheStore();
      const singleflightStore = new MemorySingleflightStore();
      const onKeyGenerated = jest.fn();
      const onCoalesced = jest.fn();

      const result = composeCacheRequest([], {
        enableIdempotency: true,
        enableSingleflight: true,
        idempotency: {
          ttlMs: 10000,
          methods: ['POST', 'PUT', 'PATCH'],
          headerName: 'X-Request-Id',
        },
        singleflight: {
          methods: ['GET', 'HEAD', 'OPTIONS'],
        },
        idempotencyStore: cacheStore,
        singleflightStore: singleflightStore,
        onIdempotencyKeyGenerated: onKeyGenerated,
        onRequestCoalesced: onCoalesced,
      });

      expect(result).toHaveLength(1);
    });
  });

  describe('Memory Management', () => {
    it('should create independent stores for each agent', () => {
      const agent1 = createCacheRequestAgent({
        enableIdempotency: true,
      });

      const agent2 = createCacheRequestAgent({
        enableIdempotency: true,
      });

      expect(agent1).not.toBe(agent2);
    });

    it('should allow shared stores across agents', () => {
      const sharedStore = new MemoryCacheStore();

      const agent1 = createCacheRequestAgent({
        idempotencyStore: sharedStore,
      });

      const agent2 = createCacheRequestAgent({
        idempotencyStore: sharedStore,
      });

      expect(agent1).toBeDefined();
      expect(agent2).toBeDefined();
    });

    it('should allow shared singleflight stores', () => {
      const sharedStore = new MemorySingleflightStore();

      const agent1 = createCacheRequestAgent({
        singleflightStore: sharedStore,
      });

      const agent2 = createCacheRequestAgent({
        singleflightStore: sharedStore,
      });

      expect(agent1).toBeDefined();
      expect(agent2).toBeDefined();
    });
  });
});
