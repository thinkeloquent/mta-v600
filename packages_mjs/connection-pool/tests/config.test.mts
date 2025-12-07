/**
 * Tests for connection-pool config module
 *
 * Coverage includes:
 * - Decision/Branch Coverage: All branches in validation logic
 * - Boundary Value Analysis: Edge cases for numeric limits
 * - Equivalence Partitioning: Valid/invalid configuration values
 */

import { describe, it, expect } from 'vitest';
import {
  DEFAULT_CONNECTION_POOL_CONFIG,
  mergeConfig,
  validateConfig,
  getHostKey,
  parseHostKey,
  generateConnectionId,
} from '../src/config.mjs';
import type { ConnectionPoolConfig } from '../src/types.mjs';

describe('DEFAULT_CONNECTION_POOL_CONFIG', () => {
  it('should have sensible defaults', () => {
    expect(DEFAULT_CONNECTION_POOL_CONFIG.id).toBe('default-pool');
    expect(DEFAULT_CONNECTION_POOL_CONFIG.maxConnections).toBe(100);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.maxConnectionsPerHost).toBe(10);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.maxIdleConnections).toBe(20);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.idleTimeoutMs).toBe(60000);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.keepAliveTimeoutMs).toBe(30000);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.connectTimeoutMs).toBe(10000);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.enableHealthCheck).toBe(true);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.healthCheckIntervalMs).toBe(30000);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.maxConnectionAgeMs).toBe(300000);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.keepAlive).toBe(true);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.queueRequests).toBe(true);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.maxQueueSize).toBe(1000);
    expect(DEFAULT_CONNECTION_POOL_CONFIG.queueTimeoutMs).toBe(30000);
  });
});

describe('mergeConfig', () => {
  it('should merge user config with defaults', () => {
    const userConfig: ConnectionPoolConfig = {
      id: 'custom-pool',
      maxConnections: 50,
    };

    const merged = mergeConfig(userConfig);

    expect(merged.id).toBe('custom-pool');
    expect(merged.maxConnections).toBe(50);
    expect(merged.maxConnectionsPerHost).toBe(10); // default
    expect(merged.idleTimeoutMs).toBe(60000); // default
  });

  it('should override all defaults when provided', () => {
    const userConfig: ConnectionPoolConfig = {
      id: 'full-custom',
      maxConnections: 200,
      maxConnectionsPerHost: 20,
      maxIdleConnections: 50,
      idleTimeoutMs: 120000,
      keepAliveTimeoutMs: 60000,
      connectTimeoutMs: 5000,
      enableHealthCheck: false,
      healthCheckIntervalMs: 60000,
      maxConnectionAgeMs: 600000,
      keepAlive: false,
      queueRequests: false,
      maxQueueSize: 500,
      queueTimeoutMs: 15000,
    };

    const merged = mergeConfig(userConfig);

    expect(merged).toEqual({
      ...DEFAULT_CONNECTION_POOL_CONFIG,
      ...userConfig,
    });
  });

  it('should handle partial config', () => {
    const userConfig: ConnectionPoolConfig = {
      id: 'partial',
    };

    const merged = mergeConfig(userConfig);

    expect(merged.id).toBe('partial');
    expect(merged.maxConnections).toBe(100);
  });
});

