/**
 * Connection pool implementation
 */

import type {
  PooledConnection,
  ConnectionPoolConfig,
  ConnectionPoolStats,
  ConnectionPoolStore,
  ConnectionPoolEventType,
  ConnectionPoolEvent,
  ConnectionPoolEventListener,
  AcquireOptions,
  AcquiredConnection,
} from './types.mjs';
import {
  mergeConfig,
  getHostKey,
  generateConnectionId,
} from './config.mjs';
import { MemoryConnectionStore } from './stores/memory.mjs';

/**
 * Pending request in the queue
 */
interface PendingRequest {
  options: AcquireOptions;
  resolve: (value: AcquiredConnection) => void;
  reject: (error: Error) => void;
  addedAt: number;
  timeoutId?: ReturnType<typeof setTimeout>;
}

/**
 * Connection pool with configurable limits, health tracking, and statistics
 */
export class ConnectionPool {
  private readonly config: Required<ConnectionPoolConfig>;
  private readonly store: ConnectionPoolStore;
  private readonly listeners: Map<ConnectionPoolEventType, Set<ConnectionPoolEventListener>> = new Map();
  private readonly pendingQueue: PendingRequest[] = [];
  private healthCheckInterval?: ReturnType<typeof setInterval>;
  private closed = false;

  // Statistics
  private stats = {
    totalCreated: 0,
    totalClosed: 0,
    totalRequests: 0,
    failedConnections: 0,
    timedOutConnections: 0,
    totalRequestDurationMs: 0,
  };

  constructor(config: ConnectionPoolConfig, store?: ConnectionPoolStore) {
    this.config = mergeConfig(config);
    this.store = store ?? new MemoryConnectionStore();

    if (this.config.enableHealthCheck) {
      this.startHealthCheck();
    }
  }

  /**
   * Get the pool ID
   */
  get id(): string {
    return this.config.id;
  }

  /**
   * Acquire a connection from the pool
   */
  async acquire(options: AcquireOptions): Promise<AcquiredConnection> {
    if (this.closed) {
      throw new Error('Connection pool is closed');
    }

    this.stats.totalRequests++;
    const hostKey = getHostKey(options.host, options.port);

    // Check for abort signal
    if (options.signal?.aborted) {
      throw new Error('Request aborted');
    }

    // Try to find an existing idle connection
    const existingConnection = await this.findIdleConnection(hostKey);
    if (existingConnection) {
      return this.wrapConnection(existingConnection);
    }

    // Check if we can create a new connection
    const totalCount = await this.store.getCount();
    const hostCount = await this.store.getCountByHost(hostKey);

    if (
      totalCount < this.config.maxConnections &&
      hostCount < this.config.maxConnectionsPerHost
    ) {
      const connection = await this.createConnection(options);
      return this.wrapConnection(connection);
    }

    // Pool is at capacity - queue the request if enabled
    if (!this.config.queueRequests) {
      this.emit('pool:full', undefined, options.host);
      throw new Error('Connection pool is full');
    }

    if (this.pendingQueue.length >= this.config.maxQueueSize) {
      this.emit('queue:overflow', undefined, options.host);
      throw new Error('Request queue is full');
    }

    return this.enqueueRequest(options);
  }

  /**
   * Release a connection back to the pool
   */
  async release(connection: PooledConnection): Promise<void> {
    if (this.closed) {
      await this.closeConnection(connection);
      return;
    }

    // Check if connection is too old
    const age = Date.now() - connection.createdAt;
    if (age > this.config.maxConnectionAgeMs) {
      await this.closeConnection(connection);
      return;
    }

    // Check if we have too many idle connections
    const idleCount = await this.getIdleCount();
    if (idleCount >= this.config.maxIdleConnections) {
      await this.closeConnection(connection);
      return;
    }

    // Update connection state
    await this.store.updateConnection(connection.id, {
      state: 'idle',
      lastUsedAt: Date.now(),
    });

    this.emit('connection:released', connection.id, connection.host);

    // Process pending queue
    await this.processPendingQueue();
  }

  /**
   * Mark a connection as failed
   */
  async fail(connection: PooledConnection, error?: Error): Promise<void> {
    this.stats.failedConnections++;

    await this.store.updateConnection(connection.id, {
      health: 'unhealthy',
    });

    this.emit('connection:error', connection.id, connection.host, {
      error: error?.message,
    });

    await this.closeConnection(connection);
  }

