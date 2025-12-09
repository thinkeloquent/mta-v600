/**
 * Comprehensive tests for figma.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All if/else paths
 * - Boundary value testing: Edge cases
 * - Log verification: Console spy checks
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { FigmaApiToken } from '../src/api_token/figma.mjs';

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

describe('FigmaApiToken', () => {
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

  describe('Provider Properties', () => {
    it('should return correct provider name', () => {
      const token = new FigmaApiToken();
      expect(token.providerName).toBe('figma');
    });

    it('should return correct health endpoint', () => {
      // Note: base_url already includes /v1, so health endpoint is just /me
      const token = new FigmaApiToken();
      expect(token.healthEndpoint).toBe('/me');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning /me')
      );
    });
  });

  describe('getApiKey - Decision Coverage', () => {
    it('should return API key when env var is set via config', () => {
      // Note: Figma uses auth_type='custom' because it uses the non-standard X-Figma-Token header
      const mockStore = createMockStore({ figma: { env_api_key: 'FIGMA_TOKEN' } });
      const token = new FigmaApiToken(mockStore);
      process.env.FIGMA_TOKEN = 'figma-test-token-12345';

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(true);
      expect(result.apiKey).toBe('figma-test-token-12345');
      expect(result.authType).toBe('custom');
      expect(result.headerName).toBe('X-Figma-Token');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Found API key')
      );
    });

    it('should return no credentials when env var not set', () => {
      const mockStore = createMockStore({ figma: { env_api_key: 'FIGMA_TOKEN' } });
      const token = new FigmaApiToken(mockStore);
      delete process.env.FIGMA_TOKEN;

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(result.authType).toBe('custom');
      expect(result.headerName).toBe('X-Figma-Token');
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('No API key found')
      );
    });

    it('should return no credentials when no config store', () => {
      const token = new FigmaApiToken();

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
    });
  });

  describe('Log Verification', () => {
    it('should log start of API key resolution', () => {
      const token = new FigmaApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Starting API key resolution')
      );
    });

    it('should log masked key when found', () => {
      const mockStore = createMockStore({ figma: { env_api_key: 'FIGMA_TOKEN' } });
      const token = new FigmaApiToken(mockStore);
      process.env.FIGMA_TOKEN = 'figma-long-token-value';

      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('length=')
      );
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('masked=')
      );
    });

    it('should log hasCredentials in result', () => {
      const token = new FigmaApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('hasCredentials=')
      );
    });
  });
});
