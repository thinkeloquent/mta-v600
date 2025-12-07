/**
 * @internal/fetch-compose-rate-limiter
 * Rate limiter interceptor for undici's compose pattern
 * Pure ESM module
 */

// Re-export types from base package
export type {
  RateLimiterConfig,
  RateLimitStore,
  RateLimiterStats,
  RateLimiterEvent,
  StaticRateLimitConfig,
  DynamicRateLimitConfig,
  RetryConfig,
} from '@internal/fetch-rate-limiter';

// Interceptor exports
export * from './interceptor.mjs';
export { rateLimitInterceptor as default } from './interceptor.mjs';

// Factory exports
export * from './factory.mjs';
