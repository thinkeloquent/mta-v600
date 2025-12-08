/**
 * Comprehensive tests for base.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All if/else paths
 * - Boundary value testing: Edge cases
 * - State transition testing: Config caching
 * - Log verification: Console spy checks
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  maskSensitive,
  ApiKeyResult,
  BaseApiToken,
} from '../src/api_token/base.mjs';

// Helper to capture console output
function setupConsoleSpy() {
  const spies = {
    debug: jest.spyOn(console, 'debug').mockImplementation(() => {}),
    info: jest.spyOn(console, 'info').mockImplementation(() => {}),
    warn: jest.spyOn(console, 'warn').mockImplementation(() => {}),
    error: jest.spyOn(console, 'error').mockImplementation(() => {}),
  };
  return spies;
}

function restoreConsoleSpy(spies) {
  Object.values(spies).forEach((spy) => spy.mockRestore());
}

/**
 * Create a mock config store that implements getNested.
 * @param {Object} providers - Provider configs
 * @returns {Object}
 */
function createMockStore(providers = {}) {
  return {
    providers,
    getNested: function(...keys) {
      let value = this;
      for (const key of keys) {
        if (value === null || value === undefined) return null;
        value = value[key];
      }
      return value ?? null;
    }
  };
}

// Concrete implementation for testing abstract base class
class TestApiToken extends BaseApiToken {
  get providerName() {
    return 'test';
  }

  getApiKey() {
    return new ApiKeyResult({ apiKey: 'test-key' });
  }
}

describe('maskSensitive', () => {
  describe('Decision/Branch Coverage', () => {
    it('should return <None> for null input', () => {
      expect(maskSensitive(null)).toBe('<None>');
    });

    it('should return <None> for undefined input', () => {
      expect(maskSensitive(undefined)).toBe('<None>');
    });

    it('should return <invalid-type> for non-string input', () => {
      expect(maskSensitive(123)).toBe('<invalid-type>');
      expect(maskSensitive({})).toBe('<invalid-type>');
      expect(maskSensitive([])).toBe('<invalid-type>');
    });

    it('should mask entirely for strings shorter than visibleChars', () => {
      expect(maskSensitive('abc', 4)).toBe('***');
    });

    it('should mask entirely for strings equal to visibleChars', () => {
      expect(maskSensitive('abcd', 4)).toBe('****');
    });

    it('should show visible chars and mask rest for longer strings', () => {
      expect(maskSensitive('secret123', 4)).toBe('secr*****');
    });
  });

  describe('Boundary Value Testing', () => {
    it('should handle empty string', () => {
      expect(maskSensitive('')).toBe('');
    });

    it('should handle single character', () => {
      expect(maskSensitive('x', 4)).toBe('*');
    });

    it('should handle custom visibleChars of 0', () => {
      expect(maskSensitive('secret', 0)).toBe('******');
    });

    it('should handle visibleChars equal to string length', () => {
      expect(maskSensitive('test', 4)).toBe('****');
    });

    it('should handle very long strings', () => {
      const longString = 'a'.repeat(1000);
      const result = maskSensitive(longString, 4);
      expect(result).toBe('aaaa' + '*'.repeat(996));
    });
  });
});

describe('ApiKeyResult', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Constructor and Defaults', () => {
    it('should create with minimal options', () => {
      const result = new ApiKeyResult({});
      expect(result.apiKey).toBeNull();
      expect(result.authType).toBe('bearer');
      expect(result.headerName).toBe('Authorization');
      expect(result.client).toBeNull();
      expect(result.username).toBeNull();
      expect(result.isPlaceholder).toBe(false);
      expect(result.placeholderMessage).toBeNull();
    });

    it('should use provided values', () => {
      const result = new ApiKeyResult({
        apiKey: 'my-key',
        authType: 'basic',
        headerName: 'X-Custom',
        client: { mock: true },
        username: 'user@test.com',
        isPlaceholder: true,
        placeholderMessage: 'Not implemented',
      });
      expect(result.apiKey).toBe('my-key');
      expect(result.authType).toBe('basic');
      expect(result.headerName).toBe('X-Custom');
      expect(result.client).toEqual({ mock: true });
      expect(result.username).toBe('user@test.com');
      expect(result.isPlaceholder).toBe(true);
      expect(result.placeholderMessage).toBe('Not implemented');
    });

    it('should default empty headerName to Authorization', () => {
      const result = new ApiKeyResult({ headerName: '' });
      expect(result.headerName).toBe('Authorization');
    });

    it('should log debug message on construction', () => {
      new ApiKeyResult({ apiKey: 'test' });
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('ApiKeyResult.constructor: Initializing result')
      );
    });
  });

  describe('hasCredentials Property', () => {
    it('should return true when apiKey is set', () => {
      const result = new ApiKeyResult({ apiKey: 'key' });
      expect(result.hasCredentials).toBe(true);
    });

    it('should return true when client is set', () => {
      const result = new ApiKeyResult({ client: {} });
      expect(result.hasCredentials).toBe(true);
    });

    it('should return false when neither apiKey nor client is set', () => {
      const result = new ApiKeyResult({});
      expect(result.hasCredentials).toBe(false);
    });

    it('should log debug message when checked', () => {
      const result = new ApiKeyResult({ apiKey: 'key' });
      const _ = result.hasCredentials;
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('hasCredentials')
      );
    });
  });

  describe('toDict Method', () => {
    it('should return dictionary with all fields', () => {
      const result = new ApiKeyResult({
        apiKey: 'secret',
        authType: 'bearer',
        username: 'user',
      });
      const dict = result.toDict();

      expect(dict).toHaveProperty('authType', 'bearer');
      expect(dict).toHaveProperty('headerName', 'Authorization');
      expect(dict).toHaveProperty('hasApiKey', true);
      expect(dict).toHaveProperty('hasUsername', true);
      expect(dict).toHaveProperty('hasClient', false);
      expect(dict).toHaveProperty('isPlaceholder', false);
    });

    it('should include masked apiKey when includeSensitive is true', () => {
      const result = new ApiKeyResult({ apiKey: 'secretkey123' });
      const dict = result.toDict(true);
      expect(dict.apiKeyMasked).toBe('secr********');
    });

    it('should not include apiKeyMasked when includeSensitive is false', () => {
      const result = new ApiKeyResult({ apiKey: 'secretkey123' });
      const dict = result.toDict(false);
      expect(dict.apiKeyMasked).toBeUndefined();
    });

    it('should include username when includeSensitive is true', () => {
      const result = new ApiKeyResult({ username: 'testuser' });
      const dict = result.toDict(true);
      expect(dict.username).toBe('testuser');
    });

    it('should log debug message on toDict', () => {
      const result = new ApiKeyResult({});
      result.toDict();
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('toDict')
      );
    });
  });

});
// Note: getAuthHeader is not implemented in the JavaScript version

