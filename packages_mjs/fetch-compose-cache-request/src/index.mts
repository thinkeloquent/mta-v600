/**
 * @internal/fetch-compose-cache-request
 * Cache request interceptor for undici's compose pattern
 * Pure ESM module
 */

// Re-export types from base package
export type {
  IdempotencyConfig,
  SingleflightConfig,
  RequestFingerprint,
  StoredResponse,
  CacheRequestStore,
  SingleflightStore,
  CacheRequestEventType,
  CacheRequestEvent,
  CacheRequestEventListener,
} from '@internal/cache-request';

// Interceptor exports
export * from './interceptor.mjs';
export { cacheRequestInterceptor as default } from './interceptor.mjs';

// Factory exports
export * from './factory.mjs';
