/**
 * In-memory connection pool store
 */

import type { PooledConnection, ConnectionPoolStore } from '../types.mjs';
import { getHostKey } from '../config.mjs';

/**
 * In-memory implementation of ConnectionPoolStore
 */
export class MemoryConnectionStore implements ConnectionPoolStore {
  private connections: Map<string, PooledConnection> = new Map();
  private connectionsByHost: Map<string, Set<string>> = new Map();

  async getConnections(): Promise<PooledConnection[]> {
    return Array.from(this.connections.values());
  }

  async getConnectionsByHost(hostKey: string): Promise<PooledConnection[]> {
    const connectionIds = this.connectionsByHost.get(hostKey);
    if (!connectionIds) {
      return [];
    }

    const connections: PooledConnection[] = [];
    for (const id of connectionIds) {
      const conn = this.connections.get(id);
      if (conn) {
        connections.push(conn);
      }
    }
    return connections;
  }

  async addConnection(connection: PooledConnection): Promise<void> {
    this.connections.set(connection.id, connection);

    const hostKey = getHostKey(connection.host, connection.port);
    let hostConnections = this.connectionsByHost.get(hostKey);
    if (!hostConnections) {
      hostConnections = new Set();
      this.connectionsByHost.set(hostKey, hostConnections);
    }
    hostConnections.add(connection.id);
  }

  async updateConnection(
    connectionId: string,
    updates: Partial<PooledConnection>
  ): Promise<void> {
    const connection = this.connections.get(connectionId);
    if (!connection) {
      return;
    }

    // If host/port changes, update host index
    if (
      (updates.host !== undefined && updates.host !== connection.host) ||
      (updates.port !== undefined && updates.port !== connection.port)
    ) {
      const oldHostKey = getHostKey(connection.host, connection.port);
      const newHostKey = getHostKey(
        updates.host ?? connection.host,
        updates.port ?? connection.port
      );

      // Remove from old host set
      const oldHostConnections = this.connectionsByHost.get(oldHostKey);
      if (oldHostConnections) {
        oldHostConnections.delete(connectionId);
        if (oldHostConnections.size === 0) {
          this.connectionsByHost.delete(oldHostKey);
        }
      }

      // Add to new host set
      let newHostConnections = this.connectionsByHost.get(newHostKey);
      if (!newHostConnections) {
        newHostConnections = new Set();
        this.connectionsByHost.set(newHostKey, newHostConnections);
      }
      newHostConnections.add(connectionId);
    }

    // Update connection
    Object.assign(connection, updates);
  }

  async removeConnection(connectionId: string): Promise<boolean> {
    const connection = this.connections.get(connectionId);
    if (!connection) {
      return false;
    }

    // Remove from host index
    const hostKey = getHostKey(connection.host, connection.port);
    const hostConnections = this.connectionsByHost.get(hostKey);
    if (hostConnections) {
      hostConnections.delete(connectionId);
      if (hostConnections.size === 0) {
        this.connectionsByHost.delete(hostKey);
      }
    }

    // Remove from main map
    this.connections.delete(connectionId);
    return true;
  }

  async getCount(): Promise<number> {
    return this.connections.size;
  }

  async getCountByHost(hostKey: string): Promise<number> {
    const hostConnections = this.connectionsByHost.get(hostKey);
    return hostConnections?.size ?? 0;
  }

  async clear(): Promise<void> {
    this.connections.clear();
    this.connectionsByHost.clear();
  }

  async close(): Promise<void> {
    await this.clear();
  }

  /**
   * Get idle connections sorted by last used time (oldest first)
   */
  async getIdleConnections(): Promise<PooledConnection[]> {
    const idle: PooledConnection[] = [];
    for (const conn of this.connections.values()) {
      if (conn.state === 'idle') {
        idle.push(conn);
      }
    }
    return idle.sort((a, b) => a.lastUsedAt - b.lastUsedAt);
  }

  /**
   * Get connections that have exceeded max age
   */
  async getExpiredConnections(maxAgeMs: number): Promise<PooledConnection[]> {
    const now = Date.now();
    const expired: PooledConnection[] = [];
    for (const conn of this.connections.values()) {
      if (now - conn.createdAt > maxAgeMs) {
        expired.push(conn);
      }
    }
    return expired;
  }

  /**
   * Get connections that have been idle too long
   */
  async getTimedOutConnections(idleTimeoutMs: number): Promise<PooledConnection[]> {
    const now = Date.now();
    const timedOut: PooledConnection[] = [];
    for (const conn of this.connections.values()) {
      if (conn.state === 'idle' && now - conn.lastUsedAt > idleTimeoutMs) {
        timedOut.push(conn);
      }
    }
    return timedOut;
  }
}
