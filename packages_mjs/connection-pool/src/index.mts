/**
 * Connection pool package exports
 */

// Types
export type {
  ConnectionState,
  HealthStatus,
  PooledConnection,
  ConnectionPoolConfig,
  ConnectionPoolStats,
  ConnectionPoolEventType,
  ConnectionPoolEvent,
  ConnectionPoolEventListener,
  AcquireOptions,
  ConnectionPoolStore,
  AcquiredConnection,
} from './types.mjs';

// Config utilities
export {
  DEFAULT_CONNECTION_POOL_CONFIG,
  mergeConfig,
  validateConfig,
  getHostKey,
  parseHostKey,
  generateConnectionId,
} from './config.mjs';

// Stores
export { MemoryConnectionStore } from './stores/memory.mjs';

// Main pool
export { ConnectionPool } from './pool.mjs';
