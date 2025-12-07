/**
 * Tests for ConnectionPool main class
 *
 * Coverage includes:
 * - Decision/Branch Coverage: acquire/release/fail paths
 * - State Transition Testing: Pool and connection states
 * - Queue logic testing
 * - Event emission testing
 * - Health check logic
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ConnectionPool } from '../src/pool.mjs';
import { MemoryConnectionStore } from '../src/stores/memory.mjs';
import type {
  ConnectionPoolConfig,
  ConnectionPoolEvent,
  AcquireOptions,
} from '../src/types.mjs';

function createConfig(overrides: Partial<ConnectionPoolConfig> = {}): ConnectionPoolConfig {
  return {
    id: 'test-pool',
    maxConnections: 10,
    maxConnectionsPerHost: 5,
    maxIdleConnections: 5,
    idleTimeoutMs: 60000,
    keepAliveTimeoutMs: 30000,
    connectTimeoutMs: 10000,
    enableHealthCheck: false, // Disable by default for tests
    healthCheckIntervalMs: 30000,
    maxConnectionAgeMs: 300000,
    keepAlive: true,
    queueRequests: true,
    maxQueueSize: 100,
    queueTimeoutMs: 5000,
    ...overrides,
  };
}

function createAcquireOptions(overrides: Partial<AcquireOptions> = {}): AcquireOptions {
  return {
    host: 'api.example.com',
    port: 443,
    protocol: 'https',
    ...overrides,
  };
}

describe('ConnectionPool', () => {
  let pool: ConnectionPool;

  afterEach(async () => {
    if (pool) {
      await pool.close();
    }
  });

  describe('Construction', () => {
    it('should create pool with config', () => {
      pool = new ConnectionPool(createConfig());
      expect(pool.id).toBe('test-pool');
    });

    it('should use custom store', () => {
      const store = new MemoryConnectionStore();
      pool = new ConnectionPool(createConfig(), store);
      expect(pool.id).toBe('test-pool');
    });

    it('should start health check when enabled', async () => {
      pool = new ConnectionPool(
        createConfig({
          enableHealthCheck: true,
          healthCheckIntervalMs: 100,
        })
      );

      // Wait for health check to run once
      await new Promise((resolve) => setTimeout(resolve, 150));

      // Pool should still be operational
      const acquired = await pool.acquire(createAcquireOptions());
      expect(acquired.connection).toBeDefined();
      await acquired.release();
    });
  });

  describe('acquire', () => {
    beforeEach(() => {
      pool = new ConnectionPool(createConfig());
    });

    it('should create new connection when pool is empty', async () => {
      const acquired = await pool.acquire(createAcquireOptions());

      expect(acquired.connection).toBeDefined();
      expect(acquired.connection.state).toBe('active');
      expect(acquired.connection.host).toBe('api.example.com');
      expect(acquired.connection.port).toBe(443);
      expect(acquired.connection.protocol).toBe('https');

      await acquired.release();
    });

    it('should reuse idle connection', async () => {
      const acquired1 = await pool.acquire(createAcquireOptions());
      const connectionId = acquired1.connection.id;
      await acquired1.release();

      const acquired2 = await pool.acquire(createAcquireOptions());

      // Should reuse the same connection
      expect(acquired2.connection.id).toBe(connectionId);
      // Request count should be greater than 1 (incremented on reuse)
      expect(acquired2.connection.requestCount).toBeGreaterThan(1);

      await acquired2.release();
    });

    it('should create connection for different host', async () => {
      const acquired1 = await pool.acquire(createAcquireOptions({ host: 'api1.example.com' }));
      const acquired2 = await pool.acquire(createAcquireOptions({ host: 'api2.example.com' }));

      expect(acquired1.connection.id).not.toBe(acquired2.connection.id);
      expect(acquired1.connection.host).toBe('api1.example.com');
      expect(acquired2.connection.host).toBe('api2.example.com');

      await acquired1.release();
      await acquired2.release();
    });

    it('should throw when pool is closed', async () => {
      await pool.close();

      await expect(pool.acquire(createAcquireOptions())).rejects.toThrow(
        'Connection pool is closed'
      );
    });

    it('should respect maxConnections limit', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 2,
          maxConnectionsPerHost: 2,
          queueRequests: false,
        })
      );

      const acquired1 = await pool.acquire(createAcquireOptions({ host: 'a.com' }));
      const acquired2 = await pool.acquire(createAcquireOptions({ host: 'b.com' }));

      await expect(
        pool.acquire(createAcquireOptions({ host: 'c.com' }))
      ).rejects.toThrow('Connection pool is full');

      await acquired1.release();
      await acquired2.release();
    });

    it('should respect maxConnectionsPerHost limit', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 10,
          maxConnectionsPerHost: 2,
          queueRequests: false,
        })
      );

      const acquired1 = await pool.acquire(createAcquireOptions());
      const acquired2 = await pool.acquire(createAcquireOptions());

      await expect(pool.acquire(createAcquireOptions())).rejects.toThrow(
        'Connection pool is full'
      );

      await acquired1.release();
      await acquired2.release();
    });

    it('should include metadata in connection', async () => {
      const acquired = await pool.acquire(
        createAcquireOptions({
          metadata: { requestId: '123', userId: 'user-1' },
        })
      );

      expect(acquired.connection.metadata).toEqual({
        requestId: '123',
        userId: 'user-1',
      });

      await acquired.release();
    });
  });

  describe('Queue Logic', () => {
    beforeEach(() => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 2,
          maxConnectionsPerHost: 2,
          queueRequests: true,
          maxQueueSize: 10,
          queueTimeoutMs: 1000,
        })
      );
    });

    it('should queue request when at capacity', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 2,
          maxConnectionsPerHost: 2,
          queueRequests: true,
          maxQueueSize: 10,
          queueTimeoutMs: 5000,
        })
      );

      const acquired1 = await pool.acquire(createAcquireOptions());
      const acquired2 = await pool.acquire(createAcquireOptions());

      // This should be queued
      const acquirePromise = pool.acquire(createAcquireOptions());

      // Wait a tick for the queue to be populated
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Release one to allow queued request to proceed
      await acquired1.release();

      const acquired3 = await acquirePromise;
      expect(acquired3.connection).toBeDefined();

      await acquired2.release();
      await acquired3.release();
    });

    it('should timeout queued requests', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          maxConnectionsPerHost: 1,
          queueRequests: true,
          queueTimeoutMs: 100,
        })
      );

      const acquired = await pool.acquire(createAcquireOptions());

      // This should be queued and timeout
      await expect(pool.acquire(createAcquireOptions())).rejects.toThrow(
        'Connection acquisition timed out'
      );

      await acquired.release();
    });

    it('should respect custom timeout in options', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          maxConnectionsPerHost: 1,
          queueRequests: true,
          queueTimeoutMs: 10000, // long default
        })
      );

      const acquired = await pool.acquire(createAcquireOptions());

      // Use short timeout in options
      await expect(
        pool.acquire(createAcquireOptions({ timeoutMs: 50 }))
      ).rejects.toThrow('Connection acquisition timed out');

      await acquired.release();
    });

    it('should throw when queue is full', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          maxConnectionsPerHost: 1,
          queueRequests: true,
          maxQueueSize: 1,
          queueTimeoutMs: 10000,
        })
      );

      const acquired = await pool.acquire(createAcquireOptions());

      // Fill the queue
      const queued = pool.acquire(createAcquireOptions());

      // This should fail
      await expect(pool.acquire(createAcquireOptions())).rejects.toThrow(
        'Request queue is full'
      );

      await acquired.release();
      await queued;
    });

    it('should process queue in priority order', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          maxConnectionsPerHost: 1,
          queueRequests: true,
          queueTimeoutMs: 5000,
        })
      );

      const acquired = await pool.acquire(createAcquireOptions());

      const order: number[] = [];

      // Queue low priority first
      const lowPriority = pool.acquire(createAcquireOptions({ priority: 0 })).then((acq) => {
        order.push(0);
        return acq;
      });

      // Wait for queue to be populated
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Queue high priority second
      const highPriority = pool.acquire(createAcquireOptions({ priority: 10 })).then((acq) => {
        order.push(10);
        return acq;
      });

      // Wait for queue to be populated
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Release to process queue
      await acquired.release();

      // Wait for high priority to complete first
      const high = await highPriority;
      await high.release();

      const low = await lowPriority;
      await low.release();

      // High priority should be processed first
      expect(order[0]).toBe(10);
      expect(order[1]).toBe(0);
    });

    it('should skip unhealthy connections when reusing', async () => {
      const acquired1 = await pool.acquire(createAcquireOptions());
      await acquired1.fail(new Error('Connection failed'));

      // Should create new connection, not reuse unhealthy one
      const acquired2 = await pool.acquire(createAcquireOptions());
      expect(acquired2.connection.health).toBe('healthy');

      await acquired2.release();
    });
  });

  describe('release', () => {
    beforeEach(() => {
      pool = new ConnectionPool(createConfig());
    });

    it('should mark connection as idle', async () => {
      const acquired = await pool.acquire(createAcquireOptions());
      expect(acquired.connection.state).toBe('active');

      await acquired.release();

      const stats = await pool.getStats();
      expect(stats.idleConnections).toBe(1);
      expect(stats.activeConnections).toBe(0);
    });

    it('should close connection if pool is closed', async () => {
      const acquired = await pool.acquire(createAcquireOptions());

      await pool.close();

      // Release after close should not error
      await acquired.release();

      const stats = await pool.getStats();
      expect(stats.idleConnections).toBe(0);
    });

    it('should close connection if too old', async () => {
      pool = new ConnectionPool(createConfig({ maxConnectionAgeMs: 0 }));

      const acquired = await pool.acquire(createAcquireOptions());

      // Wait a bit for connection to age
      await new Promise((resolve) => setTimeout(resolve, 10));

      await acquired.release();

      const stats = await pool.getStats();
      expect(stats.totalClosed).toBe(1);
    });

    it('should close connection if too many idle', async () => {
      pool = new ConnectionPool(createConfig({ maxIdleConnections: 1 }));

      const acquired1 = await pool.acquire(createAcquireOptions({ host: 'a.com' }));
      const acquired2 = await pool.acquire(createAcquireOptions({ host: 'b.com' }));

      await acquired1.release();
      await acquired2.release();

      const stats = await pool.getStats();
      expect(stats.idleConnections).toBe(1);
      expect(stats.totalClosed).toBe(1);
    });
  });

  describe('fail', () => {
    beforeEach(() => {
      pool = new ConnectionPool(createConfig());
    });

    it('should mark connection as unhealthy and close it', async () => {
      const acquired = await pool.acquire(createAcquireOptions());

      await acquired.fail(new Error('Test error'));

      const stats = await pool.getStats();
      expect(stats.failedConnections).toBe(1);
      expect(stats.totalClosed).toBe(1);
    });

    it('should work without error argument', async () => {
      const acquired = await pool.acquire(createAcquireOptions());

      await acquired.fail();

      const stats = await pool.getStats();
      expect(stats.failedConnections).toBe(1);
    });
  });

  describe('getStats', () => {
    beforeEach(() => {
      pool = new ConnectionPool(createConfig());
    });

    it('should return correct stats for empty pool', async () => {
      const stats = await pool.getStats();

      expect(stats.totalCreated).toBe(0);
      expect(stats.totalClosed).toBe(0);
      expect(stats.activeConnections).toBe(0);
      expect(stats.idleConnections).toBe(0);
      expect(stats.pendingRequests).toBe(0);
      expect(stats.totalRequests).toBe(0);
      expect(stats.failedConnections).toBe(0);
      expect(stats.timedOutConnections).toBe(0);
      expect(stats.avgConnectionAgeMs).toBe(0);
      expect(stats.avgRequestDurationMs).toBe(0);
      expect(stats.hitRatio).toBe(0);
    });

    it('should track active and idle connections', async () => {
      const acquired1 = await pool.acquire(createAcquireOptions({ host: 'a.com' }));
      const acquired2 = await pool.acquire(createAcquireOptions({ host: 'b.com' }));
      await acquired1.release();

      const stats = await pool.getStats();

      expect(stats.activeConnections).toBe(1);
      expect(stats.idleConnections).toBe(1);
      expect(stats.totalCreated).toBe(2);

      await acquired2.release();
    });

    it('should track connections by host', async () => {
      const acquired1 = await pool.acquire(createAcquireOptions({ host: 'a.com' }));
      const acquired2 = await pool.acquire(createAcquireOptions({ host: 'a.com' }));
      const acquired3 = await pool.acquire(createAcquireOptions({ host: 'b.com' }));

      const stats = await pool.getStats();

      expect(stats.connectionsByHost['a.com:443']).toBe(2);
      expect(stats.connectionsByHost['b.com:443']).toBe(1);

      await acquired1.release();
      await acquired2.release();
      await acquired3.release();
    });

    it('should calculate hit ratio', async () => {
      // First request creates connection
      const acquired1 = await pool.acquire(createAcquireOptions());
      await acquired1.release();

      // Second request reuses connection
      const acquired2 = await pool.acquire(createAcquireOptions());
      await acquired2.release();

      // Third request reuses connection
      const acquired3 = await pool.acquire(createAcquireOptions());
      await acquired3.release();

      const stats = await pool.getStats();

      // 1 created, 3 total requests = 2/3 hit ratio
      expect(stats.hitRatio).toBeCloseTo(0.667, 2);
    });

    it('should track average connection age', async () => {
      const acquired = await pool.acquire(createAcquireOptions());

      // Wait a bit
      await new Promise((resolve) => setTimeout(resolve, 50));

      const stats = await pool.getStats();
      expect(stats.avgConnectionAgeMs).toBeGreaterThanOrEqual(50);

      await acquired.release();
    });
  });

  describe('drain', () => {
    it('should mark idle connections as draining', async () => {
      pool = new ConnectionPool(createConfig());

      const acquired = await pool.acquire(createAcquireOptions());
      await acquired.release();

      await pool.drain();

      // Pool should still have connection in draining state
      const stats = await pool.getStats();
      expect(stats.idleConnections).toBe(0);
    });

    it('should reject pending requests', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          maxConnectionsPerHost: 1,
          queueRequests: true,
          queueTimeoutMs: 10000,
        })
      );

      const acquired = await pool.acquire(createAcquireOptions());

      // Start the pending acquire
      const pending = pool.acquire(createAcquireOptions());

      // Wait for the request to be queued
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Drain the pool - this should reject the pending request
      await pool.drain();

      await expect(pending).rejects.toThrow('Pool is draining');

      // Release after drain
      await acquired.release();
    });
  });

  describe('close', () => {
    it('should close all connections', async () => {
      pool = new ConnectionPool(createConfig());

      const acquired1 = await pool.acquire(createAcquireOptions({ host: 'a.com' }));
      const acquired2 = await pool.acquire(createAcquireOptions({ host: 'b.com' }));
      await acquired1.release();

      await pool.close();

      const stats = await pool.getStats();
      expect(stats.activeConnections).toBe(0);
      expect(stats.idleConnections).toBe(0);
    });

    it('should be idempotent', async () => {
      pool = new ConnectionPool(createConfig());

      await pool.close();
      await pool.close(); // Should not throw
    });

    it('should stop health check', async () => {
      pool = new ConnectionPool(
        createConfig({
          enableHealthCheck: true,
          healthCheckIntervalMs: 50,
        })
      );

      await pool.close();

      // Wait to ensure no health check runs
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Should be closed without errors
    });
  });

  describe('Event Listeners', () => {
    beforeEach(() => {
      pool = new ConnectionPool(createConfig());
    });

    it('should emit connection:created event', async () => {
      const events: ConnectionPoolEvent[] = [];
      pool.on('connection:created', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('connection:created');
      expect(events[0].connectionId).toBe(acquired.connection.id);
      expect(events[0].host).toBe('api.example.com');

      await acquired.release();
    });

    it('should emit connection:acquired event', async () => {
      const events: ConnectionPoolEvent[] = [];
      pool.on('connection:acquired', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('connection:acquired');

      await acquired.release();
    });

    it('should emit connection:released event', async () => {
      const events: ConnectionPoolEvent[] = [];
      pool.on('connection:released', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());
      await acquired.release();

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('connection:released');
    });

    it('should emit connection:closed event', async () => {
      pool = new ConnectionPool(createConfig({ maxIdleConnections: 0 }));

      const events: ConnectionPoolEvent[] = [];
      pool.on('connection:closed', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());
      await acquired.release();

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('connection:closed');
    });

    it('should emit connection:error event', async () => {
      const events: ConnectionPoolEvent[] = [];
      pool.on('connection:error', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());
      await acquired.fail(new Error('Test error'));

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('connection:error');
      expect(events[0].data?.error).toBe('Test error');
    });

    it('should emit pool:full event', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          queueRequests: false,
        })
      );

      const events: ConnectionPoolEvent[] = [];
      pool.on('pool:full', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());

      try {
        await pool.acquire(createAcquireOptions());
      } catch {
        // Expected
      }

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('pool:full');

      await acquired.release();
    });

    it('should emit queue:added event', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          maxConnectionsPerHost: 1,
          queueRequests: true,
          queueTimeoutMs: 5000,
        })
      );

      const events: ConnectionPoolEvent[] = [];
      pool.on('queue:added', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());

      // Start the pending acquire but don't await yet
      const pending = pool.acquire(createAcquireOptions());

      // Wait a tick for the async enqueue to happen
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('queue:added');

      await acquired.release();
      const pendingResult = await pending;
      await pendingResult.release();
    });

    it('should emit queue:timeout event', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          maxConnectionsPerHost: 1,
          queueRequests: true,
          queueTimeoutMs: 50,
        })
      );

      const events: ConnectionPoolEvent[] = [];
      pool.on('queue:timeout', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());

      try {
        await pool.acquire(createAcquireOptions());
      } catch {
        // Expected timeout
      }

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('queue:timeout');

      await acquired.release();
    });

    it('should emit queue:overflow event', async () => {
      pool = new ConnectionPool(
        createConfig({
          maxConnections: 1,
          maxConnectionsPerHost: 1,
          queueRequests: true,
          maxQueueSize: 0,
        })
      );

      const events: ConnectionPoolEvent[] = [];
      pool.on('queue:overflow', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());

      try {
        await pool.acquire(createAcquireOptions());
      } catch {
        // Expected overflow
      }

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('queue:overflow');

      await acquired.release();
    });

    it('should emit pool:drained event', async () => {
      const events: ConnectionPoolEvent[] = [];
      pool.on('pool:drained', (e) => events.push(e));

      await pool.drain();

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('pool:drained');
    });

    it('should allow removing listeners', async () => {
      const events: ConnectionPoolEvent[] = [];
      const listener = (e: ConnectionPoolEvent) => events.push(e);

      pool.on('connection:created', listener);
      pool.off('connection:created', listener);

      const acquired = await pool.acquire(createAcquireOptions());

      expect(events).toHaveLength(0);

      await acquired.release();
    });

    it('should handle listener errors gracefully', async () => {
      pool.on('connection:created', () => {
        throw new Error('Listener error');
      });

      // Should not throw
      const acquired = await pool.acquire(createAcquireOptions());
      expect(acquired.connection).toBeDefined();

      await acquired.release();
    });
  });

  describe('Health Check Logic', () => {
    it('should close timed out idle connections', async () => {
      pool = new ConnectionPool(
        createConfig({
          enableHealthCheck: true,
          healthCheckIntervalMs: 50,
          idleTimeoutMs: 10,
        })
      );

      const acquired = await pool.acquire(createAcquireOptions());
      await acquired.release();

      // Wait for health check and timeout
      await new Promise((resolve) => setTimeout(resolve, 100));

      const stats = await pool.getStats();
      expect(stats.timedOutConnections).toBeGreaterThanOrEqual(1);
    });

    it('should emit connection:timeout event', async () => {
      pool = new ConnectionPool(
        createConfig({
          enableHealthCheck: true,
          healthCheckIntervalMs: 50,
          idleTimeoutMs: 10,
        })
      );

      const events: ConnectionPoolEvent[] = [];
      pool.on('connection:timeout', (e) => events.push(e));

      const acquired = await pool.acquire(createAcquireOptions());
      await acquired.release();

      // Wait for health check
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(events.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Request Duration Tracking', () => {
    it('should track request duration', async () => {
      pool = new ConnectionPool(createConfig());

      const acquired = await pool.acquire(createAcquireOptions());

      // Simulate request time
      await new Promise((resolve) => setTimeout(resolve, 50));

      await acquired.release();

      const stats = await pool.getStats();
      expect(stats.avgRequestDurationMs).toBeGreaterThanOrEqual(50);
    });

    it('should track duration even on failure', async () => {
      pool = new ConnectionPool(createConfig());

      const acquired = await pool.acquire(createAcquireOptions());

      // Simulate request time
      await new Promise((resolve) => setTimeout(resolve, 50));

      await acquired.fail(new Error('Test'));

      const stats = await pool.getStats();
      expect(stats.avgRequestDurationMs).toBeGreaterThanOrEqual(50);
    });
  });
});
