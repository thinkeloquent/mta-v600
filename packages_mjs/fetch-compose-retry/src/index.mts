/**
 * @internal/fetch-compose-retry
 * Retry interceptor for undici's compose pattern
 * Pure ESM module
 */

// Re-export types from base package
export type {
  RetryConfig,
  RetryOptions,
  RetryResult,
  RetryEvent,
  RetryEventListener,
} from '@internal/fetch-retry';

// Interceptor exports
export * from './interceptor.mjs';
export { retryInterceptor as default } from './interceptor.mjs';

// Factory exports
export * from './factory.mjs';
