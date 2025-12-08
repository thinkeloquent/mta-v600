/**
 * Comprehensive tests for github.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All if/else paths including fallback logic
 * - Boundary value testing: Edge cases
 * - Log verification: Console spy checks
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { GithubApiToken, GITHUB_FALLBACK_ENV_VARS } from '../src/api_token/github.mjs';

function setupConsoleSpy() {
  return {
    debug: jest.spyOn(console, 'debug').mockImplementation(() => {}),
    warn: jest.spyOn(console, 'warn').mockImplementation(() => {}),
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

describe('GithubApiToken', () => {
  let consoleSpy;
  let originalEnv;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    originalEnv = { ...process.env };
    // Clear all GitHub-related env vars
    GITHUB_FALLBACK_ENV_VARS.forEach((v) => delete process.env[v]);
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    process.env = originalEnv;
  });

  describe('Provider Properties', () => {
    it('should return correct provider name', () => {
      const token = new GithubApiToken();
      expect(token.providerName).toBe('github');
    });

    it('should return correct health endpoint', () => {
      const token = new GithubApiToken();
      expect(token.healthEndpoint).toBe('/user');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning /user')
      );
    });
  });

  describe('Fallback Env Vars', () => {
    it('should export correct fallback env vars', () => {
      expect(GITHUB_FALLBACK_ENV_VARS).toEqual([
        'GITHUB_TOKEN',
        'GH_TOKEN',
        'GITHUB_ACCESS_TOKEN',
        'GITHUB_PAT',
      ]);
    });
  });

  describe('_lookupWithFallbacks - Decision Coverage', () => {
    it('should return configured env var first when set', () => {
      const mockStore = createMockStore({ github: { env_api_key: 'MY_GITHUB_KEY' } });
      const token = new GithubApiToken(mockStore);
      process.env.MY_GITHUB_KEY = 'configured-key';
      process.env.GITHUB_TOKEN = 'fallback-key';

      const result = token.getApiKey();

      expect(result.apiKey).toBe('configured-key');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining("Found key in configured env var 'MY_GITHUB_KEY'")
      );
    });

    it('should fall back to GITHUB_TOKEN when configured not set', () => {
      const mockStore = createMockStore({ github: { env_api_key: 'MY_GITHUB_KEY' } });
      const token = new GithubApiToken(mockStore);
      delete process.env.MY_GITHUB_KEY;
      process.env.GITHUB_TOKEN = 'github-token-value';

      const result = token.getApiKey();

      expect(result.apiKey).toBe('github-token-value');
    });

    it('should fall back to GH_TOKEN when GITHUB_TOKEN not set', () => {
      const token = new GithubApiToken();
      process.env.GH_TOKEN = 'gh-token-value';

      const result = token.getApiKey();

      expect(result.apiKey).toBe('gh-token-value');
    });

    it('should fall back to GITHUB_ACCESS_TOKEN when prior vars not set', () => {
      const token = new GithubApiToken();
      process.env.GITHUB_ACCESS_TOKEN = 'access-token-value';

      const result = token.getApiKey();

      expect(result.apiKey).toBe('access-token-value');
    });

    it('should fall back to GITHUB_PAT when all prior vars not set', () => {
      const token = new GithubApiToken();
      process.env.GITHUB_PAT = 'pat-value';

      const result = token.getApiKey();

      expect(result.apiKey).toBe('pat-value');
    });

    it('should return null when no env vars set', () => {
      const token = new GithubApiToken();

      const result = token.getApiKey();

      expect(result.apiKey).toBeNull();
      expect(result.hasCredentials).toBe(false);
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('No API key found')
      );
    });
  });

  describe('getApiKey - Result Format', () => {
    it('should return bearer auth type', () => {
      const token = new GithubApiToken();
      process.env.GITHUB_TOKEN = 'test-token';

      const result = token.getApiKey();

      expect(result.authType).toBe('bearer');
      expect(result.headerName).toBe('Authorization');
    });
  });

  describe('Log Verification', () => {
    it('should log fallback iteration', () => {
      const token = new GithubApiToken();
      token.getApiKey();

      // Should log checking each fallback
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Checking fallback')
      );
    });

    it('should log number of fallback vars being checked', () => {
      const token = new GithubApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('4 fallback env vars')
      );
    });

    it('should log when env var is not set', () => {
      const token = new GithubApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('is not set')
      );
    });
  });
});