  /**
   * Get pool statistics
   */
  async getStats(): Promise<ConnectionPoolStats> {
    const connections = await this.store.getConnections();
    const activeConnections = connections.filter((c) => c.state === 'active').length;
    const idleConnections = connections.filter((c) => c.state === 'idle').length;

    const connectionsByHost: Record<string, number> = {};
    for (const conn of connections) {
      const hostKey = getHostKey(conn.host, conn.port);
      connectionsByHost[hostKey] = (connectionsByHost[hostKey] ?? 0) + 1;
    }

    const totalAge = connections.reduce((sum, c) => sum + (Date.now() - c.createdAt), 0);
    const avgConnectionAgeMs = connections.length > 0 ? totalAge / connections.length : 0;

    const avgRequestDurationMs =
      this.stats.totalRequests > 0
        ? this.stats.totalRequestDurationMs / this.stats.totalRequests
        : 0;

    const hitRatio =
      this.stats.totalRequests > 0
        ? (this.stats.totalRequests - this.stats.totalCreated) / this.stats.totalRequests
        : 0;

    return {
      totalCreated: this.stats.totalCreated,
      totalClosed: this.stats.totalClosed,
      activeConnections,
      idleConnections,
      pendingRequests: this.pendingQueue.length,
      totalRequests: this.stats.totalRequests,
      failedConnections: this.stats.failedConnections,
      timedOutConnections: this.stats.timedOutConnections,
      connectionsByHost,
      avgConnectionAgeMs,
      avgRequestDurationMs,
      hitRatio,
    };
  }

  /**
   * Drain the pool (stop accepting new requests, wait for existing to complete)
   */
  async drain(): Promise<void> {
    // Mark all idle connections as draining
    const connections = await this.store.getConnections();
    for (const conn of connections) {
      if (conn.state === 'idle') {
        await this.store.updateConnection(conn.id, { state: 'draining' });
      }
    }

    // Reject all pending requests
    for (const pending of this.pendingQueue) {
      if (pending.timeoutId) {
        clearTimeout(pending.timeoutId);
      }
      pending.reject(new Error('Pool is draining'));
    }
    this.pendingQueue.length = 0;

    this.emit('pool:drained');
  }

  /**
   * Close the pool and all connections
   */
  async close(): Promise<void> {
    if (this.closed) {
      return;
    }

    this.closed = true;

    // Stop health check
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = undefined;
    }

    // Drain first
    await this.drain();

    // Close all connections
    const connections = await this.store.getConnections();
    for (const conn of connections) {
      await this.closeConnection(conn);
    }

