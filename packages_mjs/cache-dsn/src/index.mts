/**
 * @internal/cache-dsn
 * Standalone DNS/service discovery cache with TTL, health-aware invalidation, and pluggable backends
 * Pure ESM module
 */

// Type exports
export * from './types.mjs';

// Config exports
export * from './config.mjs';
export { default as config } from './config.mjs';

// Store exports
export * from './stores/index.mjs';

// Main resolver exports
export * from './resolver.mjs';
export { DnsCacheResolver as default } from './resolver.mjs';
