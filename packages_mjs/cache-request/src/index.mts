/**
 * @internal/cache-request
 *
 * Request deduplication with Idempotency Keys and Request Coalescing (Singleflight) support.
 *
 * @example Idempotency Keys
 * ```typescript
 * import { IdempotencyManager } from '@internal/cache-request';
 *
 * const manager = new IdempotencyManager({ ttlMs: 3600000 });
 *
 * // Generate a key for a POST request
 * const key = manager.generateKey();
 *
 * // Check for cached response before making request
 * const check = await manager.check(key);
 * if (check.cached) {
 *   return check.response.value;
 * }
 *
 * // Make request and store response
 * const response = await fetch(url, { method: 'POST', body });
 * await manager.store(key, await response.json());
 * ```
 *
 * @example Request Coalescing (Singleflight)
 * ```typescript
 * import { Singleflight } from '@internal/cache-request';
 *
 * const sf = new Singleflight();
 *
 * // Multiple concurrent calls to the same endpoint are coalesced
 * const results = await Promise.all([
 *   sf.do({ method: 'GET', url: '/api/data' }, () => fetch('/api/data')),
 *   sf.do({ method: 'GET', url: '/api/data' }, () => fetch('/api/data')),
 *   sf.do({ method: 'GET', url: '/api/data' }, () => fetch('/api/data')),
 * ]);
 *
 * // Only one fetch was made, all received the same result
 * console.log(results[0].shared); // false (the leader)
 * console.log(results[1].shared); // true (joined existing)
 * console.log(results[2].shared); // true (joined existing)
 * ```
 */

// Types
export type {
  IdempotencyConfig,
  SingleflightConfig,
  RequestFingerprint,
  StoredResponse,
  InFlightRequest,
  CacheRequestStore,
  SingleflightStore,
  CacheRequestConfig,
  IdempotencyCheckResult,
  SingleflightResult,
  CacheRequestEventType,
  CacheRequestEvent,
  CacheRequestEventListener,
} from './types.mjs';

// Idempotency
export {
  IdempotencyManager,
  IdempotencyConflictError,
  createIdempotencyManager,
  DEFAULT_IDEMPOTENCY_CONFIG,
  mergeIdempotencyConfig,
  generateFingerprint,
} from './idempotency.mjs';

// Singleflight
export {
  Singleflight,
  createSingleflight,
  DEFAULT_SINGLEFLIGHT_CONFIG,
  mergeSingleflightConfig,
} from './singleflight.mjs';

// Stores
export {
  MemoryCacheStore,
  MemorySingleflightStore,
  createMemoryCacheStore,
  createMemorySingleflightStore,
} from './stores/index.mjs';