    await this.store.close();
  }

  /**
   * Add an event listener
   */
  on(type: ConnectionPoolEventType, listener: ConnectionPoolEventListener): void {
    let listeners = this.listeners.get(type);
    if (!listeners) {
      listeners = new Set();
      this.listeners.set(type, listeners);
    }
    listeners.add(listener);
  }

  /**
   * Remove an event listener
   */
  off(type: ConnectionPoolEventType, listener: ConnectionPoolEventListener): void {
    const listeners = this.listeners.get(type);
    if (listeners) {
      listeners.delete(listener);
    }
  }

  /**
   * Find an idle connection for the given host
   */
  private async findIdleConnection(hostKey: string): Promise<PooledConnection | null> {
    const connections = await this.store.getConnectionsByHost(hostKey);

    for (const conn of connections) {
      if (conn.state === 'idle' && conn.health !== 'unhealthy') {
        // Mark as active
        await this.store.updateConnection(conn.id, {
          state: 'active',
          lastUsedAt: Date.now(),
          requestCount: conn.requestCount + 1,
        });

        this.emit('connection:acquired', conn.id, conn.host);
        return { ...conn, state: 'active', requestCount: conn.requestCount + 1 };
      }
    }

    return null;
  }

  /**
   * Create a new connection
   */
  private async createConnection(options: AcquireOptions): Promise<PooledConnection> {
    const now = Date.now();
    const connection: PooledConnection = {
      id: generateConnectionId(),
      host: options.host,
      port: options.port,
      protocol: options.protocol,
      state: 'active',
      health: 'healthy',
      createdAt: now,
      lastUsedAt: now,
      requestCount: 1,
      metadata: options.metadata,
    };

    await this.store.addConnection(connection);
    this.stats.totalCreated++;

    this.emit('connection:created', connection.id, connection.host);
    this.emit('connection:acquired', connection.id, connection.host);

    return connection;
  }

  /**
   * Close a connection
   */
  private async closeConnection(connection: PooledConnection): Promise<void> {
    await this.store.updateConnection(connection.id, { state: 'closed' });
    await this.store.removeConnection(connection.id);
    this.stats.totalClosed++;

    this.emit('connection:closed', connection.id, connection.host);
  }

  /**
   * Wrap a connection with release/fail methods
   */
  private wrapConnection(connection: PooledConnection): AcquiredConnection {
    const startTime = Date.now();

    return {
      connection,
      release: async () => {
        this.stats.totalRequestDurationMs += Date.now() - startTime;
        await this.release(connection);
      },
      fail: async (error?: Error) => {
        this.stats.totalRequestDurationMs += Date.now() - startTime;
        await this.fail(connection, error);
      },
    };
  }

  /**
   * Enqueue a request when pool is at capacity
   */
  private enqueueRequest(options: AcquireOptions): Promise<AcquiredConnection> {
    return new Promise((resolve, reject) => {
      const pending: PendingRequest = {
        options,
        resolve,
        reject,
        addedAt: Date.now(),
      };

      // Set up timeout
      const timeoutMs = options.timeoutMs ?? this.config.queueTimeoutMs;
      if (timeoutMs > 0) {
        pending.timeoutId = setTimeout(() => {
          const index = this.pendingQueue.indexOf(pending);
          if (index !== -1) {
            this.pendingQueue.splice(index, 1);
            this.stats.timedOutConnections++;
            this.emit('queue:timeout', undefined, options.host);
            reject(new Error('Connection acquisition timed out'));
          }
        }, timeoutMs);
      }

      // Set up abort signal handling
      if (options.signal) {
        options.signal.addEventListener('abort', () => {
          const index = this.pendingQueue.indexOf(pending);
          if (index !== -1) {
            this.pendingQueue.splice(index, 1);
            if (pending.timeoutId) {
              clearTimeout(pending.timeoutId);
            }
            reject(new Error('Request aborted'));
          }
        });
      }

      // Add to queue (sorted by priority)
      this.insertByPriority(pending);
      this.emit('queue:added', undefined, options.host);
    });
  }

  /**
   * Insert a pending request by priority (higher priority first)
   */
  private insertByPriority(pending: PendingRequest): void {
    const priority = pending.options.priority ?? 0;
    let insertIndex = this.pendingQueue.length;

    for (let i = 0; i < this.pendingQueue.length; i++) {
      const existingPriority = this.pendingQueue[i].options.priority ?? 0;
      if (priority > existingPriority) {
        insertIndex = i;
        break;
      }
    }

    this.pendingQueue.splice(insertIndex, 0, pending);
  }

  /**
   * Process pending queue after a connection is released
   */
  private async processPendingQueue(): Promise<void> {
    if (this.pendingQueue.length === 0) {
      return;
    }

    // Try to satisfy pending requests
    while (this.pendingQueue.length > 0) {
      const pending = this.pendingQueue[0];
      const hostKey = getHostKey(pending.options.host, pending.options.port);

      // Try to find an idle connection
      const connection = await this.findIdleConnection(hostKey);
      if (connection) {
        this.pendingQueue.shift();
        if (pending.timeoutId) {
          clearTimeout(pending.timeoutId);
        }
        pending.resolve(this.wrapConnection(connection));
        continue;
      }

      // Try to create a new connection
      const totalCount = await this.store.getCount();
      const hostCount = await this.store.getCountByHost(hostKey);

      if (
        totalCount < this.config.maxConnections &&
        hostCount < this.config.maxConnectionsPerHost
      ) {
        this.pendingQueue.shift();
        if (pending.timeoutId) {
          clearTimeout(pending.timeoutId);
        }
        try {
          const newConnection = await this.createConnection(pending.options);
          pending.resolve(this.wrapConnection(newConnection));
        } catch (error) {
          pending.reject(error instanceof Error ? error : new Error(String(error)));
        }
        continue;
      }

      // Can't satisfy this request yet
      break;
    }
  }

  /**
   * Start periodic health check
   */
  private startHealthCheck(): void {
    this.healthCheckInterval = setInterval(async () => {
      await this.performHealthCheck();
    }, this.config.healthCheckIntervalMs);
  }

  /**
   * Perform health check on connections
   */
  private async performHealthCheck(): Promise<void> {
    const now = Date.now();

    // Check for timed out idle connections
    if (this.store instanceof MemoryConnectionStore) {
      const timedOut = await this.store.getTimedOutConnections(this.config.idleTimeoutMs);
      for (const conn of timedOut) {
        this.stats.timedOutConnections++;
        this.emit('connection:timeout', conn.id, conn.host);
        await this.closeConnection(conn);
      }

      // Check for expired connections (max age)
      const expired = await this.store.getExpiredConnections(this.config.maxConnectionAgeMs);
      for (const conn of expired) {
        if (conn.state === 'idle') {
          await this.closeConnection(conn);
        }
      }
    }
  }

  /**
   * Get count of idle connections
   */
  private async getIdleCount(): Promise<number> {
    const connections = await this.store.getConnections();
    return connections.filter((c) => c.state === 'idle').length;
  }

  /**
   * Emit an event
   */
  private emit(
    type: ConnectionPoolEventType,
    connectionId?: string,
    host?: string,
    data?: Record<string, unknown>
  ): void {
    const event: ConnectionPoolEvent = {
      type,
      connectionId,
      host,
      data,
      timestamp: Date.now(),
    };

    const listeners = this.listeners.get(type);
    if (listeners) {
      for (const listener of listeners) {
        try {
          listener(event);
        } catch {
          // Ignore listener errors
        }
      }
    }
  }
}
