/**
 * Configuration utilities for connection-pool
 */

import type { ConnectionPoolConfig } from './types.mjs';

/**
 * Default connection pool configuration
 */
export const DEFAULT_CONNECTION_POOL_CONFIG: Required<ConnectionPoolConfig> = {
  id: 'default-pool',
  maxConnections: 100,
  maxConnectionsPerHost: 10,
  maxIdleConnections: 20,
  idleTimeoutMs: 60000,
  keepAliveTimeoutMs: 30000,
  connectTimeoutMs: 10000,
  enableHealthCheck: true,
  healthCheckIntervalMs: 30000,
  maxConnectionAgeMs: 300000,
  keepAlive: true,
  queueRequests: true,
  maxQueueSize: 1000,
  queueTimeoutMs: 30000,
};

/**
 * Merge user config with defaults
 */
export function mergeConfig(
  userConfig: ConnectionPoolConfig
): Required<ConnectionPoolConfig> {
  return {
    ...DEFAULT_CONNECTION_POOL_CONFIG,
    ...userConfig,
  };
}

/**
 * Validate configuration values
 */
export function validateConfig(config: ConnectionPoolConfig): string[] {
  const errors: string[] = [];

  if (config.maxConnections !== undefined && config.maxConnections < 1) {
    errors.push('maxConnections must be at least 1');
  }

  if (config.maxConnectionsPerHost !== undefined && config.maxConnectionsPerHost < 1) {
    errors.push('maxConnectionsPerHost must be at least 1');
  }

  if (config.maxIdleConnections !== undefined && config.maxIdleConnections < 0) {
    errors.push('maxIdleConnections must be non-negative');
  }

  if (config.idleTimeoutMs !== undefined && config.idleTimeoutMs < 0) {
    errors.push('idleTimeoutMs must be non-negative');
  }

  if (config.keepAliveTimeoutMs !== undefined && config.keepAliveTimeoutMs < 0) {
    errors.push('keepAliveTimeoutMs must be non-negative');
  }

  if (config.connectTimeoutMs !== undefined && config.connectTimeoutMs < 0) {
    errors.push('connectTimeoutMs must be non-negative');
  }

  if (config.healthCheckIntervalMs !== undefined && config.healthCheckIntervalMs < 1000) {
    errors.push('healthCheckIntervalMs must be at least 1000ms');
  }

  if (config.maxConnectionAgeMs !== undefined && config.maxConnectionAgeMs < 0) {
    errors.push('maxConnectionAgeMs must be non-negative');
  }

  if (config.maxQueueSize !== undefined && config.maxQueueSize < 0) {
    errors.push('maxQueueSize must be non-negative');
  }

  if (config.queueTimeoutMs !== undefined && config.queueTimeoutMs < 0) {
    errors.push('queueTimeoutMs must be non-negative');
  }

  // Cross-field validations
  if (
    config.maxConnectionsPerHost !== undefined &&
    config.maxConnections !== undefined &&
    config.maxConnectionsPerHost > config.maxConnections
  ) {
    errors.push('maxConnectionsPerHost cannot exceed maxConnections');
  }

  if (
    config.maxIdleConnections !== undefined &&
    config.maxConnections !== undefined &&
    config.maxIdleConnections > config.maxConnections
  ) {
    errors.push('maxIdleConnections cannot exceed maxConnections');
  }

  return errors;
}

/**
 * Generate a host key from host and port
 */
export function getHostKey(host: string, port: number): string {
  return `${host}:${port}`;
}

/**
 * Parse a host key back to host and port
 */
export function parseHostKey(hostKey: string): { host: string; port: number } {
  const lastColonIndex = hostKey.lastIndexOf(':');
  if (lastColonIndex === -1) {
    throw new Error(`Invalid host key: ${hostKey}`);
  }
  return {
    host: hostKey.slice(0, lastColonIndex),
    port: parseInt(hostKey.slice(lastColonIndex + 1), 10),
  };
}

/**
 * Generate a unique connection ID
 */
export function generateConnectionId(): string {
  return `conn-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}