describe('BaseApiToken', () => {
  let consoleSpy;
  let originalEnv;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    originalEnv = { ...process.env };
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    process.env = originalEnv;
  });

  describe('Constructor', () => {
    it('should initialize without config store', () => {
      const token = new TestApiToken();
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Initializing with')
      );
    });

    it('should initialize with config store', () => {
      const mockStore = createMockStore({ test: {} });
      const token = new TestApiToken(mockStore);
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Initializing with')
      );
    });
  });

  describe('_getProviderConfig', () => {
    it('should return empty object when no config store', () => {
      const token = new TestApiToken();
      expect(token._getProviderConfig()).toEqual({});
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('No configStore available')
      );
    });

    it('should return empty object when provider not in config', () => {
      const mockStore = createMockStore({});
      const token = new TestApiToken(mockStore);
      expect(token._getProviderConfig()).toEqual({});
    });

    it('should return config when provider exists', () => {
      const mockStore = createMockStore({ test: { base_url: 'http://test.com' } });
      const token = new TestApiToken(mockStore);
      expect(token._getProviderConfig()).toEqual({ base_url: 'http://test.com' });
    });

    it('should cache config after first call', () => {
      const mockStore = createMockStore({ test: { key: 'value' } });
      const token = new TestApiToken(mockStore);

      // First call
      token._getProviderConfig();

      // Second call should use cache
      token._getProviderConfig();
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning cached config')
      );
    });
  });

  describe('_getEnvApiKeyName', () => {
    it('should return null when no config', () => {
      const token = new TestApiToken();
      expect(token._getEnvApiKeyName()).toBeNull();
    });

    it('should return env_api_key from config', () => {
      const mockStore = createMockStore({ test: { env_api_key: 'CUSTOM_KEY' } });
      const token = new TestApiToken(mockStore);
      expect(token._getEnvApiKeyName()).toBe('CUSTOM_KEY');
    });
  });

  describe('_lookupEnvApiKey', () => {
    it('should return null when no env key name configured', () => {
      const token = new TestApiToken();
      expect(token._lookupEnvApiKey()).toBeNull();
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('No env_api_key configured')
      );
    });

    it('should return null when env var not set', () => {
      const mockStore = createMockStore({ test: { env_api_key: 'TEST_API_KEY' } });
      const token = new TestApiToken(mockStore);
      delete process.env.TEST_API_KEY;
      expect(token._lookupEnvApiKey()).toBeNull();
    });

    it('should return value when env var is set', () => {
      const mockStore = createMockStore({ test: { env_api_key: 'TEST_API_KEY' } });
      const token = new TestApiToken(mockStore);
      process.env.TEST_API_KEY = 'my-secret-api-key';
      expect(token._lookupEnvApiKey()).toBe('my-secret-api-key');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining("Found API key in env var 'TEST_API_KEY'")
      );
    });
  });

  describe('getBaseUrl', () => {
    it('should return null when no config', () => {
      const token = new TestApiToken();
      expect(token.getBaseUrl()).toBeNull();
    });

    it('should return base_url from config', () => {
      const mockStore = createMockStore({ test: { base_url: 'https://api.test.com' } });
      const token = new TestApiToken(mockStore);
      expect(token.getBaseUrl()).toBe('https://api.test.com');
    });
  });

  describe('healthEndpoint', () => {
    it('should return default endpoint from config when not overridden', () => {
      // Use TestApiToken which doesn't override healthEndpoint
      // The base class returns health_endpoint from config or '/'
      const token = new TestApiToken();
      // Base implementation returns '/' if no config
      expect(token.healthEndpoint).toBe('/');
    });
  });

  describe('getApiKeyForRequest', () => {
    it('should delegate to getApiKey by default', () => {
      const token = new TestApiToken();
      const result = token.getApiKeyForRequest({});
      expect(result.apiKey).toBe('test-key');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('getApiKeyForRequest')
      );
    });
  });
});
