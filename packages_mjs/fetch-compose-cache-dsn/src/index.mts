/**
 * @internal/fetch-compose-cache-dsn
 * DNS cache interceptor for undici's compose pattern
 * Pure ESM module
 */

// Re-export types from base package
export type {
  DnsCacheConfig,
  DnsCacheStore,
  DnsCacheStats,
  DnsCacheEvent,
  LoadBalanceStrategy,
  ResolvedEndpoint,
  CachedEntry,
  ResolutionResult,
  HealthCheckConfig,
} from '@internal/cache-dsn';

// Interceptor exports
export * from './interceptor.mjs';
export { dnsCacheInterceptor as default } from './interceptor.mjs';

// Factory exports
export * from './factory.mjs';
