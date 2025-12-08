/**
 * Factory functions for creating cache request interceptors
 */

import { Agent, type Dispatcher } from 'undici';
import { cacheRequestInterceptor, type CacheRequestInterceptorOptions } from './interceptor.mjs';

/**
 * Create a dispatcher with cache request capabilities
 *
 * @param baseDispatcher - Base dispatcher to compose with
 * @param options - Cache request interceptor options
 * @returns Composed dispatcher with cache request capabilities
 *
 * @example
 * const dispatcher = createCacheRequestDispatcher(new Agent(), {
 *   idempotency: { ttlMs: 3600000 }
 * });
 */
export function createCacheRequestDispatcher(
  baseDispatcher: Dispatcher.ComposedDispatcher | Agent,
  options?: CacheRequestInterceptorOptions
): Dispatcher.ComposedDispatcher {
  return baseDispatcher.compose(cacheRequestInterceptor(options));
}

/**
 * Create an agent with cache request capabilities
 *
 * @param options - Cache request interceptor options
 * @param agentOptions - Agent constructor options
 * @returns Agent with cache request capabilities
 *
 * @example
 * const agent = createCacheRequestAgent({
 *   enableIdempotency: true,
 *   enableSingleflight: true
 * });
 */
export function createCacheRequestAgent(
  options?: CacheRequestInterceptorOptions,
  agentOptions?: Agent.Options
): Dispatcher.ComposedDispatcher {
  const agent = new Agent(agentOptions);
  return agent.compose(cacheRequestInterceptor(options));
}

/**
 * Compose cache request interceptor with other interceptors
 *
 * @param interceptors - Array of interceptors to compose
 * @param cacheRequestOptions - Cache request interceptor options
 * @returns Array of interceptors with cache request included
 *
 * @example
 * const interceptorChain = composeCacheRequest(
 *   [
 *     interceptors.retry({ maxRetries: 3 }),
 *     interceptors.dns({ affinity: 4 })
 *   ],
 *   { enableSingleflight: true }
 * );
 *
 * const client = new Agent().compose(...interceptorChain);
 */
export function composeCacheRequest(
  interceptors: Dispatcher.DispatcherComposeInterceptor[],
  cacheRequestOptions?: CacheRequestInterceptorOptions
): Dispatcher.DispatcherComposeInterceptor[] {
  return [cacheRequestInterceptor(cacheRequestOptions), ...interceptors];
}
