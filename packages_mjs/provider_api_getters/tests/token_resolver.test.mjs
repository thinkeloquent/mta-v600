/**
 * Comprehensive tests for token_resolver/registry.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All if/else paths
 * - Boundary value testing: Edge cases for inputs
 * - State transition testing: Registry state changes
 * - Log verification: Console spy checks for every branch
 * - Loop testing: 0, 1, and multiple iterations
 * - Error handling: All catch blocks
 *
 * Test Structure follows Defensive Programming:
 * - Every branch must have a corresponding test
 * - Every log statement must be verified
 * - Fail fast validation must be tested
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  TokenResolverRegistry,
  tokenRegistry,
  setAPIToken,
  clearAPIToken,
} from '../src/token_resolver/registry.mjs';
import { RequestContext } from '../src/api_token/base.mjs';

// ========== Test Utilities ==========

/**
 * Setup console spy for log verification.
 * @returns {Object} Spies object with debug, info, warn, error methods
 */
function setupConsoleSpy() {
  const spies = {
    debug: jest.spyOn(console, 'debug').mockImplementation(() => {}),
    info: jest.spyOn(console, 'info').mockImplementation(() => {}),
    warn: jest.spyOn(console, 'warn').mockImplementation(() => {}),
    error: jest.spyOn(console, 'error').mockImplementation(() => {}),
  };
  return spies;
}

/**
 * Restore all console spies.
 * @param {Object} spies - Spies object from setupConsoleSpy
 */
function restoreConsoleSpy(spies) {
  Object.values(spies).forEach((spy) => spy.mockRestore());
}

/**
 * Assert that a specific log message was emitted.
 * @param {Object} spy - Jest spy for console method
 * @param {string} expectedText - Text that should appear in log
 */
function assertLogContains(spy, expectedText) {
  const calls = spy.mock.calls.map((call) => call[0]);
  const found = calls.some((msg) => msg.includes(expectedText));
  if (!found) {
    throw new Error(
      `Expected log containing '${expectedText}' not found.\n` +
        `Actual logs:\n${calls.join('\n')}`
    );
  }
}

/**
 * Create a mock config store for testing.
 * @param {Object} providers - Provider configurations
 * @returns {Object} Mock config store
 */
function createMockConfigStore(providers = {}) {
  return {
    providers,
    getNested: function (...keys) {
      let value = this;
      for (const key of keys) {
        if (value === null || value === undefined) return null;
        value = value[key];
      }
      return value ?? null;
    },
  };
}

// ========== Test Suite ==========