describe('validateConfig', () => {
  describe('Decision/Branch Coverage - Individual field validation', () => {
    it('should return empty array for valid config', () => {
      const config: ConnectionPoolConfig = {
        id: 'valid-pool',
        maxConnections: 100,
        maxConnectionsPerHost: 10,
        maxIdleConnections: 20,
      };

      const errors = validateConfig(config);
      expect(errors).toEqual([]);
    });

    it('should detect maxConnections < 1', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnections: 0,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('maxConnections must be at least 1');
    });

    it('should detect maxConnectionsPerHost < 1', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnectionsPerHost: 0,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('maxConnectionsPerHost must be at least 1');
    });

    it('should detect negative maxIdleConnections', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxIdleConnections: -1,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('maxIdleConnections must be non-negative');
    });

    it('should detect negative idleTimeoutMs', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        idleTimeoutMs: -1,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('idleTimeoutMs must be non-negative');
    });

    it('should detect negative keepAliveTimeoutMs', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        keepAliveTimeoutMs: -1,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('keepAliveTimeoutMs must be non-negative');
    });

    it('should detect negative connectTimeoutMs', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        connectTimeoutMs: -1,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('connectTimeoutMs must be non-negative');
    });

    it('should detect healthCheckIntervalMs < 1000', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        healthCheckIntervalMs: 999,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('healthCheckIntervalMs must be at least 1000ms');
    });

    it('should detect negative maxConnectionAgeMs', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnectionAgeMs: -1,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('maxConnectionAgeMs must be non-negative');
    });

    it('should detect negative maxQueueSize', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxQueueSize: -1,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('maxQueueSize must be non-negative');
    });

    it('should detect negative queueTimeoutMs', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        queueTimeoutMs: -1,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('queueTimeoutMs must be non-negative');
    });
  });

  describe('Cross-field validation', () => {
    it('should detect maxConnectionsPerHost > maxConnections', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnections: 10,
        maxConnectionsPerHost: 20,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('maxConnectionsPerHost cannot exceed maxConnections');
    });

    it('should detect maxIdleConnections > maxConnections', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnections: 10,
        maxIdleConnections: 20,
      };

      const errors = validateConfig(config);
      expect(errors).toContain('maxIdleConnections cannot exceed maxConnections');
    });

    it('should allow maxConnectionsPerHost == maxConnections', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnections: 10,
        maxConnectionsPerHost: 10,
      };

      const errors = validateConfig(config);
      expect(errors).not.toContain('maxConnectionsPerHost cannot exceed maxConnections');
    });
  });

  describe('Boundary Value Analysis', () => {
    it('should accept maxConnections = 1 (minimum valid)', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnections: 1,
      };

      const errors = validateConfig(config);
      expect(errors).not.toContain('maxConnections must be at least 1');
    });

    it('should accept maxIdleConnections = 0 (boundary)', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxIdleConnections: 0,
      };

      const errors = validateConfig(config);
      expect(errors).not.toContain('maxIdleConnections must be non-negative');
    });

    it('should accept healthCheckIntervalMs = 1000 (minimum valid)', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        healthCheckIntervalMs: 1000,
      };

      const errors = validateConfig(config);
      expect(errors).not.toContain('healthCheckIntervalMs must be at least 1000ms');
    });

    it('should accept very large values', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnections: Number.MAX_SAFE_INTEGER,
        maxConnectionsPerHost: 1000000,
        idleTimeoutMs: 86400000, // 24 hours
      };

      const errors = validateConfig(config);
      expect(errors.length).toBe(0);
    });
  });

  describe('Multiple errors', () => {
    it('should return all errors for invalid config', () => {
      const config: ConnectionPoolConfig = {
        id: 'test',
        maxConnections: 0,
        maxConnectionsPerHost: 0,
        maxIdleConnections: -1,
        idleTimeoutMs: -1,
      };

      const errors = validateConfig(config);
      expect(errors.length).toBeGreaterThanOrEqual(4);
    });
  });
});

describe('getHostKey', () => {
  it('should generate host:port format', () => {
    expect(getHostKey('example.com', 443)).toBe('example.com:443');
    expect(getHostKey('localhost', 8080)).toBe('localhost:8080');
  });

  it('should handle IPv4 addresses', () => {
    expect(getHostKey('192.168.1.1', 80)).toBe('192.168.1.1:80');
  });

  it('should handle IPv6 addresses', () => {
    expect(getHostKey('::1', 8080)).toBe('::1:8080');
    expect(getHostKey('2001:db8::1', 443)).toBe('2001:db8::1:443');
  });

  it('should handle special characters in host', () => {
    expect(getHostKey('sub.domain.example.com', 443)).toBe('sub.domain.example.com:443');
  });
});

describe('parseHostKey', () => {
  it('should parse host:port format', () => {
    const result = parseHostKey('example.com:443');
    expect(result.host).toBe('example.com');
    expect(result.port).toBe(443);
  });

  it('should parse localhost', () => {
    const result = parseHostKey('localhost:8080');
    expect(result.host).toBe('localhost');
    expect(result.port).toBe(8080);
  });

  it('should handle IPv4 addresses', () => {
    const result = parseHostKey('192.168.1.1:80');
    expect(result.host).toBe('192.168.1.1');
    expect(result.port).toBe(80);
  });

  it('should handle IPv6 addresses (last colon is port)', () => {
    const result = parseHostKey('::1:8080');
    expect(result.host).toBe('::1');
    expect(result.port).toBe(8080);
  });

  it('should throw for invalid host key without colon', () => {
    expect(() => parseHostKey('example.com')).toThrow('Invalid host key: example.com');
  });

  it('should be inverse of getHostKey', () => {
    const original = { host: 'example.com', port: 443 };
    const hostKey = getHostKey(original.host, original.port);
    const parsed = parseHostKey(hostKey);
    expect(parsed).toEqual(original);
  });
});

describe('generateConnectionId', () => {
  it('should generate unique IDs', () => {
    const ids = new Set<string>();
    for (let i = 0; i < 1000; i++) {
      ids.add(generateConnectionId());
    }
    expect(ids.size).toBe(1000);
  });

  it('should start with "conn-" prefix', () => {
    const id = generateConnectionId();
    expect(id.startsWith('conn-')).toBe(true);
  });

  it('should contain timestamp', () => {
    const before = Date.now();
    const id = generateConnectionId();
    const after = Date.now();

    // Extract timestamp from ID (conn-{timestamp}-{random})
    const parts = id.split('-');
    const timestamp = parseInt(parts[1], 10);

    expect(timestamp).toBeGreaterThanOrEqual(before);
    expect(timestamp).toBeLessThanOrEqual(after);
  });

  it('should have random suffix', () => {
    const id = generateConnectionId();
    const parts = id.split('-');
    expect(parts.length).toBe(3);
    expect(parts[2].length).toBeGreaterThan(0);
  });
});
