/**
 * Factory functions for creating cache response interceptors
 */

import { Agent, type Dispatcher } from 'undici';
import {
  cacheResponseInterceptor,
  type CacheResponseInterceptorOptions,
} from './interceptor.mjs';

/**
 * Create a dispatcher with cache response capabilities
 *
 * @param baseDispatcher - Base dispatcher to compose with
 * @param options - Cache response interceptor options
 * @returns Composed dispatcher with cache response capabilities
 *
 * @example
 * const dispatcher = createCacheResponseDispatcher(new Agent(), {
 *   config: { defaultTtlMs: 300000 }
 * });
 */
export function createCacheResponseDispatcher(
  baseDispatcher: Dispatcher.ComposedDispatcher | Agent,
  options?: CacheResponseInterceptorOptions
): Dispatcher.ComposedDispatcher {
  return baseDispatcher.compose(cacheResponseInterceptor(options));
}

/**
 * Create an agent with cache response capabilities
 *
 * @param options - Cache response interceptor options
 * @param agentOptions - Agent constructor options
 * @returns Agent with cache response capabilities
 *
 * @example
 * const agent = createCacheResponseAgent({
 *   config: {
 *     staleWhileRevalidate: true,
 *     defaultTtlMs: 60000
 *   }
 * });
 */
export function createCacheResponseAgent(
  options?: CacheResponseInterceptorOptions,
  agentOptions?: Agent.Options
): Dispatcher.ComposedDispatcher {
  const agent = new Agent(agentOptions);
  return agent.compose(cacheResponseInterceptor(options));
}

/**
 * Compose cache response interceptor with other interceptors
 *
 * @param interceptors - Array of interceptors to compose
 * @param cacheResponseOptions - Cache response interceptor options
 * @returns Array of interceptors with cache response included
 *
 * @example
 * const interceptorChain = composeCacheResponse(
 *   [
 *     interceptors.retry({ maxRetries: 3 }),
 *     interceptors.dns({ affinity: 4 })
 *   ],
 *   { config: { staleWhileRevalidate: true } }
 * );
 *
 * const client = new Agent().compose(...interceptorChain);
 */
export function composeCacheResponse(
  interceptors: Dispatcher.DispatcherComposeInterceptor[],
  cacheResponseOptions?: CacheResponseInterceptorOptions
): Dispatcher.DispatcherComposeInterceptor[] {
  // Cache should typically be first in the chain to check cache before other interceptors
  return [cacheResponseInterceptor(cacheResponseOptions), ...interceptors];
}