describe('TokenResolverRegistry', () => {
  let consoleSpy;
  let registry;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    registry = new TokenResolverRegistry();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    // Clear singleton registry state
    tokenRegistry.clear();
  });

  // ========== Constructor Tests ==========
  describe('Constructor', () => {
    it('should initialize registry and log debug message', () => {
      // Already created in beforeEach
      assertLogContains(
        consoleSpy.debug,
        'TokenResolverRegistry.constructor: Initializing registry'
      );
    });
  });

  // ========== Option A: setAPIToken Tests ==========
  describe('setAPIToken - Option A', () => {
    describe('Decision/Branch Coverage', () => {
      it('Branch 1: Valid providerName and token - should set token', () => {
        registry.setAPIToken('github', 'ghp_test123');

        expect(registry.hasRuntimeToken('github')).toBe(true);
        assertLogContains(
          consoleSpy.info,
          "setAPIToken: Setting runtime token for 'github'"
        );
        assertLogContains(
          consoleSpy.debug,
          "setAPIToken: Token set for 'github' (length=11)"
        );
      });

      it('Branch 2: Empty providerName - should throw and log error', () => {
        expect(() => registry.setAPIToken('', 'token')).toThrow(
          'providerName must be a non-empty string'
        );
        assertLogContains(
          consoleSpy.error,
          'setAPIToken: providerName must be a non-empty string'
        );
      });

      it('Branch 3: Null providerName - should throw and log error', () => {
        expect(() => registry.setAPIToken(null, 'token')).toThrow(
          'providerName must be a non-empty string'
        );
        assertLogContains(
          consoleSpy.error,
          'setAPIToken: providerName must be a non-empty string'
        );
      });

      it('Branch 4: Non-string providerName - should throw and log error', () => {
        expect(() => registry.setAPIToken(123, 'token')).toThrow(
          'providerName must be a non-empty string'
        );
      });

      it('Branch 5: Empty token - should throw and log error', () => {
        expect(() => registry.setAPIToken('github', '')).toThrow(
          'token must be a non-empty string'
        );
        assertLogContains(
          consoleSpy.error,
          'setAPIToken: token must be a non-empty string'
        );
      });

      it('Branch 6: Null token - should throw and log error', () => {
        expect(() => registry.setAPIToken('github', null)).toThrow(
          'token must be a non-empty string'
        );
      });

      it('Branch 7: Non-string token - should throw and log error', () => {
        expect(() => registry.setAPIToken('github', 123)).toThrow(
          'token must be a non-empty string'
        );
      });
    });

    describe('Boundary Value Testing', () => {
      it('should accept single character providerName', () => {
        registry.setAPIToken('a', 'token');
        expect(registry.hasRuntimeToken('a')).toBe(true);
      });

      it('should accept single character token', () => {
        registry.setAPIToken('github', 'x');
        expect(registry.hasRuntimeToken('github')).toBe(true);
      });

      it('should accept very long token', () => {
        const longToken = 'a'.repeat(10000);
        registry.setAPIToken('github', longToken);
        expect(registry.hasRuntimeToken('github')).toBe(true);
        assertLogContains(consoleSpy.debug, '(length=10000)');
      });

      it('should overwrite existing token', () => {
        registry.setAPIToken('github', 'token1');
        registry.setAPIToken('github', 'token2');
        expect(registry.hasRuntimeToken('github')).toBe(true);
      });
    });

    describe('State Transition Testing', () => {
      it('should transition from empty to having token', () => {
        expect(registry.hasRuntimeToken('github')).toBe(false);
        registry.setAPIToken('github', 'token');
        expect(registry.hasRuntimeToken('github')).toBe(true);
      });

      it('should maintain separate tokens for different providers', () => {
        registry.setAPIToken('github', 'gh_token');
        registry.setAPIToken('jira', 'jira_token');
        expect(registry.hasRuntimeToken('github')).toBe(true);
        expect(registry.hasRuntimeToken('jira')).toBe(true);
      });
    });
  });

  // ========== clearAPIToken Tests ==========
  describe('clearAPIToken', () => {
    describe('Decision/Branch Coverage', () => {
      it('Branch 1: Token exists - should clear and log existed=true', () => {
        registry.setAPIToken('github', 'token');
        registry.clearAPIToken('github');

        expect(registry.hasRuntimeToken('github')).toBe(false);
        assertLogContains(
          consoleSpy.info,
          "clearAPIToken: Clearing runtime token for 'github'"
        );
        assertLogContains(
          consoleSpy.debug,
          "clearAPIToken: Token existed=true for 'github'"
        );
      });

      it('Branch 2: Token does not exist - should log existed=false', () => {
        registry.clearAPIToken('nonexistent');

        assertLogContains(
          consoleSpy.debug,
          "clearAPIToken: Token existed=false for 'nonexistent'"
        );
      });
    });

    describe('State Transition Testing', () => {
      it('should transition from having token to empty', () => {
        registry.setAPIToken('github', 'token');
        expect(registry.hasRuntimeToken('github')).toBe(true);
        registry.clearAPIToken('github');
        expect(registry.hasRuntimeToken('github')).toBe(false);
      });

      it('multiple clears should be idempotent', () => {
        registry.setAPIToken('github', 'token');
        registry.clearAPIToken('github');
        registry.clearAPIToken('github');
        expect(registry.hasRuntimeToken('github')).toBe(false);
      });
    });
  });

  // ========== hasRuntimeToken Tests ==========
  describe('hasRuntimeToken', () => {
    it('should return false when no token set', () => {
      const result = registry.hasRuntimeToken('github');
      expect(result).toBe(false);
      assertLogContains(consoleSpy.debug, "hasRuntimeToken: 'github' = false");
    });

    it('should return true when token is set', () => {
      registry.setAPIToken('github', 'token');
      const result = registry.hasRuntimeToken('github');
      expect(result).toBe(true);
      assertLogContains(consoleSpy.debug, "hasRuntimeToken: 'github' = true");
    });
  });

  // ========== Option C: registerResolver Tests ==========
  describe('registerResolver - Option C', () => {
    describe('Decision/Branch Coverage', () => {
      it('Branch 1: Valid providerName and resolver - should register', () => {
        const resolver = async () => 'token';
        registry.registerResolver('github', resolver);

        expect(registry.hasResolver('github')).toBe(true);
        assertLogContains(
          consoleSpy.info,
          "registerResolver: Registering resolver for 'github'"
        );
        assertLogContains(
          consoleSpy.debug,
          "registerResolver: Resolver registered for 'github'"
        );
      });

      it('Branch 2: Empty providerName - should throw and log error', () => {
        expect(() => registry.registerResolver('', async () => 'token')).toThrow(
          'providerName must be a non-empty string'
        );
        assertLogContains(
          consoleSpy.error,
          'registerResolver: providerName must be a non-empty string'
        );
      });

      it('Branch 3: Null providerName - should throw and log error', () => {
        expect(() => registry.registerResolver(null, async () => 'token')).toThrow(
          'providerName must be a non-empty string'
        );
      });

      it('Branch 4: Non-function resolver - should throw and log error', () => {
        expect(() => registry.registerResolver('github', 'not-a-function')).toThrow(
          'resolver must be a function'
        );
        assertLogContains(
          consoleSpy.error,
          'registerResolver: resolver must be a function'
        );
      });

      it('Branch 5: Null resolver - should throw and log error', () => {
        expect(() => registry.registerResolver('github', null)).toThrow(
          'resolver must be a function'
        );
      });
    });

    describe('Function Types', () => {
      it('should accept async function', async () => {
        const resolver = async (ctx) => 'async_token';
        registry.registerResolver('github', resolver);
        expect(registry.hasResolver('github')).toBe(true);
      });

      it('should accept sync function', () => {
        const resolver = (ctx) => 'sync_token';
        registry.registerResolver('github', resolver);
        expect(registry.hasResolver('github')).toBe(true);
      });

      it('should accept arrow function', () => {
        registry.registerResolver('github', () => 'arrow_token');
        expect(registry.hasResolver('github')).toBe(true);
      });
    });
  });

  // ========== unregisterResolver Tests ==========
  describe('unregisterResolver', () => {
    describe('Decision/Branch Coverage', () => {
      it('Branch 1: Resolver exists - should unregister and log existed=true', () => {
        registry.registerResolver('github', async () => 'token');
        registry.unregisterResolver('github');

        expect(registry.hasResolver('github')).toBe(false);
        assertLogContains(
          consoleSpy.info,
          "unregisterResolver: Unregistering resolver for 'github'"
        );
        assertLogContains(
          consoleSpy.debug,
          "unregisterResolver: Resolver existed=true for 'github'"
        );
      });

      it('Branch 2: Resolver does not exist - should log existed=false', () => {
        registry.unregisterResolver('nonexistent');
        assertLogContains(
          consoleSpy.debug,
          "unregisterResolver: Resolver existed=false for 'nonexistent'"
        );
      });
    });
  });

  // ========== hasResolver Tests ==========
  describe('hasResolver', () => {
    it('should return false when no resolver or runtime token', () => {
      expect(registry.hasResolver('github')).toBe(false);
    });

    it('should return true when resolver is registered', () => {
      registry.registerResolver('github', async () => 'token');
      expect(registry.hasResolver('github')).toBe(true);
    });

    it('should return true when runtime token is set', () => {
      registry.setAPIToken('github', 'token');
      expect(registry.hasResolver('github')).toBe(true);
    });
  });

  // ========== Option B: loadResolversFromConfig Tests ==========
  describe('loadResolversFromConfig - Option B', () => {
    describe('Decision/Branch Coverage', () => {
      it('Branch 1: No configStore provided - should warn and return', async () => {
        await registry.loadResolversFromConfig(null);
        assertLogContains(
          consoleSpy.warn,
          'loadResolversFromConfig: No configStore provided'
        );
      });

      it('Branch 2: configStore.getNested throws - should log error', async () => {
        const mockStore = {
          getNested: () => {
            throw new Error('Config error');
          },
        };
        await registry.loadResolversFromConfig(mockStore);
        assertLogContains(
          consoleSpy.error,
          'loadResolversFromConfig: Failed to get providers from config'
        );
      });

      it('Branch 3: No runtime_import - should skip provider', async () => {
        const mockStore = createMockConfigStore({
          github: { base_url: 'https://api.github.com' },
        });
        await registry.loadResolversFromConfig(mockStore);
        expect(registry.hasResolver('github')).toBe(false);
      });

      it('Branch 4: Resolver already registered - should skip and log', async () => {
        registry.registerResolver('github', async () => 'existing');
        const mockStore = createMockConfigStore({
          github: { runtime_import: { fastify: './resolver.mjs' } },
        });
        await registry.loadResolversFromConfig(mockStore);
        assertLogContains(
          consoleSpy.debug,
          "loadResolversFromConfig: Skipping 'github' - resolver already registered"
        );
      });

      it('Branch 5: runtime_import is object with fastify key', async () => {
        const mockStore = createMockConfigStore({
          github: { runtime_import: { fastify: './resolver.mjs' } },
        });
        await registry.loadResolversFromConfig(mockStore);
        assertLogContains(
          consoleSpy.debug,
          "loadResolversFromConfig: Found fastify-specific import for 'github'"
        );
      });

      it('Branch 6: runtime_import is string', async () => {
        const mockStore = createMockConfigStore({
          github: { runtime_import: './resolver.mjs' },
        });
        await registry.loadResolversFromConfig(mockStore);
        assertLogContains(
          consoleSpy.debug,
          "loadResolversFromConfig: Found string import for 'github'"
        );
      });

      it('Branch 7: No importPath resolved - should skip', async () => {
        const mockStore = createMockConfigStore({
          github: { runtime_import: { fastapi: './resolver.py' } }, // No fastify key
        });
        await registry.loadResolversFromConfig(mockStore);
        assertLogContains(
          consoleSpy.debug,
          "loadResolversFromConfig: No importPath resolved for 'github'"
        );
      });
    });

    describe('Loop Testing', () => {
      it('should handle 0 providers', async () => {
        const mockStore = createMockConfigStore({});
        await registry.loadResolversFromConfig(mockStore);
        assertLogContains(
          consoleSpy.debug,
          'loadResolversFromConfig: Found 0 providers to check'
        );
      });

      it('should handle 1 provider', async () => {
        const mockStore = createMockConfigStore({
          github: { base_url: 'test' },
        });
        await registry.loadResolversFromConfig(mockStore);
        assertLogContains(
          consoleSpy.debug,
          'loadResolversFromConfig: Found 1 providers to check'
        );
      });

      it('should handle multiple providers', async () => {
        const mockStore = createMockConfigStore({
          github: { base_url: 'test1' },
          jira: { base_url: 'test2' },
          figma: { base_url: 'test3' },
        });
        await registry.loadResolversFromConfig(mockStore);
        assertLogContains(
          consoleSpy.debug,
          'loadResolversFromConfig: Found 3 providers to check'
        );
      });
    });
  });

  // ========== resolveStartupTokens Tests ==========
  describe('resolveStartupTokens', () => {
    describe('Decision/Branch Coverage', () => {
      it('Branch 1: No configStore provided - should warn and return', async () => {
        await registry.resolveStartupTokens(null);
        assertLogContains(
          consoleSpy.warn,
          'resolveStartupTokens: No configStore provided'
        );
      });

      it('Branch 2: configStore.getNested throws - should log error', async () => {
        const mockStore = {
          getNested: () => {
            throw new Error('Config error');
          },
        };
        await registry.resolveStartupTokens(mockStore);
        assertLogContains(
          consoleSpy.error,
          'resolveStartupTokens: Failed to get providers from config'
        );
      });

      it('Branch 3: token_resolver !== startup - should skip', async () => {
        const mockStore = createMockConfigStore({
          github: { token_resolver: 'static' },
        });
        await registry.resolveStartupTokens(mockStore);
        // Should not attempt to resolve for this specific provider
        // The log pattern is: "Resolving startup token for 'github'"
        expect(consoleSpy.info.mock.calls.filter(
          (c) => c[0].includes("Resolving startup token for 'github'")
        ).length).toBe(0);
      });

      it('Branch 4: No resolver for startup provider - should log debug', async () => {
        const mockStore = createMockConfigStore({
          github: { token_resolver: 'startup' },
        });
        await registry.resolveStartupTokens(mockStore);
        assertLogContains(
          consoleSpy.debug,
          "resolveStartupTokens: No resolver for startup provider 'github'"
        );
      });

      it('Branch 5: Resolver returns valid token - should cache', async () => {
        registry.registerResolver('github', async () => 'startup_token_123');
        const mockStore = createMockConfigStore({
          github: { token_resolver: 'startup' },
        });
        await registry.resolveStartupTokens(mockStore);
        assertLogContains(
          consoleSpy.info,
          "resolveStartupTokens: Startup token resolved for 'github'"
        );
      });

      it('Branch 6: Resolver returns null - should warn', async () => {
        registry.registerResolver('github', async () => null);
        const mockStore = createMockConfigStore({
          github: { token_resolver: 'startup' },
        });
        await registry.resolveStartupTokens(mockStore);
        assertLogContains(
          consoleSpy.warn,
          "resolveStartupTokens: Resolver for 'github' returned invalid token"
        );
      });

      it('Branch 7: Resolver returns non-string - should warn', async () => {
        registry.registerResolver('github', async () => 12345);
        const mockStore = createMockConfigStore({
          github: { token_resolver: 'startup' },
        });
        await registry.resolveStartupTokens(mockStore);
        assertLogContains(
          consoleSpy.warn,
          "resolveStartupTokens: Resolver for 'github' returned invalid token"
        );
      });

      it('Branch 8: Resolver throws error - should log error', async () => {
        registry.registerResolver('github', async () => {
          throw new Error('Resolver failed');
        });
        const mockStore = createMockConfigStore({
          github: { token_resolver: 'startup' },
        });
        await registry.resolveStartupTokens(mockStore);
        assertLogContains(
          consoleSpy.error,
          "resolveStartupTokens: Failed to resolve startup token for 'github'"
        );
      });
    });
  });

  // ========== getToken Tests ==========
  describe('getToken', () => {
    describe('Decision/Branch Coverage - Resolution Priority', () => {
      it('Branch 1: Runtime token override (highest priority)', async () => {
        registry.setAPIToken('github', 'runtime_token');
        registry.registerResolver('github', async () => 'resolver_token');

        const token = await registry.getToken('github', null, { token_resolver: 'request' });

        expect(token).toBe('runtime_token');
        assertLogContains(
          consoleSpy.debug,
          "getToken: Using runtime token override for 'github'"
        );
      });

      it('Branch 2: Startup token from cache', async () => {
        registry.registerResolver('github', async () => 'startup_token');
        const mockStore = createMockConfigStore({
          github: { token_resolver: 'startup' },
        });
        await registry.resolveStartupTokens(mockStore);

        const token = await registry.getToken('github', null, { token_resolver: 'startup' });

        expect(token).toBe('startup_token');
        assertLogContains(
          consoleSpy.debug,
          "getToken: Returning startup token for 'github'"
        );
      });

      it('Branch 3: Startup token not found - returns null', async () => {
        const token = await registry.getToken('github', null, { token_resolver: 'startup' });
        expect(token).toBeNull();
        assertLogContains(
          consoleSpy.debug,
          "getToken: Returning startup token for 'github' (found=false)"
        );
      });

      it('Branch 4: Request resolver called with context', async () => {
        const mockResolver = jest.fn().mockResolvedValue('request_token');
        registry.registerResolver('github', mockResolver);

        const context = new RequestContext({ tenantId: 'tenant123' });
        const token = await registry.getToken('github', context, { token_resolver: 'request' });

        expect(token).toBe('request_token');
        expect(mockResolver).toHaveBeenCalledWith(context);
        assertLogContains(
          consoleSpy.debug,
          "getToken: Calling request resolver for 'github'"
        );
        assertLogContains(
          consoleSpy.debug,
          "getToken: Request resolver returned token for 'github' (hasToken=true)"
        );
      });

      it('Branch 5: Request resolver returns null', async () => {
        registry.registerResolver('github', async () => null);

        const token = await registry.getToken('github', null, { token_resolver: 'request' });

        expect(token).toBeNull();
        assertLogContains(
          consoleSpy.debug,
          "getToken: Request resolver returned token for 'github' (hasToken=false)"
        );
      });

      it('Branch 6: Request resolver throws - should catch and return null', async () => {
        registry.registerResolver('github', async () => {
          throw new Error('Resolver exploded');
        });

        const token = await registry.getToken('github', null, { token_resolver: 'request' });

        expect(token).toBeNull();
        assertLogContains(
          consoleSpy.error,
          "getToken: Request resolver failed for 'github': Resolver exploded"
        );
      });

      it('Branch 7: Request type but no resolver - falls through', async () => {
        const token = await registry.getToken('github', null, { token_resolver: 'request' });

        expect(token).toBeNull();
        assertLogContains(
          consoleSpy.debug,
          "getToken: No token override for 'github', will fall back to env var"
        );
      });

      it('Branch 8: Static resolver type - returns null', async () => {
        registry.registerResolver('github', async () => 'should_not_be_called');

        const token = await registry.getToken('github', null, { token_resolver: 'static' });

        expect(token).toBeNull();
        assertLogContains(
          consoleSpy.debug,
          "getToken: resolverType='static' for 'github'"
        );
      });

      it('Branch 9: No config provided - defaults to static', async () => {
        const token = await registry.getToken('github', null, null);

        expect(token).toBeNull();
        assertLogContains(
          consoleSpy.debug,
          "getToken: resolverType='static' for 'github'"
        );
      });
    });

    describe('Boundary Value Testing', () => {
      it('should handle empty context object', async () => {
        registry.registerResolver('github', async (ctx) => ctx ? 'has_ctx' : 'no_ctx');
        const token = await registry.getToken('github', {}, { token_resolver: 'request' });
        expect(token).toBe('has_ctx');
      });

      it('should handle null context', async () => {
        registry.registerResolver('github', async (ctx) => ctx ? 'has_ctx' : 'no_ctx');
        const token = await registry.getToken('github', null, { token_resolver: 'request' });
        expect(token).toBe('no_ctx');
      });

      it('should handle context with all fields', async () => {
        registry.registerResolver('github', async (ctx) => `${ctx.tenantId}-${ctx.userId}`);
        const context = new RequestContext({
          tenantId: 'tenant1',
          userId: 'user1',
        });
        const token = await registry.getToken('github', context, { token_resolver: 'request' });
        expect(token).toBe('tenant1-user1');
      });
    });
  });

  // ========== Utility Methods Tests ==========
  describe('Utility Methods', () => {
    describe('getRegisteredProviders', () => {
      it('should return empty array when no providers', () => {
        expect(registry.getRegisteredProviders()).toEqual([]);
      });

      it('should include runtime token providers', () => {
        registry.setAPIToken('github', 'token');
        expect(registry.getRegisteredProviders()).toContain('github');
      });

      it('should include resolver providers', () => {
        registry.registerResolver('jira', async () => 'token');
        expect(registry.getRegisteredProviders()).toContain('jira');
      });

      it('should deduplicate providers with both token and resolver', () => {
        registry.setAPIToken('github', 'token');
        registry.registerResolver('github', async () => 'resolver');
        const providers = registry.getRegisteredProviders();
        expect(providers.filter((p) => p === 'github').length).toBe(1);
      });
    });

    describe('clear', () => {
      it('should clear all state and log', () => {
        registry.setAPIToken('github', 'token');
        registry.registerResolver('jira', async () => 'token');

        registry.clear();

        expect(registry.hasRuntimeToken('github')).toBe(false);
        expect(registry.hasResolver('jira')).toBe(false);
        assertLogContains(consoleSpy.info, 'clear: Clearing all resolvers and tokens');
      });
    });

    describe('getDebugInfo', () => {
      it('should return accurate counts', () => {
        registry.setAPIToken('github', 'token');
        registry.registerResolver('jira', async () => 'token');

        const info = registry.getDebugInfo();

        expect(info.runtimeTokenCount).toBe(1);
        expect(info.resolverCount).toBe(1);
        expect(info.startupTokenCount).toBe(0);
        expect(info.runtimeTokenProviders).toContain('github');
        expect(info.resolverProviders).toContain('jira');
      });
    });
  });

  // ========== Convenience Functions Tests ==========
  describe('Convenience Functions (Module Exports)', () => {
    describe('setAPIToken', () => {
      it('should delegate to singleton registry', () => {
        setAPIToken('github', 'token');
        expect(tokenRegistry.hasRuntimeToken('github')).toBe(true);
      });
    });

    describe('clearAPIToken', () => {
      it('should delegate to singleton registry', () => {
        tokenRegistry.setAPIToken('github', 'token');
        clearAPIToken('github');
        expect(tokenRegistry.hasRuntimeToken('github')).toBe(false);
      });
    });
  });

  // ========== Integration/E2E Tests ==========
  describe('Integration: Full Token Resolution Flow', () => {
    it('should resolve token through full priority chain', async () => {
      // 1. Start with resolver (lowest priority)
      registry.registerResolver('github', async () => 'resolver_token');

      // Resolver should work
      let token = await registry.getToken('github', null, { token_resolver: 'request' });
      expect(token).toBe('resolver_token');

      // 2. Set runtime token (higher priority)
      registry.setAPIToken('github', 'runtime_token');

      // Runtime token should override
      token = await registry.getToken('github', null, { token_resolver: 'request' });
      expect(token).toBe('runtime_token');

      // 3. Clear runtime token
      registry.clearAPIToken('github');

      // Back to resolver
      token = await registry.getToken('github', null, { token_resolver: 'request' });
      expect(token).toBe('resolver_token');
    });

    it('should handle concurrent token resolution', async () => {
      registry.registerResolver('github', async (ctx) => {
        await new Promise((resolve) => setTimeout(resolve, 10));
        return `token_${ctx?.tenantId || 'default'}`;
      });

      const promises = [
        registry.getToken('github', { tenantId: '1' }, { token_resolver: 'request' }),
        registry.getToken('github', { tenantId: '2' }, { token_resolver: 'request' }),
        registry.getToken('github', { tenantId: '3' }, { token_resolver: 'request' }),
      ];

      const results = await Promise.all(promises);
      expect(results).toEqual(['token_1', 'token_2', 'token_3']);
    });
  });
});
