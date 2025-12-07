/**
 * Tests for config utilities
 *
 * Coverage includes:
 * - Decision/Branch Coverage: All config merge branches
 * - Boundary Value Analysis: TTL clamping at min/max bounds
 * - Equivalence Partitioning: Load balance strategy selection
 * - State Testing: Load balance state management
 * - Property Testing: DSN parsing with various formats
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  DEFAULT_DNS_CACHE_CONFIG,
  DEFAULT_HEALTH_CHECK_CONFIG,
  mergeConfig,
  clampTtl,
  isExpired,
  isWithinGracePeriod,
  selectEndpoint,
  createLoadBalanceState,
  getEndpointKey,
  parseDsn,
  sleep,
  type LoadBalanceState,
} from '../src/config.mjs';
import type { DnsCacheConfig, ResolvedEndpoint } from '../src/types.mjs';

describe('config utilities', () => {
  describe('DEFAULT_DNS_CACHE_CONFIG', () => {
    it('should have sensible defaults', () => {
      expect(DEFAULT_DNS_CACHE_CONFIG.defaultTtlMs).toBe(60000);
      expect(DEFAULT_DNS_CACHE_CONFIG.minTtlMs).toBe(1000);
      expect(DEFAULT_DNS_CACHE_CONFIG.maxTtlMs).toBe(300000);
      expect(DEFAULT_DNS_CACHE_CONFIG.maxEntries).toBe(1000);
      expect(DEFAULT_DNS_CACHE_CONFIG.respectDnsTtl).toBe(true);
      expect(DEFAULT_DNS_CACHE_CONFIG.negativeTtlMs).toBe(30000);
      expect(DEFAULT_DNS_CACHE_CONFIG.staleWhileRevalidate).toBe(true);
      expect(DEFAULT_DNS_CACHE_CONFIG.staleGracePeriodMs).toBe(5000);
      expect(DEFAULT_DNS_CACHE_CONFIG.loadBalanceStrategy).toBe('round-robin');
    });
  });

  describe('DEFAULT_HEALTH_CHECK_CONFIG', () => {
    it('should have sensible defaults', () => {
      expect(DEFAULT_HEALTH_CHECK_CONFIG.enabled).toBe(false);
      expect(DEFAULT_HEALTH_CHECK_CONFIG.intervalMs).toBe(30000);
      expect(DEFAULT_HEALTH_CHECK_CONFIG.timeoutMs).toBe(5000);
      expect(DEFAULT_HEALTH_CHECK_CONFIG.unhealthyThreshold).toBe(3);
      expect(DEFAULT_HEALTH_CHECK_CONFIG.healthyThreshold).toBe(2);
    });
  });

  describe('mergeConfig', () => {
    it('should merge minimal config with defaults', () => {
      const config: DnsCacheConfig = { id: 'test' };
      const merged = mergeConfig(config);

      expect(merged.id).toBe('test');
      expect(merged.defaultTtlMs).toBe(DEFAULT_DNS_CACHE_CONFIG.defaultTtlMs);
      expect(merged.minTtlMs).toBe(DEFAULT_DNS_CACHE_CONFIG.minTtlMs);
      expect(merged.maxTtlMs).toBe(DEFAULT_DNS_CACHE_CONFIG.maxTtlMs);
      expect(merged.loadBalanceStrategy).toBe('round-robin');
    });

    it('should preserve user-provided values', () => {
      const config: DnsCacheConfig = {
        id: 'test',
        defaultTtlMs: 120000,
        minTtlMs: 5000,
        maxTtlMs: 600000,
        maxEntries: 500,
        loadBalanceStrategy: 'power-of-two',
      };

      const merged = mergeConfig(config);

      expect(merged.defaultTtlMs).toBe(120000);
      expect(merged.minTtlMs).toBe(5000);
      expect(merged.maxTtlMs).toBe(600000);
      expect(merged.maxEntries).toBe(500);
      expect(merged.loadBalanceStrategy).toBe('power-of-two');
    });

    it('should merge health check config with defaults', () => {
      const config: DnsCacheConfig = {
        id: 'test',
        healthCheck: {
          enabled: true,
          intervalMs: 60000,
        },
      };

      const merged = mergeConfig(config);

      expect(merged.healthCheck.enabled).toBe(true);
      expect(merged.healthCheck.intervalMs).toBe(60000);
      expect(merged.healthCheck.timeoutMs).toBe(DEFAULT_HEALTH_CHECK_CONFIG.timeoutMs);
    });

    it('should handle undefined health check', () => {
      const config: DnsCacheConfig = { id: 'test' };
      const merged = mergeConfig(config);

      expect(merged.healthCheck).toEqual(DEFAULT_HEALTH_CHECK_CONFIG);
    });
  });

  describe('clampTtl', () => {
    it('should return value within bounds unchanged', () => {
      expect(clampTtl(60000, 1000, 300000)).toBe(60000);
    });

    it('should clamp value below minimum', () => {
      expect(clampTtl(500, 1000, 300000)).toBe(1000);
    });

    it('should clamp value above maximum', () => {
      expect(clampTtl(500000, 1000, 300000)).toBe(300000);
    });

    it('should handle edge case: value equals minimum', () => {
      expect(clampTtl(1000, 1000, 300000)).toBe(1000);
    });

    it('should handle edge case: value equals maximum', () => {
      expect(clampTtl(300000, 1000, 300000)).toBe(300000);
    });

    it('should handle zero values', () => {
      expect(clampTtl(0, 0, 100)).toBe(0);
    });

    it('should handle negative input', () => {
      expect(clampTtl(-100, 1000, 300000)).toBe(1000);
    });
  });

  describe('isExpired', () => {
    it('should return true when now >= expiresAt', () => {
      const expiresAt = 1000;
      expect(isExpired(expiresAt, 1000)).toBe(true);
      expect(isExpired(expiresAt, 1001)).toBe(true);
    });

    it('should return false when now < expiresAt', () => {
      const expiresAt = 1000;
      expect(isExpired(expiresAt, 999)).toBe(false);
    });

    it('should use Date.now() when now is not provided', () => {
      const futureTime = Date.now() + 100000;
      expect(isExpired(futureTime)).toBe(false);

      const pastTime = Date.now() - 1000;
      expect(isExpired(pastTime)).toBe(true);
    });

    it('should handle boundary: exactly at expiry time', () => {
      const expiresAt = 1000;
      expect(isExpired(expiresAt, 1000)).toBe(true);
    });
  });

  describe('isWithinGracePeriod', () => {
    it('should return true when within grace period', () => {
      const expiresAt = 1000;
      const gracePeriodMs = 5000;
      expect(isWithinGracePeriod(expiresAt, gracePeriodMs, 1001)).toBe(true);
      expect(isWithinGracePeriod(expiresAt, gracePeriodMs, 5999)).toBe(true);
    });

    it('should return false when past grace period', () => {
      const expiresAt = 1000;
      const gracePeriodMs = 5000;
      expect(isWithinGracePeriod(expiresAt, gracePeriodMs, 6001)).toBe(false);
    });

    it('should return true when not yet expired', () => {
      const expiresAt = 1000;
      const gracePeriodMs = 5000;
      expect(isWithinGracePeriod(expiresAt, gracePeriodMs, 500)).toBe(true);
    });

    it('should handle boundary: exactly at grace period end', () => {
      const expiresAt = 1000;
      const gracePeriodMs = 5000;
      expect(isWithinGracePeriod(expiresAt, gracePeriodMs, 6000)).toBe(false);
    });

    it('should handle zero grace period', () => {
      const expiresAt = 1000;
      expect(isWithinGracePeriod(expiresAt, 0, 1000)).toBe(false);
      expect(isWithinGracePeriod(expiresAt, 0, 999)).toBe(true);
    });
  });

  describe('createLoadBalanceState', () => {
    it('should create empty state', () => {
      const state = createLoadBalanceState();
      expect(state.roundRobinIndex).toBeInstanceOf(Map);
      expect(state.activeConnections).toBeInstanceOf(Map);
      expect(state.roundRobinIndex.size).toBe(0);
      expect(state.activeConnections.size).toBe(0);
    });
  });

  describe('getEndpointKey', () => {
    it('should create key from host and port', () => {
      const endpoint: ResolvedEndpoint = {
        host: '192.168.1.1',
        port: 8080,
        healthy: true,
      };
      expect(getEndpointKey(endpoint)).toBe('192.168.1.1:8080');
    });

    it('should handle IPv6 addresses', () => {
      const endpoint: ResolvedEndpoint = {
        host: '::1',
        port: 443,
        healthy: true,
      };
      expect(getEndpointKey(endpoint)).toBe('::1:443');
    });

    it('should handle hostnames', () => {
      const endpoint: ResolvedEndpoint = {
        host: 'api.example.com',
        port: 80,
        healthy: true,
      };
      expect(getEndpointKey(endpoint)).toBe('api.example.com:80');
    });
  });

  describe('selectEndpoint', () => {
    let state: LoadBalanceState;
    let healthyEndpoints: ResolvedEndpoint[];
    let mixedEndpoints: ResolvedEndpoint[];

    beforeEach(() => {
      state = createLoadBalanceState();
      healthyEndpoints = [
        { host: '10.0.0.1', port: 80, healthy: true },
        { host: '10.0.0.2', port: 80, healthy: true },
        { host: '10.0.0.3', port: 80, healthy: true },
      ];
      mixedEndpoints = [
        { host: '10.0.0.1', port: 80, healthy: true },
        { host: '10.0.0.2', port: 80, healthy: false },
        { host: '10.0.0.3', port: 80, healthy: true },
      ];
    });

    describe('round-robin strategy', () => {
      it('should cycle through endpoints in order', () => {
        const selected = [];
        for (let i = 0; i < 6; i++) {
          selected.push(selectEndpoint(healthyEndpoints, 'round-robin', state)?.host);
        }

        expect(selected).toEqual([
          '10.0.0.1',
          '10.0.0.2',
          '10.0.0.3',
          '10.0.0.1',
          '10.0.0.2',
          '10.0.0.3',
        ]);
      });

      it('should skip unhealthy endpoints', () => {
        const selected = [];
        for (let i = 0; i < 4; i++) {
          selected.push(selectEndpoint(mixedEndpoints, 'round-robin', state)?.host);
        }

        expect(selected).not.toContain('10.0.0.2');
      });
    });

    describe('random strategy', () => {
      it('should return a valid endpoint', () => {
        const selected = selectEndpoint(healthyEndpoints, 'random', state);
        expect(selected).toBeDefined();
        expect(healthyEndpoints).toContainEqual(selected);
      });

      it('should only select healthy endpoints', () => {
        for (let i = 0; i < 100; i++) {
          const selected = selectEndpoint(mixedEndpoints, 'random', state);
          expect(selected?.healthy).toBe(true);
        }
      });
    });

    describe('weighted strategy', () => {
      it('should respect weights', () => {
        const weightedEndpoints: ResolvedEndpoint[] = [
          { host: '10.0.0.1', port: 80, healthy: true, weight: 10 },
          { host: '10.0.0.2', port: 80, healthy: true, weight: 1 },
        ];

        const counts: Record<string, number> = { '10.0.0.1': 0, '10.0.0.2': 0 };
        for (let i = 0; i < 1000; i++) {
          const selected = selectEndpoint(weightedEndpoints, 'weighted', state);
          if (selected) counts[selected.host]++;
        }

        // With 10:1 weight ratio, first endpoint should be selected ~10x more
        expect(counts['10.0.0.1']).toBeGreaterThan(counts['10.0.0.2'] * 5);
      });

      it('should default weight to 1', () => {
        const selected = selectEndpoint(healthyEndpoints, 'weighted', state);
        expect(selected).toBeDefined();
      });
    });

    describe('least-connections strategy', () => {
      it('should select endpoint with fewest connections', () => {
        state.activeConnections.set('10.0.0.1:80', 5);
        state.activeConnections.set('10.0.0.2:80', 2);
        state.activeConnections.set('10.0.0.3:80', 8);

        const selected = selectEndpoint(healthyEndpoints, 'least-connections', state);
        expect(selected?.host).toBe('10.0.0.2');
      });

      it('should select first with 0 connections when all are equal', () => {
        const selected = selectEndpoint(healthyEndpoints, 'least-connections', state);
        expect(selected?.host).toBe('10.0.0.1');
      });
    });

    describe('power-of-two strategy', () => {
      it('should select one of two random endpoints with fewer connections', () => {
        state.activeConnections.set('10.0.0.1:80', 10);
        state.activeConnections.set('10.0.0.2:80', 1);
        state.activeConnections.set('10.0.0.3:80', 10);

        // Run multiple times - endpoint 2 should be selected more often
        const counts: Record<string, number> = {};
        for (let i = 0; i < 100; i++) {
          const selected = selectEndpoint(healthyEndpoints, 'power-of-two', state);
          if (selected) {
            counts[selected.host] = (counts[selected.host] || 0) + 1;
          }
        }

        // Endpoint with 1 connection should be selected more often
        expect(counts['10.0.0.2']).toBeGreaterThan(10);
      });

      it('should handle single endpoint', () => {
        const singleEndpoint = [healthyEndpoints[0]];
        const selected = selectEndpoint(singleEndpoint, 'power-of-two', state);
        expect(selected).toEqual(healthyEndpoints[0]);
      });
    });

    describe('edge cases', () => {
      it('should return undefined for empty array', () => {
        const selected = selectEndpoint([], 'round-robin', state);
        expect(selected).toBeUndefined();
      });

      it('should fall back to first endpoint when all unhealthy', () => {
        const allUnhealthy: ResolvedEndpoint[] = [
          { host: '10.0.0.1', port: 80, healthy: false },
          { host: '10.0.0.2', port: 80, healthy: false },
        ];
        const selected = selectEndpoint(allUnhealthy, 'round-robin', state);
        expect(selected?.host).toBe('10.0.0.1');
      });

      it('should handle single healthy endpoint', () => {
        const single: ResolvedEndpoint[] = [{ host: '10.0.0.1', port: 80, healthy: true }];
        const selected = selectEndpoint(single, 'round-robin', state);
        expect(selected?.host).toBe('10.0.0.1');
      });
    });
  });

  describe('parseDsn', () => {
    describe('URL format', () => {
      it('should parse https URL', () => {
        const result = parseDsn('https://api.example.com:8443/path');
        expect(result.protocol).toBe('https');
        expect(result.host).toBe('api.example.com');
        expect(result.port).toBe(8443);
      });

      it('should parse http URL', () => {
        const result = parseDsn('http://localhost:3000');
        expect(result.protocol).toBe('http');
        expect(result.host).toBe('localhost');
        expect(result.port).toBe(3000);
      });

      it('should handle URL without port', () => {
        const result = parseDsn('https://api.example.com/path');
        expect(result.protocol).toBe('https');
        expect(result.host).toBe('api.example.com');
        expect(result.port).toBeUndefined();
      });
    });

    describe('host:port format', () => {
      it('should parse hostname with port', () => {
        const result = parseDsn('api.example.com:8080');
        expect(result.host).toBe('api.example.com');
        expect(result.port).toBe(8080);
        expect(result.protocol).toBeUndefined();
      });

      it('should parse IP address with port', () => {
        const result = parseDsn('192.168.1.1:3000');
        expect(result.host).toBe('192.168.1.1');
        expect(result.port).toBe(3000);
      });

      it('should parse localhost with port', () => {
        const result = parseDsn('localhost:5432');
        expect(result.host).toBe('localhost');
        expect(result.port).toBe(5432);
      });
    });

    describe('hostname only', () => {
      it('should parse plain hostname', () => {
        const result = parseDsn('api.example.com');
        expect(result.host).toBe('api.example.com');
        expect(result.port).toBeUndefined();
        expect(result.protocol).toBeUndefined();
      });

      it('should parse IP address', () => {
        const result = parseDsn('192.168.1.1');
        expect(result.host).toBe('192.168.1.1');
        expect(result.port).toBeUndefined();
      });

      it('should parse localhost', () => {
        const result = parseDsn('localhost');
        expect(result.host).toBe('localhost');
      });
    });

    describe('edge cases', () => {
      it('should handle empty string', () => {
        const result = parseDsn('');
        expect(result.host).toBe('');
      });

      it('should handle invalid port (non-numeric)', () => {
        const result = parseDsn('example.com:abc');
        expect(result.host).toBe('example.com:abc');
        expect(result.port).toBeUndefined();
      });
    });
  });

  describe('sleep', () => {
    it('should resolve after specified delay', async () => {
      const start = Date.now();
      await sleep(50);
      const elapsed = Date.now() - start;
      expect(elapsed).toBeGreaterThanOrEqual(40);
    });

    it('should reject if already aborted', async () => {
      const controller = new AbortController();
      controller.abort();

      await expect(sleep(1000, controller.signal)).rejects.toThrow('Aborted');
    });

    it('should reject when aborted during sleep', async () => {
      const controller = new AbortController();
      const promise = sleep(1000, controller.signal);

      setTimeout(() => controller.abort(), 10);

      await expect(promise).rejects.toThrow('Aborted');
    });

    it('should handle zero delay', async () => {
      const start = Date.now();
      await sleep(0);
      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(50);
    });
  });
});
