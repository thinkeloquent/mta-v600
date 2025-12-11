/**
 * Comprehensive tests for confluence.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All 4 branches in getApiKey
 * - Boundary value testing: Edge cases
 * - Log verification: Console spy checks
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { ConfluenceApiToken } from '../src/api_token/confluence.mjs';

function setupConsoleSpy() {
  return {
    debug: jest.spyOn(console, 'debug').mockImplementation(() => {}),
    warn: jest.spyOn(console, 'warn').mockImplementation(() => {}),
    error: jest.spyOn(console, 'error').mockImplementation(() => {}),
  };
}

function restoreConsoleSpy(spies) {
  Object.values(spies).forEach((spy) => spy.mockRestore());
}

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

describe('ConfluenceApiToken', () => {
  let consoleSpy;
  let originalEnv;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    originalEnv = { ...process.env };
    // Clear all Confluence and Jira-related env vars (Jira is fallback for Confluence)
    delete process.env.CONFLUENCE_EMAIL;
    delete process.env.CONFLUENCE_API_TOKEN;
    delete process.env.CONFLUENCE_BASE_URL;
    delete process.env.JIRA_EMAIL;
    delete process.env.JIRA_API_TOKEN;
    delete process.env.JIRA_BASE_URL;
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    process.env = originalEnv;
  });

  describe('Provider Properties', () => {
    it('should return correct provider name', () => {
      const token = new ConfluenceApiToken();
      expect(token.providerName).toBe('confluence');
    });

    it('should return correct health endpoint', () => {
      // Note: base_url already includes /wiki, so health endpoint is just /rest/api/user/current
      const token = new ConfluenceApiToken();
      expect(token.healthEndpoint).toBe('/rest/api/user/current');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning /rest/api/user/current')
      );
    });
  });

  describe('_getEmail - Decision Coverage', () => {
    it('should return email from default env var', () => {
      const token = new ConfluenceApiToken();
      process.env.CONFLUENCE_EMAIL = 'test@example.com';

      const email = token._getEmail();

      expect(email).toBe('test@example.com');
    });

    it('should return email from configured env var', () => {
      const mockStore = createMockStore({ confluence: { env_email: 'CUSTOM_CONFLUENCE_EMAIL' } });
      const token = new ConfluenceApiToken(mockStore);
      process.env.CUSTOM_CONFLUENCE_EMAIL = 'custom@example.com';

      const email = token._getEmail();

      expect(email).toBe('custom@example.com');
    });

    it('should return null when env var not set', () => {
      const token = new ConfluenceApiToken();

      const email = token._getEmail();

      expect(email).toBeNull();
    });

    it('should mask short email in log', () => {
      const token = new ConfluenceApiToken();
      process.env.CONFLUENCE_EMAIL = 'ab';

      token._getEmail();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('***@***')
      );
    });

    it('should mask long email in log', () => {
      const token = new ConfluenceApiToken();
      process.env.CONFLUENCE_EMAIL = 'longemail@example.com';

      token._getEmail();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('lon***@***')
      );
    });
  });

  describe('_encodeAuth', () => {
    it('should encode credentials with Basic auth for basic_email_token type', () => {
      const token = new ConfluenceApiToken();
      const encoded = token._encodeAuth('user@test.com', 'api-token', 'basic_email_token');

      const expected = 'Basic ' + Buffer.from('user@test.com:api-token').toString('base64');
      expect(encoded).toBe(expected);
    });

    it('should encode credentials with Bearer auth for bearer_email_token type', () => {
      const token = new ConfluenceApiToken();
      const encoded = token._encodeAuth('user@test.com', 'api-token', 'bearer_email_token');

      // Bearer with base64-encoded credentials
      const expected = 'Bearer ' + Buffer.from('user@test.com:api-token').toString('base64');
      expect(encoded).toBe(expected);
    });

    it('should throw when email is null', () => {
      const token = new ConfluenceApiToken();

      expect(() => token._encodeAuth(null, 'token', 'basic_email_token')).toThrow(
        'Both email and token are required for auth encoding'
      );
    });

    it('should throw when token is null', () => {
      const token = new ConfluenceApiToken();

      expect(() => token._encodeAuth('email@test.com', null, 'basic_email_token')).toThrow(
        'Both email and token are required for auth encoding'
      );
    });

    it('should log encoded length', () => {
      const token = new ConfluenceApiToken();
      token._encodeAuth('user@test.com', 'token', 'basic_email_token');

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('length=')
      );
    });
  });

  describe('getApiKey - 4-Branch Coverage', () => {
    it('Branch 1: Both email and token present - should return encoded auth', () => {
      const mockStore = createMockStore({
        confluence: {
          env_api_key: 'CONFLUENCE_API_TOKEN',
          env_email: 'CONFLUENCE_EMAIL',
          api_auth_type: 'basic_email_token'
        }
      });
      const token = new ConfluenceApiToken(mockStore);
      process.env.CONFLUENCE_EMAIL = 'user@test.com';
      process.env.CONFLUENCE_API_TOKEN = 'api-token-123';

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(true);
      expect(result.authType).toBe('basic_email_token');
      expect(result.headerName).toBe('Authorization');
      expect(result.username).toBe('user@test.com');
      expect(result.apiKey).toContain('Basic ');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Both email and token found')
      );
    });

    it('Branch 2: Token present, email missing - should return null apiKey', () => {
      const mockStore = createMockStore({ confluence: { env_api_key: 'CONFLUENCE_API_TOKEN' } });
      const token = new ConfluenceApiToken(mockStore);
      process.env.CONFLUENCE_API_TOKEN = 'api-token-123';

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('API token found but email is missing')
      );
    });

    it('Branch 3: Email present, token missing - should return null apiKey', () => {
      const token = new ConfluenceApiToken();
      process.env.CONFLUENCE_EMAIL = 'user@test.com';

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(result.username).toBe('user@test.com');
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('Email found but API token is missing')
      );
    });

    it('Branch 4: Neither email nor token - should return null apiKey', () => {
      const token = new ConfluenceApiToken();

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(result.username).toBeNull();
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('Neither email nor token found')
      );
    });
  });

  describe('getApiKey - Error Handling', () => {
    it('should handle encoding error gracefully', () => {
      const mockStore = createMockStore({
        confluence: {
          env_api_key: 'CONFLUENCE_API_TOKEN',
          env_email: 'CONFLUENCE_EMAIL'
        }
      });
      const token = new ConfluenceApiToken(mockStore);
      process.env.CONFLUENCE_EMAIL = 'user@test.com';
      process.env.CONFLUENCE_API_TOKEN = 'token';

      // Mock _encodeAuth to throw
      const originalEncode = token._encodeAuth.bind(token);
      token._encodeAuth = () => { throw new Error('Encoding failed'); };

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining('Failed to encode credentials')
      );

      token._encodeAuth = originalEncode;
    });
  });

  describe('getBaseUrl - Decision Coverage', () => {
    it('should return base URL from config', () => {
      const mockStore = createMockStore({ confluence: { base_url: 'https://wiki.company.com' } });
      const token = new ConfluenceApiToken(mockStore);

      const url = token.getBaseUrl();

      expect(url).toBe('https://wiki.company.com');
    });

    it('should fall back to CONFLUENCE_BASE_URL env var', () => {
      const token = new ConfluenceApiToken();
      process.env.CONFLUENCE_BASE_URL = 'https://confluence-env.company.com';

      const url = token.getBaseUrl();

      expect(url).toBe('https://confluence-env.company.com');
    });

    it('should return null when no base URL configured', () => {
      const token = new ConfluenceApiToken();

      const url = token.getBaseUrl();

      expect(url).toBeNull();
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('No base URL configured')
      );
    });
  });
});
