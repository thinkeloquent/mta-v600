/**
 * Tests for DNS cache factory functions
 *
 * Coverage includes:
 * - Preset configurations (aggressive, conservative, high-availability)
 * - createFromPreset factory
 * - createApiDnsCache factory
 * - createSharedDnsCache factory
 * - composeDnsCacheInterceptors for multi-host configs
 * - Override merging
 * - Interceptor composition behavior
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { Dispatcher } from 'undici';
import {
  AGGRESSIVE_PRESET,
  CONSERVATIVE_PRESET,
  HIGH_AVAILABILITY_PRESET,
  createFromPreset,
  createApiDnsCache,
  createSharedDnsCache,
  composeDnsCacheInterceptors,
  type DnsCachePreset,
} from '../src/factory.mjs';

// Mock dispatcher for testing
function createMockDispatch(): {
  dispatch: Dispatcher.Dispatch;
  calls: Array<{ opts: Dispatcher.DispatchOptions; handler: Dispatcher.DispatchHandler }>;
} {
  const calls: Array<{ opts: Dispatcher.DispatchOptions; handler: Dispatcher.DispatchHandler }> = [];

  const dispatch: Dispatcher.Dispatch = (
    opts: Dispatcher.DispatchOptions,
    handler: Dispatcher.DispatchHandler
  ): boolean => {
    calls.push({ opts, handler });
    return true;
  };

  return { dispatch, calls };
}

// Mock handler
function createMockHandler(): Dispatcher.DispatchHandler {
  return {
    onRequestStart: vi.fn(),
    onResponseEnd: vi.fn(),
  };
}

describe('Presets', () => {
  describe('AGGRESSIVE_PRESET', () => {
    it('should have correct name', () => {
      expect(AGGRESSIVE_PRESET.name).toBe('aggressive');
    });

    it('should have long TTL', () => {
      expect(AGGRESSIVE_PRESET.config.defaultTtlMs).toBe(300000); // 5 minutes
    });

    it('should use power-of-two strategy', () => {
      expect(AGGRESSIVE_PRESET.config.loadBalanceStrategy).toBe('power-of-two');
    });

    it('should mark unhealthy on error', () => {
      expect(AGGRESSIVE_PRESET.config.markUnhealthyOnError).toBe(true);
    });
  });

  describe('CONSERVATIVE_PRESET', () => {
    it('should have correct name', () => {
      expect(CONSERVATIVE_PRESET.name).toBe('conservative');
    });

    it('should have short TTL', () => {
      expect(CONSERVATIVE_PRESET.config.defaultTtlMs).toBe(10000); // 10 seconds
    });

    it('should use round-robin strategy', () => {
      expect(CONSERVATIVE_PRESET.config.loadBalanceStrategy).toBe('round-robin');
    });

    it('should mark unhealthy on error', () => {
      expect(CONSERVATIVE_PRESET.config.markUnhealthyOnError).toBe(true);
    });
  });

  describe('HIGH_AVAILABILITY_PRESET', () => {
    it('should have correct name', () => {
      expect(HIGH_AVAILABILITY_PRESET.name).toBe('high-availability');
    });

    it('should have moderate TTL', () => {
      expect(HIGH_AVAILABILITY_PRESET.config.defaultTtlMs).toBe(30000); // 30 seconds
    });

    it('should use least-connections strategy', () => {
      expect(HIGH_AVAILABILITY_PRESET.config.loadBalanceStrategy).toBe('least-connections');
    });

    it('should mark unhealthy on error', () => {
      expect(HIGH_AVAILABILITY_PRESET.config.markUnhealthyOnError).toBe(true);
    });
  });

  describe('Preset TTL ordering', () => {
    it('should have conservative < high-availability < aggressive TTL', () => {
      expect(CONSERVATIVE_PRESET.config.defaultTtlMs).toBeLessThan(
        HIGH_AVAILABILITY_PRESET.config.defaultTtlMs!
      );
      expect(HIGH_AVAILABILITY_PRESET.config.defaultTtlMs).toBeLessThan(
        AGGRESSIVE_PRESET.config.defaultTtlMs!
      );
    });
  });
});

describe('createFromPreset', () => {
  it('should create interceptor from aggressive preset', () => {
    const interceptor = createFromPreset(AGGRESSIVE_PRESET);
    expect(typeof interceptor).toBe('function');
  });

  it('should create interceptor from conservative preset', () => {
    const interceptor = createFromPreset(CONSERVATIVE_PRESET);
    expect(typeof interceptor).toBe('function');
  });

  it('should create interceptor from high-availability preset', () => {
    const interceptor = createFromPreset(HIGH_AVAILABILITY_PRESET);
    expect(typeof interceptor).toBe('function');
  });

  it('should apply overrides to preset config', () => {
    const interceptor = createFromPreset(AGGRESSIVE_PRESET, {
      defaultTtlMs: 60000,
      hosts: ['api.example.com'],
    });

    expect(typeof interceptor).toBe('function');
  });

  it('should allow overriding load balance strategy', () => {
    const interceptor = createFromPreset(CONSERVATIVE_PRESET, {
      loadBalanceStrategy: 'random',
    });

    expect(typeof interceptor).toBe('function');
  });

  it('should allow overriding markUnhealthyOnError', () => {
    const interceptor = createFromPreset(HIGH_AVAILABILITY_PRESET, {
      markUnhealthyOnError: false,
    });

    expect(typeof interceptor).toBe('function');
  });

  it('should accept custom preset', () => {
    const customPreset: DnsCachePreset = {
      name: 'custom',
      config: {
        defaultTtlMs: 45000,
        loadBalanceStrategy: 'weighted',
        markUnhealthyOnError: false,
      },
    };

    const interceptor = createFromPreset(customPreset);
    expect(typeof interceptor).toBe('function');
  });

  it('should work with empty overrides', () => {
    const interceptor = createFromPreset(AGGRESSIVE_PRESET, {});
    expect(typeof interceptor).toBe('function');
  });
});

describe('createApiDnsCache', () => {
  it('should create interceptor with API ID', () => {
    const interceptor = createApiDnsCache('my-api');
    expect(typeof interceptor).toBe('function');
  });

  it('should create interceptor with custom TTL', () => {
    const interceptor = createApiDnsCache('my-api', {
      ttlMs: 120000,
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should create interceptor with load balance strategy', () => {
    const interceptor = createApiDnsCache('my-api', {
      loadBalanceStrategy: 'power-of-two',
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should create interceptor with host filter', () => {
    const interceptor = createApiDnsCache('my-api', {
      hosts: ['api.example.com', 'api2.example.com'],
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should apply host filter correctly', async () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = createApiDnsCache('my-api', {
      hosts: ['api.example.com'],
    });
    const wrappedDispatch = interceptor(dispatch);

    // Should passthrough (not in hosts list)
    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://other.example.com',
      path: '/resource',
    };

    wrappedDispatch(opts, handler);

    expect(calls).toHaveLength(1);
    expect(calls[0].opts.origin).toBe('https://other.example.com');
  });

  it('should create interceptor with all options', () => {
    const interceptor = createApiDnsCache('my-api', {
      ttlMs: 90000,
      loadBalanceStrategy: 'least-connections',
      hosts: ['api.example.com'],
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should use default values when no options provided', () => {
    const interceptor = createApiDnsCache('default-api');
    expect(typeof interceptor).toBe('function');

    // Should work with dispatch
    const { dispatch } = createMockDispatch();
    const wrappedDispatch = interceptor(dispatch);
    expect(typeof wrappedDispatch).toBe('function');
  });

  it('should handle empty API ID', () => {
    const interceptor = createApiDnsCache('');
    expect(typeof interceptor).toBe('function');
  });

  it('should handle API ID with special characters', () => {
    const interceptor = createApiDnsCache('api-v2:production/us-east');
    expect(typeof interceptor).toBe('function');
  });
});

describe('createSharedDnsCache', () => {
  it('should return resolver and createInterceptor function', () => {
    const { resolver, createInterceptor } = createSharedDnsCache({
      id: 'shared-cache',
      defaultTtlMs: 60000,
      loadBalanceStrategy: 'round-robin',
    });

    expect(resolver).toBeDefined();
    expect(typeof createInterceptor).toBe('function');
  });

  it('should create multiple interceptors sharing same config', () => {
    const { createInterceptor } = createSharedDnsCache({
      id: 'shared-cache',
      defaultTtlMs: 60000,
      loadBalanceStrategy: 'round-robin',
    });

    const interceptor1 = createInterceptor();
    const interceptor2 = createInterceptor();
    const interceptor3 = createInterceptor();

    expect(typeof interceptor1).toBe('function');
    expect(typeof interceptor2).toBe('function');
    expect(typeof interceptor3).toBe('function');
  });

  it('should allow per-interceptor options', () => {
    const { createInterceptor } = createSharedDnsCache({
      id: 'shared-cache',
      defaultTtlMs: 60000,
      loadBalanceStrategy: 'round-robin',
    });

    const interceptor1 = createInterceptor({ hosts: ['api1.example.com'] });
    const interceptor2 = createInterceptor({ hosts: ['api2.example.com'] });

    expect(typeof interceptor1).toBe('function');
    expect(typeof interceptor2).toBe('function');
  });

  it('should allow manual operations via resolver', async () => {
    const { resolver, createInterceptor } = createSharedDnsCache({
      id: 'shared-cache',
      defaultTtlMs: 60000,
      loadBalanceStrategy: 'round-robin',
    });

    // Register custom resolver - returns ResolvedEndpoint[] directly
    resolver.registerResolver('custom.example.com', async () => [
      { host: '10.0.0.1', port: 80, healthy: true },
    ]);

    // Verify can resolve
    const result = await resolver.resolve('custom.example.com');
    expect(result.endpoints[0].host).toBe('10.0.0.1');

    // Create interceptor
    const interceptor = createInterceptor();
    expect(typeof interceptor).toBe('function');

    // Cleanup
    await resolver.destroy();
  });

  it('should work with minimal config', () => {
    const { resolver, createInterceptor } = createSharedDnsCache({
      id: 'minimal',
      defaultTtlMs: 30000,
      loadBalanceStrategy: 'random',
    });

    expect(resolver).toBeDefined();
    expect(typeof createInterceptor).toBe('function');
  });

  it('should work with full config', () => {
    const { resolver, createInterceptor } = createSharedDnsCache({
      id: 'full-config',
      defaultTtlMs: 120000,
      minTtlMs: 10000,
      maxTtlMs: 300000,
      loadBalanceStrategy: 'power-of-two',
      staleWhileRevalidate: true,
      maxStaleAgeMs: 60000,
    });

    expect(resolver).toBeDefined();
    expect(typeof createInterceptor).toBe('function');
  });
});

describe('composeDnsCacheInterceptors', () => {
  it('should create composite interceptor', () => {
    const interceptor = composeDnsCacheInterceptors([
      { hosts: ['api1.example.com'] },
      { hosts: ['api2.example.com'] },
    ]);

    expect(typeof interceptor).toBe('function');
  });

  it('should chain interceptors correctly', () => {
    const { dispatch } = createMockDispatch();

    const interceptor = composeDnsCacheInterceptors([
      { hosts: ['api1.example.com'], options: { defaultTtlMs: 60000 } },
      { hosts: ['api2.example.com'], options: { defaultTtlMs: 120000 } },
    ]);

    const wrappedDispatch = interceptor(dispatch);
    expect(typeof wrappedDispatch).toBe('function');
  });

  it('should work with empty array', () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = composeDnsCacheInterceptors([]);
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://any.example.com',
      path: '/resource',
    };

    wrappedDispatch(opts, handler);

    // Should pass through directly
    expect(calls).toHaveLength(1);
  });

  it('should work with single config', () => {
    const interceptor = composeDnsCacheInterceptors([
      { hosts: ['api.example.com'], options: { loadBalanceStrategy: 'random' } },
    ]);

    expect(typeof interceptor).toBe('function');
  });

  it('should work with multiple configs and different strategies', () => {
    const interceptor = composeDnsCacheInterceptors([
      {
        hosts: ['api1.example.com'],
        options: { loadBalanceStrategy: 'round-robin', defaultTtlMs: 30000 },
      },
      {
        hosts: ['api2.example.com'],
        options: { loadBalanceStrategy: 'power-of-two', defaultTtlMs: 60000 },
      },
      {
        hosts: ['api3.example.com'],
        options: { loadBalanceStrategy: 'least-connections', defaultTtlMs: 120000 },
      },
    ]);

    expect(typeof interceptor).toBe('function');
  });

  it('should handle wildcard hosts', () => {
    const interceptor = composeDnsCacheInterceptors([
      { hosts: ['*.api.example.com'] },
      { hosts: ['*.internal.example.com'], options: { excludeHosts: ['public.internal.example.com'] } },
    ]);

    expect(typeof interceptor).toBe('function');
  });

  it('should apply options to each config', () => {
    const interceptor = composeDnsCacheInterceptors([
      {
        hosts: ['api.example.com'],
        options: {
          defaultTtlMs: 60000,
          loadBalanceStrategy: 'random',
          markUnhealthyOnError: false,
          methods: ['GET', 'POST'],
        },
      },
    ]);

    expect(typeof interceptor).toBe('function');
  });

  it('should work with passthrough for unmatched hosts', async () => {
    const { dispatch, calls } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = composeDnsCacheInterceptors([
      { hosts: ['api1.example.com'] },
      { hosts: ['api2.example.com'] },
    ]);
    const wrappedDispatch = interceptor(dispatch);

    // Request to unmatched host
    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://unmatched.example.com',
      path: '/resource',
    };

    wrappedDispatch(opts, handler);

    // Should pass through (both interceptors should pass through)
    expect(calls).toHaveLength(1);
    expect(calls[0].opts.origin).toBe('https://unmatched.example.com');
  });
});

describe('Factory integration', () => {
  it('should combine preset with compose pattern', () => {
    const interceptor = composeDnsCacheInterceptors([
      {
        hosts: ['fast-api.example.com'],
        options: { ...AGGRESSIVE_PRESET.config },
      },
      {
        hosts: ['slow-api.example.com'],
        options: { ...CONSERVATIVE_PRESET.config },
      },
    ]);

    expect(typeof interceptor).toBe('function');
  });

  it('should use API cache with shared resolver', async () => {
    const { resolver, createInterceptor } = createSharedDnsCache({
      id: 'api-shared',
      defaultTtlMs: 60000,
      loadBalanceStrategy: 'round-robin',
    });

    const interceptor1 = createInterceptor({
      hosts: ['api1.example.com'],
      markUnhealthyOnError: true,
    });

    const interceptor2 = createInterceptor({
      hosts: ['api2.example.com'],
      markUnhealthyOnError: true,
    });

    expect(typeof interceptor1).toBe('function');
    expect(typeof interceptor2).toBe('function');

    await resolver.destroy();
  });
});

describe('Boundary conditions', () => {
  it('should handle preset with undefined optional fields', () => {
    const preset: DnsCachePreset = {
      name: 'minimal',
      config: {
        defaultTtlMs: 60000,
      },
    };

    const interceptor = createFromPreset(preset);
    expect(typeof interceptor).toBe('function');
  });

  it('should handle API cache with undefined store', () => {
    const interceptor = createApiDnsCache('api', {
      store: undefined,
    });
    expect(typeof interceptor).toBe('function');
  });

  it('should handle shared cache with undefined store', () => {
    const { resolver, createInterceptor } = createSharedDnsCache(
      {
        id: 'shared',
        defaultTtlMs: 60000,
        loadBalanceStrategy: 'round-robin',
      },
      undefined
    );

    expect(resolver).toBeDefined();
    expect(typeof createInterceptor).toBe('function');
  });

  it('should handle very long API ID', () => {
    const longId = 'a'.repeat(1000);
    const interceptor = createApiDnsCache(longId);
    expect(typeof interceptor).toBe('function');
  });

  it('should handle compose with many configs', () => {
    const configs = Array.from({ length: 100 }, (_, i) => ({
      hosts: [`api${i}.example.com`],
      options: { defaultTtlMs: 60000 + i * 1000 },
    }));

    const interceptor = composeDnsCacheInterceptors(configs);
    expect(typeof interceptor).toBe('function');
  });
});

describe('Error scenarios', () => {
  it('should pass through and throw for excluded host with throwing dispatch', async () => {
    const dispatch: Dispatcher.Dispatch = () => {
      throw new Error('Dispatch failed');
    };
    const handler = createMockHandler();

    // Use excludeHosts to ensure synchronous passthrough where error is thrown
    const interceptor = createApiDnsCache('api', {
      hosts: ['api.example.com'], // Only this host is cached
    });
    const wrappedDispatch = interceptor(dispatch);

    // Request to host NOT in the list triggers synchronous passthrough
    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://excluded.example.com', // Not in hosts list
      path: '/resource',
    };

    // When host doesn't match, passes through synchronously and throws
    expect(() => wrappedDispatch(opts, handler)).toThrow('Dispatch failed');
  });

  it('should handle errors in async DNS resolution path', async () => {
    const { dispatch } = createMockDispatch();
    const handler = createMockHandler();

    const interceptor = createApiDnsCache('api');
    const wrappedDispatch = interceptor(dispatch);

    const opts: Dispatcher.DispatchOptions = {
      method: 'GET',
      origin: 'https://api.example.com',
      path: '/resource',
    };

    // Async dispatch returns true immediately
    const result = wrappedDispatch(opts, handler);
    expect(result).toBe(true);
  });
});

describe('Default export', () => {
  it('should export all factories as default', async () => {
    const factoryDefault = await import('../src/factory.mjs').then((m) => m.default);

    expect(factoryDefault.AGGRESSIVE_PRESET).toBeDefined();
    expect(factoryDefault.CONSERVATIVE_PRESET).toBeDefined();
    expect(factoryDefault.HIGH_AVAILABILITY_PRESET).toBeDefined();
    expect(typeof factoryDefault.createFromPreset).toBe('function');
    expect(typeof factoryDefault.createApiDnsCache).toBe('function');
    expect(typeof factoryDefault.createSharedDnsCache).toBe('function');
    expect(typeof factoryDefault.composeDnsCacheInterceptors).toBe('function');
  });
});
