/**
 * Tests for connection-pool memory store
 *
 * Coverage includes:
 * - State Transition Testing: Connection state changes
 * - CRUD operations coverage
 * - Concurrent operations testing
 * - Boundary conditions for eviction
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { MemoryConnectionStore } from '../src/stores/memory.mjs';
import type { PooledConnection } from '../src/types.mjs';

function createConnection(overrides: Partial<PooledConnection> = {}): PooledConnection {
  const now = Date.now();
  return {
    id: `conn-${now}-${Math.random().toString(36).slice(2, 11)}`,
    host: 'example.com',
    port: 443,
    state: 'idle',
    health: 'healthy',
    createdAt: now,
    lastUsedAt: now,
    requestCount: 0,
    protocol: 'https',
    ...overrides,
  };
}

describe('MemoryConnectionStore', () => {
  let store: MemoryConnectionStore;

  beforeEach(() => {
    store = new MemoryConnectionStore();
  });

  describe('CRUD Operations', () => {
    describe('addConnection', () => {
      it('should add a connection', async () => {
        const conn = createConnection();
        await store.addConnection(conn);

        const connections = await store.getConnections();
        expect(connections).toHaveLength(1);
        expect(connections[0].id).toBe(conn.id);
      });

      it('should add multiple connections', async () => {
        const conn1 = createConnection({ id: 'conn-1' });
        const conn2 = createConnection({ id: 'conn-2' });

        await store.addConnection(conn1);
        await store.addConnection(conn2);

        const connections = await store.getConnections();
        expect(connections).toHaveLength(2);
      });

      it('should track connections by host', async () => {
        const conn1 = createConnection({ id: 'conn-1', host: 'api.example.com', port: 443 });
        const conn2 = createConnection({ id: 'conn-2', host: 'api.example.com', port: 443 });
        const conn3 = createConnection({ id: 'conn-3', host: 'other.example.com', port: 443 });

        await store.addConnection(conn1);
        await store.addConnection(conn2);
        await store.addConnection(conn3);

        const apiConnections = await store.getConnectionsByHost('api.example.com:443');
        expect(apiConnections).toHaveLength(2);

        const otherConnections = await store.getConnectionsByHost('other.example.com:443');
        expect(otherConnections).toHaveLength(1);
      });
    });

    describe('getConnections', () => {
      it('should return empty array when no connections', async () => {
        const connections = await store.getConnections();
        expect(connections).toEqual([]);
      });

      it('should return all connections', async () => {
        await store.addConnection(createConnection({ id: 'conn-1' }));
        await store.addConnection(createConnection({ id: 'conn-2' }));
        await store.addConnection(createConnection({ id: 'conn-3' }));

        const connections = await store.getConnections();
        expect(connections).toHaveLength(3);
      });
    });

    describe('getConnectionsByHost', () => {
      it('should return empty array for unknown host', async () => {
        const connections = await store.getConnectionsByHost('unknown.com:443');
        expect(connections).toEqual([]);
      });

      it('should filter by host key correctly', async () => {
        await store.addConnection(createConnection({ id: 'conn-1', host: 'a.com', port: 80 }));
        await store.addConnection(createConnection({ id: 'conn-2', host: 'a.com', port: 443 }));
        await store.addConnection(createConnection({ id: 'conn-3', host: 'b.com', port: 80 }));

        expect(await store.getConnectionsByHost('a.com:80')).toHaveLength(1);
        expect(await store.getConnectionsByHost('a.com:443')).toHaveLength(1);
        expect(await store.getConnectionsByHost('b.com:80')).toHaveLength(1);
      });
    });

    describe('updateConnection', () => {
      it('should update connection properties', async () => {
        const conn = createConnection({ id: 'conn-1', state: 'idle' });
        await store.addConnection(conn);

        await store.updateConnection('conn-1', { state: 'active', requestCount: 5 });

        const connections = await store.getConnections();
        expect(connections[0].state).toBe('active');
        expect(connections[0].requestCount).toBe(5);
      });

      it('should do nothing for non-existent connection', async () => {
        await store.updateConnection('non-existent', { state: 'active' });
        const connections = await store.getConnections();
        expect(connections).toHaveLength(0);
      });

      it('should update host index when host changes', async () => {
        const conn = createConnection({ id: 'conn-1', host: 'old.com', port: 80 });
        await store.addConnection(conn);

        await store.updateConnection('conn-1', { host: 'new.com' });

        expect(await store.getConnectionsByHost('old.com:80')).toHaveLength(0);
        expect(await store.getConnectionsByHost('new.com:80')).toHaveLength(1);
      });

      it('should update host index when port changes', async () => {
        const conn = createConnection({ id: 'conn-1', host: 'example.com', port: 80 });
        await store.addConnection(conn);

        await store.updateConnection('conn-1', { port: 443 });

        expect(await store.getConnectionsByHost('example.com:80')).toHaveLength(0);
        expect(await store.getConnectionsByHost('example.com:443')).toHaveLength(1);
      });
    });

    describe('removeConnection', () => {
      it('should remove connection', async () => {
        const conn = createConnection({ id: 'conn-1' });
        await store.addConnection(conn);

        const removed = await store.removeConnection('conn-1');

        expect(removed).toBe(true);
        expect(await store.getConnections()).toHaveLength(0);
      });

      it('should return false for non-existent connection', async () => {
        const removed = await store.removeConnection('non-existent');
        expect(removed).toBe(false);
      });

      it('should remove from host index', async () => {
        const conn = createConnection({ id: 'conn-1', host: 'example.com', port: 443 });
        await store.addConnection(conn);

        await store.removeConnection('conn-1');

        expect(await store.getConnectionsByHost('example.com:443')).toHaveLength(0);
      });

      it('should clean up empty host sets', async () => {
        const conn = createConnection({ id: 'conn-1', host: 'example.com', port: 443 });
        await store.addConnection(conn);
        await store.removeConnection('conn-1');

        // Add new connection to same host to verify set was cleaned
        const conn2 = createConnection({ id: 'conn-2', host: 'example.com', port: 443 });
        await store.addConnection(conn2);

        expect(await store.getConnectionsByHost('example.com:443')).toHaveLength(1);
      });
    });

    describe('getCount', () => {
      it('should return 0 for empty store', async () => {
        expect(await store.getCount()).toBe(0);
      });

      it('should return correct count', async () => {
        await store.addConnection(createConnection({ id: 'conn-1' }));
        await store.addConnection(createConnection({ id: 'conn-2' }));

        expect(await store.getCount()).toBe(2);
      });

      it('should update count after removal', async () => {
        await store.addConnection(createConnection({ id: 'conn-1' }));
        await store.addConnection(createConnection({ id: 'conn-2' }));
        await store.removeConnection('conn-1');

        expect(await store.getCount()).toBe(1);
      });
    });

    describe('getCountByHost', () => {
      it('should return 0 for unknown host', async () => {
        expect(await store.getCountByHost('unknown.com:443')).toBe(0);
      });

      it('should return correct count per host', async () => {
        await store.addConnection(createConnection({ id: 'conn-1', host: 'a.com', port: 80 }));
        await store.addConnection(createConnection({ id: 'conn-2', host: 'a.com', port: 80 }));
        await store.addConnection(createConnection({ id: 'conn-3', host: 'b.com', port: 80 }));

        expect(await store.getCountByHost('a.com:80')).toBe(2);
        expect(await store.getCountByHost('b.com:80')).toBe(1);
      });
    });

    describe('clear', () => {
      it('should remove all connections', async () => {
        await store.addConnection(createConnection({ id: 'conn-1' }));
        await store.addConnection(createConnection({ id: 'conn-2' }));

        await store.clear();

        expect(await store.getConnections()).toHaveLength(0);
        expect(await store.getCount()).toBe(0);
      });

      it('should clear host index', async () => {
        await store.addConnection(createConnection({ id: 'conn-1', host: 'a.com', port: 80 }));
        await store.addConnection(createConnection({ id: 'conn-2', host: 'b.com', port: 80 }));

        await store.clear();

        expect(await store.getConnectionsByHost('a.com:80')).toHaveLength(0);
        expect(await store.getConnectionsByHost('b.com:80')).toHaveLength(0);
      });
    });

    describe('close', () => {
      it('should clear all data', async () => {
        await store.addConnection(createConnection({ id: 'conn-1' }));

        await store.close();

        expect(await store.getConnections()).toHaveLength(0);
      });
    });
  });

  describe('State Transition Testing', () => {
    it('should track idle -> active transition', async () => {
      const conn = createConnection({ id: 'conn-1', state: 'idle' });
      await store.addConnection(conn);

      await store.updateConnection('conn-1', { state: 'active' });

      const connections = await store.getConnections();
      expect(connections[0].state).toBe('active');
    });

    it('should track active -> idle transition', async () => {
      const conn = createConnection({ id: 'conn-1', state: 'active' });
      await store.addConnection(conn);

      await store.updateConnection('conn-1', { state: 'idle' });

      const connections = await store.getConnections();
      expect(connections[0].state).toBe('idle');
    });

    it('should track idle -> draining transition', async () => {
      const conn = createConnection({ id: 'conn-1', state: 'idle' });
      await store.addConnection(conn);

      await store.updateConnection('conn-1', { state: 'draining' });

      const connections = await store.getConnections();
      expect(connections[0].state).toBe('draining');
    });

    it('should track any -> closed transition', async () => {
      const conn = createConnection({ id: 'conn-1', state: 'active' });
      await store.addConnection(conn);

      await store.updateConnection('conn-1', { state: 'closed' });

      const connections = await store.getConnections();
      expect(connections[0].state).toBe('closed');
    });

    it('should track health status transitions', async () => {
      const conn = createConnection({ id: 'conn-1', health: 'healthy' });
      await store.addConnection(conn);

      await store.updateConnection('conn-1', { health: 'unhealthy' });
      let connections = await store.getConnections();
      expect(connections[0].health).toBe('unhealthy');

      await store.updateConnection('conn-1', { health: 'unknown' });
      connections = await store.getConnections();
      expect(connections[0].health).toBe('unknown');

      await store.updateConnection('conn-1', { health: 'healthy' });
      connections = await store.getConnections();
      expect(connections[0].health).toBe('healthy');
    });
  });

  describe('getIdleConnections', () => {
    it('should return only idle connections', async () => {
      await store.addConnection(createConnection({ id: 'conn-1', state: 'idle' }));
      await store.addConnection(createConnection({ id: 'conn-2', state: 'active' }));
      await store.addConnection(createConnection({ id: 'conn-3', state: 'idle' }));

      const idle = await store.getIdleConnections();

      expect(idle).toHaveLength(2);
      expect(idle.every((c) => c.state === 'idle')).toBe(true);
    });

    it('should sort by last used time (oldest first)', async () => {
      const now = Date.now();
      await store.addConnection(
        createConnection({ id: 'conn-1', state: 'idle', lastUsedAt: now - 1000 })
      );
      await store.addConnection(
        createConnection({ id: 'conn-2', state: 'idle', lastUsedAt: now - 3000 })
      );
      await store.addConnection(
        createConnection({ id: 'conn-3', state: 'idle', lastUsedAt: now - 2000 })
      );

      const idle = await store.getIdleConnections();

      expect(idle[0].id).toBe('conn-2'); // oldest
      expect(idle[1].id).toBe('conn-3');
      expect(idle[2].id).toBe('conn-1'); // newest
    });

    it('should return empty array when no idle connections', async () => {
      await store.addConnection(createConnection({ id: 'conn-1', state: 'active' }));

      const idle = await store.getIdleConnections();
      expect(idle).toHaveLength(0);
    });
  });

  describe('getExpiredConnections', () => {
    it('should return connections older than max age', async () => {
      const now = Date.now();
      await store.addConnection(
        createConnection({ id: 'conn-1', createdAt: now - 10000 }) // 10 seconds old
      );
      await store.addConnection(
        createConnection({ id: 'conn-2', createdAt: now - 5000 }) // 5 seconds old
      );
      await store.addConnection(
        createConnection({ id: 'conn-3', createdAt: now - 1000 }) // 1 second old
      );

      const expired = await store.getExpiredConnections(6000); // 6 second max age

      expect(expired).toHaveLength(1);
      expect(expired[0].id).toBe('conn-1');
    });

    it('should return empty array when no expired connections', async () => {
      const now = Date.now();
      await store.addConnection(createConnection({ id: 'conn-1', createdAt: now }));

      const expired = await store.getExpiredConnections(60000);
      expect(expired).toHaveLength(0);
    });

    it('should handle boundary case (exactly at max age)', async () => {
      const now = Date.now();
      await store.addConnection(createConnection({ id: 'conn-1', createdAt: now - 5000 }));

      // At exactly max age, should NOT be expired (> not >=)
      const expired = await store.getExpiredConnections(5000);
      expect(expired).toHaveLength(0);
    });
  });

  describe('getTimedOutConnections', () => {
    it('should return idle connections past timeout', async () => {
      const now = Date.now();
      await store.addConnection(
        createConnection({ id: 'conn-1', state: 'idle', lastUsedAt: now - 10000 })
      );
      await store.addConnection(
        createConnection({ id: 'conn-2', state: 'idle', lastUsedAt: now - 1000 })
      );
      await store.addConnection(
        createConnection({ id: 'conn-3', state: 'active', lastUsedAt: now - 10000 })
      );

      const timedOut = await store.getTimedOutConnections(5000);

      expect(timedOut).toHaveLength(1);
      expect(timedOut[0].id).toBe('conn-1');
    });

    it('should not include active connections', async () => {
      const now = Date.now();
      await store.addConnection(
        createConnection({ id: 'conn-1', state: 'active', lastUsedAt: now - 10000 })
      );

      const timedOut = await store.getTimedOutConnections(5000);
      expect(timedOut).toHaveLength(0);
    });
  });

  describe('Concurrent Operations', () => {
    it('should handle concurrent adds', async () => {
      const promises = Array.from({ length: 100 }, (_, i) =>
        store.addConnection(createConnection({ id: `conn-${i}` }))
      );

      await Promise.all(promises);

      expect(await store.getCount()).toBe(100);
    });

    it('should handle concurrent removes', async () => {
      // Add 100 connections
      for (let i = 0; i < 100; i++) {
        await store.addConnection(createConnection({ id: `conn-${i}` }));
      }

      // Remove 50 concurrently
      const promises = Array.from({ length: 50 }, (_, i) =>
        store.removeConnection(`conn-${i}`)
      );

      await Promise.all(promises);

      expect(await store.getCount()).toBe(50);
    });

    it('should handle concurrent updates', async () => {
      await store.addConnection(createConnection({ id: 'conn-1', requestCount: 0 }));

      // Note: These updates are not atomic, so the final count depends on timing
      const promises = Array.from({ length: 10 }, (_, i) =>
        store.updateConnection('conn-1', { requestCount: i + 1 })
      );

      await Promise.all(promises);

      const connections = await store.getConnections();
      expect(connections[0].requestCount).toBeGreaterThanOrEqual(1);
    });

    it('should handle mixed operations', async () => {
      const operations: Promise<unknown>[] = [];

      for (let i = 0; i < 20; i++) {
        operations.push(store.addConnection(createConnection({ id: `conn-${i}` })));
      }

      await Promise.all(operations);

      const moreOperations: Promise<unknown>[] = [];
      for (let i = 0; i < 10; i++) {
        moreOperations.push(store.removeConnection(`conn-${i}`));
        moreOperations.push(
          store.updateConnection(`conn-${i + 10}`, { state: 'active' })
        );
      }

      await Promise.all(moreOperations);

      const count = await store.getCount();
      expect(count).toBe(10);
    });
  });

  describe('Boundary Conditions', () => {
    it('should handle empty string connection ID', async () => {
      const conn = createConnection({ id: '' });
      await store.addConnection(conn);

      expect(await store.getCount()).toBe(1);

      const removed = await store.removeConnection('');
      expect(removed).toBe(true);
    });

    it('should handle very long connection ID', async () => {
      const longId = 'conn-' + 'a'.repeat(1000);
      const conn = createConnection({ id: longId });
      await store.addConnection(conn);

      expect(await store.getCount()).toBe(1);
    });

    it('should handle port 0', async () => {
      const conn = createConnection({ id: 'conn-1', host: 'example.com', port: 0 });
      await store.addConnection(conn);

      const connections = await store.getConnectionsByHost('example.com:0');
      expect(connections).toHaveLength(1);
    });

    it('should handle maximum port number', async () => {
      const conn = createConnection({ id: 'conn-1', host: 'example.com', port: 65535 });
      await store.addConnection(conn);

      const connections = await store.getConnectionsByHost('example.com:65535');
      expect(connections).toHaveLength(1);
    });
  });
});
