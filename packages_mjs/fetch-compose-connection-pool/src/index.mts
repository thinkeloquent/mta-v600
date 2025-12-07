/**
 * Connection pool interceptor for undici's compose pattern
 */

// Interceptor
export {
  connectionPoolInterceptor,
  createConnectionPoolInterceptorWithPool,
  type ConnectionPoolInterceptorOptions,
} from './interceptor.mjs';

// Factory functions
export {
  HIGH_CONCURRENCY_PRESET,
  LOW_LATENCY_PRESET,
  MINIMAL_PRESET,
  createFromPreset,
  createApiConnectionPool,
  createSharedConnectionPool,
  composeConnectionPoolInterceptors,
  type ConnectionPoolPreset,
} from './factory.mjs';

// Re-export useful types from connection-pool
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
} from '@internal/connection-pool';

export { ConnectionPool } from '@internal/connection-pool';
