/**
 * @internal/fetch-compose-cache-response
 * Cache response interceptor for undici's compose pattern
 *
 * RFC 7234 compliant HTTP response caching with:
 * - Cache-Control directive parsing and compliance
 * - ETag and Last-Modified conditional request support
 * - Vary header handling
 * - Stale-while-revalidate pattern
 * - Stale-if-error pattern
 *
 * Pure ESM module
 */

// Re-export types from base package
export type {
  CacheControlDirectives,
  CacheEntryMetadata,
  CachedResponse,
  CacheFreshness,
  CacheLookupResult,
  CacheResponseStore,
  CacheResponseConfig,
  CacheResponseEventType,
  CacheResponseEvent,
  CacheResponseEventListener,
  BackgroundRevalidator,
} from '@internal/cache-response';

// Re-export cache utilities from base package
export {
  ResponseCache,
  createResponseCache,
  parseCacheControl,
  buildCacheControl,
  MemoryCacheStore,
  createMemoryCacheStore,
} from '@internal/cache-response';

// Interceptor exports
export * from './interceptor.mjs';
export { cacheResponseInterceptor as default } from './interceptor.mjs';

// Factory exports
export * from './factory.mjs';
