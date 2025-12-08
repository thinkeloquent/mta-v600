/**
 * @internal/cache-response
 *
 * RFC 7234 compliant HTTP response caching with support for:
 * - Cache-Control directive parsing and compliance
 * - ETag and Last-Modified conditional request support
 * - Vary header handling
 * - Stale-while-revalidate pattern
 * - Stale-if-error pattern
 * - Pluggable storage backends (In-Memory LRU, Redis, Filesystem)
 *
 * @example Basic usage
 * ```typescript
 * import { ResponseCache } from '@internal/cache-response';
 *
 * const cache = new ResponseCache({
 *   defaultTtlMs: 300000, // 5 minutes
 *   maxTtlMs: 3600000,    // 1 hour
 * });
 *
 * // Check cache before making request
 * const lookup = await cache.lookup('GET', 'https://api.example.com/users');
 *
 * if (lookup.found && lookup.freshness === 'fresh') {
 *   // Use cached response
 *   return lookup.response;
 * }
 *
 * // Make request with conditional headers
 * const headers: Record<string, string> = {};
 * if (lookup.etag) headers['If-None-Match'] = lookup.etag;
 * if (lookup.lastModified) headers['If-Modified-Since'] = lookup.lastModified;
 *
 * const response = await fetch(url, { headers });
 *
 * // Handle 304 Not Modified
 * if (response.status === 304 && lookup.response) {
 *   await cache.revalidate('GET', url);
 *   return lookup.response;
 * }
 *
 * // Store new response
 * const body = await response.text();
 * await cache.store('GET', url, response.status, Object.fromEntries(response.headers), body);
 * ```
 *
 * @example Stale-while-revalidate
 * ```typescript
 * import { ResponseCache } from '@internal/cache-response';
 *
 * const cache = new ResponseCache({ staleWhileRevalidate: true });
 *
 * // Set background revalidator
 * cache.setBackgroundRevalidator(async (url, headers) => {
 *   const response = await fetch(url, { headers });
 *   const body = await response.text();
 *   await cache.store('GET', url, response.status, Object.fromEntries(response.headers), body);
 * });
 *
 * // When a stale response is found, it's returned immediately
 * // while background revalidation updates the cache
 * const lookup = await cache.lookup('GET', url);
 * if (lookup.found && lookup.freshness === 'stale') {
 *   // Returns stale data immediately, background update in progress
 *   return lookup.response;
 * }
 * ```
 */

// Types
export type {
  CacheControlDirectives,
  CacheEntryMetadata,
  CachedResponse,
  CacheFreshness,
  CacheLookupResult,
  RevalidationResult,
  CacheResponseStore,
  CacheResponseConfig,
  CacheResponseEventType,
  CacheResponseEvent,
  CacheResponseEventListener,
  BackgroundRevalidator,
} from './types.mjs';

// Parser utilities
export {
  parseCacheControl,
  buildCacheControl,
  extractETag,
  extractLastModified,
  parseDateHeader,
  calculateExpiration,
  determineFreshness,
  isCacheableStatus,
  isCacheableMethod,
  shouldCache,
  needsRevalidation,
  parseVary,
  isVaryUncacheable,
  extractVaryHeaders,
  matchVaryHeaders,
  getHeaderValue,
  normalizeHeaders,
} from './parser.mjs';

// Cache manager
export {
  ResponseCache,
  createResponseCache,
  DEFAULT_CACHE_RESPONSE_CONFIG,
  mergeCacheResponseConfig,
} from './cache.mjs';

// Stores
export {
  MemoryCacheStore,
  createMemoryCacheStore,
  type MemoryCacheStoreOptions,
  type MemoryCacheStats,
} from './stores/index.mjs';
