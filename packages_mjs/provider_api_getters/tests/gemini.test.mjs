/**
 * Comprehensive tests for gemini_openai.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All if/else paths
 * - Log verification: Console spy checks
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { GeminiOpenAIApiToken } from '../src/api_token/gemini_openai.mjs';

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

describe('GeminiOpenAIApiToken', () => {
  let consoleSpy;
  let originalEnv;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    originalEnv = { ...process.env };
    delete process.env.GEMINI_API_KEY;
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    process.env = originalEnv;
  });

  describe('Provider Properties', () => {
    it('should return correct provider name', () => {
      const token = new GeminiOpenAIApiToken();
      expect(token.providerName).toBe('gemini');
    });

    it('should return correct health endpoint', () => {
      const token = new GeminiOpenAIApiToken();
      expect(token.healthEndpoint).toBe('models');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning models')
      );
    });
  });

  describe('getApiKey - Decision Coverage', () => {
    it('should return API key when env var is set', () => {
      const mockStore = createMockStore({ gemini: { env_api_key: 'GEMINI_API_KEY' } });
      const token = new GeminiOpenAIApiToken(mockStore);
      process.env.GEMINI_API_KEY = 'gemini-test-key-12345';

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(true);
      expect(result.apiKey).toBe('gemini-test-key-12345');
      expect(result.authType).toBe('bearer');
      expect(result.headerName).toBe('Authorization');
    });

    it('should return no credentials when env var not set', () => {
      const mockStore = createMockStore({ gemini: { env_api_key: 'GEMINI_API_KEY' } });
      const token = new GeminiOpenAIApiToken(mockStore);

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('No API key found')
      );
    });

    it('should return no credentials when no config store', () => {
      const token = new GeminiOpenAIApiToken();

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
    });
  });

  describe('getApiKey - Auth Type', () => {
    it('should use bearer auth type', () => {
      const mockStore = createMockStore({ gemini: { env_api_key: 'GEMINI_API_KEY' } });
      const token = new GeminiOpenAIApiToken(mockStore);
      process.env.GEMINI_API_KEY = 'test-key';

      const result = token.getApiKey();

      expect(result.authType).toBe('bearer');
      expect(result.headerName).toBe('Authorization');
    });
  });

  describe('Log Verification', () => {
    it('should log start of API key resolution', () => {
      const token = new GeminiOpenAIApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Starting API key resolution')
      );
    });

    it('should log masked key when found', () => {
      const mockStore = createMockStore({ gemini: { env_api_key: 'GEMINI_API_KEY' } });
      const token = new GeminiOpenAIApiToken(mockStore);
      process.env.GEMINI_API_KEY = 'gemini-long-key-value';

      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('length=')
      );
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('masked=')
      );
    });

    it('should log warning message when key not found', () => {
      const mockStore = createMockStore({ gemini: { env_api_key: 'GEMINI_API_KEY' } });
      const token = new GeminiOpenAIApiToken(mockStore);

      token.getApiKey();

      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('GEMINI_API_KEY')
      );
    });
  });
});
