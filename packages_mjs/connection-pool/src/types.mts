/**
 * Type definitions for connection-pool
 */

/**
 * Connection state
 */
export type ConnectionState = 'idle' | 'active' | 'draining' | 'closed';

/**
 * Connection health status
 */
export type HealthStatus = 'healthy' | 'unhealthy' | 'unknown';

/**
 * A pooled connection
 */
export interface PooledConnection {
  /** Unique connection ID */
  id: string;
  /** Connection host */
  host: string;
  /** Connection port */
  port: number;
  /** Current state */
  state: ConnectionState;
  /** Health status */
  health: HealthStatus;
  /** When the connection was created (Unix timestamp) */
  createdAt: number;
  /** Last time the connection was used (Unix timestamp) */
  lastUsedAt: number;
  /** Number of requests made on this connection */
  requestCount: number;
  /** Protocol (http or https) */
  protocol: 'http' | 'https';
  /** Custom metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Connection pool configuration
 */
export interface ConnectionPoolConfig {
  /** Unique identifier for this pool */
  id: string;
  /** Maximum total connections across all hosts. Default: 100 */
  maxConnections?: number;
  /** Maximum connections per host. Default: 10 */
  maxConnectionsPerHost?: number;
  /** Maximum idle connections to keep. Default: 20 */
  maxIdleConnections?: number;
  /** Idle connection timeout in ms. Default: 60000 (1 minute) */
  idleTimeoutMs?: number;
  /** Keep-alive timeout in ms. Default: 30000 (30 seconds) */
  keepAliveTimeoutMs?: number;
  /** Connection timeout in ms (for new connections). Default: 10000 (10 seconds) */
  connectTimeoutMs?: number;
  /** Whether to enable connection health checks. Default: true */
  enableHealthCheck?: boolean;
  /** Health check interval in ms. Default: 30000 (30 seconds) */
  healthCheckIntervalMs?: number;
  /** Max connection age in ms before forcing close. Default: 300000 (5 minutes) */
  maxConnectionAgeMs?: number;
  /** Enable keep-alive. Default: true */
  keepAlive?: boolean;
  /** Queue pending requests when at capacity. Default: true */
  queueRequests?: boolean;
  /** Max pending requests in queue. Default: 1000 */
  maxQueueSize?: number;
  /** Request timeout while waiting in queue in ms. Default: 30000 */
  queueTimeoutMs?: number;
}

/**
 * Connection pool statistics
 */
export interface ConnectionPoolStats {
  /** Total connections created */
  totalCreated: number;
  /** Total connections closed */
  totalClosed: number;
  /** Currently active connections */
  activeConnections: number;
  /** Currently idle connections */
  idleConnections: number;
  /** Pending requests in queue */
  pendingRequests: number;
  /** Total requests processed */
  totalRequests: number;
  /** Failed connection attempts */
  failedConnections: number;
  /** Connections closed due to timeout */
  timedOutConnections: number;
  /** Connections per host */
  connectionsByHost: Record<string, number>;
  /** Average connection age in ms */
  avgConnectionAgeMs: number;
  /** Average request duration in ms */
  avgRequestDurationMs: number;
  /** Pool hit ratio (reused connections / total requests) */
  hitRatio: number;
}

/**
 * Pool event types
 */
export type ConnectionPoolEventType =
  | 'connection:created'
  | 'connection:acquired'
  | 'connection:released'
  | 'connection:closed'
  | 'connection:timeout'
  | 'connection:error'
  | 'connection:health:changed'
  | 'pool:drained'
  | 'pool:full'
  | 'queue:added'
  | 'queue:timeout'
  | 'queue:overflow';

/**
 * Pool event
 */
export interface ConnectionPoolEvent {
  type: ConnectionPoolEventType;
  connectionId?: string;
  host?: string;
  data?: Record<string, unknown>;
  timestamp: number;
}

/**
 * Event listener type
 */
export type ConnectionPoolEventListener = (event: ConnectionPoolEvent) => void;

/**
 * Connection acquisition options
 */
export interface AcquireOptions {
  /** Host to acquire connection for */
  host: string;
  /** Port number */
  port: number;
  /** Protocol */
  protocol: 'http' | 'https';
  /** Priority (higher = more urgent). Default: 0 */
  priority?: number;
  /** Timeout for acquisition in ms */
  timeoutMs?: number;
  /** Abort signal */
  signal?: AbortSignal;
  /** Custom metadata to attach to connection */
  metadata?: Record<string, unknown>;
}

/**
 * Store interface for connection pool state (for distributed pools)
 */
export interface ConnectionPoolStore {
  /** Get all connections */
  getConnections(): Promise<PooledConnection[]>;
  /** Get connections for a specific host */
  getConnectionsByHost(hostKey: string): Promise<PooledConnection[]>;
  /** Add a connection to the store */
  addConnection(connection: PooledConnection): Promise<void>;
  /** Update a connection */
  updateConnection(connectionId: string, updates: Partial<PooledConnection>): Promise<void>;
  /** Remove a connection */
  removeConnection(connectionId: string): Promise<boolean>;
  /** Get connection count */
  getCount(): Promise<number>;
  /** Get connection count by host */
  getCountByHost(hostKey: string): Promise<number>;
  /** Clear all connections */
  clear(): Promise<void>;
  /** Close the store */
  close(): Promise<void>;
}

/**
 * Acquired connection handle
 */
export interface AcquiredConnection {
  /** The connection */
  connection: PooledConnection;
  /** Release the connection back to the pool */
  release: () => Promise<void>;
  /** Mark the connection as failed and remove from pool */
  fail: (error?: Error) => Promise<void>;
}
