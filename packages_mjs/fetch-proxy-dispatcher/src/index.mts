/**
 * @internal/fetch-proxy-dispatcher
 * Environment-aware proxy dispatcher for fetch/undici
 * Pure ESM module
 */

// Config exports
export * from './config.mjs';
export { default as config } from './config.mjs';

// Agent exports
export * from './agents.mjs';
export { default as agents } from './agents.mjs';

// Simple dispatcher API
export * from './dispatcher.mjs';
export { default as dispatcher } from './dispatcher.mjs';

// Factory API
export * from './factory.mjs';
export { ProxyDispatcherFactory as default } from './factory.mjs';
