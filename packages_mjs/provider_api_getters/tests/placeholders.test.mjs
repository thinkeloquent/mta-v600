/**
 * Comprehensive tests for placeholder providers (rally.mjs, elasticsearch.mjs)
 *
 * Coverage targets:
 * - Decision/Branch coverage: All if/else paths
 * - Log verification: Console spy checks
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { RallyApiToken } from '../src/api_token/rally.mjs';
import { ElasticsearchApiToken } from '../src/api_token/elasticsearch.mjs';

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

describe('RallyApiToken', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Provider Properties', () => {
    it('should return correct provider name', () => {
      const token = new RallyApiToken();
      expect(token.providerName).toBe('rally');
    });

    it('should return correct health endpoint', () => {
      const token = new RallyApiToken();
      expect(token.healthEndpoint).toBe('/');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning /')
      );
    });
  });

  describe('getApiKey - Placeholder Behavior', () => {
    it('should return placeholder result with default message', () => {
      const token = new RallyApiToken();

      const result = token.getApiKey();

      expect(result.apiKey).toBeNull();
      expect(result.isPlaceholder).toBe(true);
      expect(result.placeholderMessage).toBe('Rally integration not implemented');
      expect(result.hasCredentials).toBe(false);
    });

    it('should use custom message from config', () => {
      const mockStore = createMockStore({ rally: { message: 'Custom Rally message' } });
      const token = new RallyApiToken(mockStore);

      const result = token.getApiKey();

      expect(result.placeholderMessage).toBe('Custom Rally message');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Using custom message from config')
      );
    });

    it('should use default message when config has no message', () => {
      const mockStore = createMockStore({ rally: {} });
      const token = new RallyApiToken(mockStore);

      const result = token.getApiKey();

      expect(result.placeholderMessage).toBe('Rally integration not implemented');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Using default placeholder message')
      );
    });
  });

  describe('Log Verification', () => {
    it('should log start of API key resolution as placeholder', () => {
      const token = new RallyApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Starting API key resolution (placeholder)')
      );
    });

    it('should log warning with placeholder message', () => {
      const token = new RallyApiToken();
      token.getApiKey();

      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('Returning placeholder result')
      );
    });

    it('should log isPlaceholder in result', () => {
      const token = new RallyApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('isPlaceholder=true')
      );
    });
  });
});

describe('ElasticsearchApiToken', () => {
  let consoleSpy;
  let originalEnv;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    originalEnv = { ...process.env };
    // Clear all Elasticsearch-related env vars
    delete process.env.ELASTIC_DB_URL;
    delete process.env.ELASTIC_DB_HOST;
    delete process.env.ELASTIC_DB_PORT;
    delete process.env.ELASTIC_DB_USERNAME;
    delete process.env.ELASTIC_DB_ACCESS_KEY;
    delete process.env.ELASTIC_DB_TLS;
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    process.env = originalEnv;
  });

  describe('Provider Properties', () => {
    it('should return correct provider name', () => {
      const token = new ElasticsearchApiToken();
      expect(token.providerName).toBe('elasticsearch');
    });

    it('should return correct health endpoint', () => {
      const token = new ElasticsearchApiToken();
      expect(token.healthEndpoint).toBe('/_cluster/health');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning /_cluster/health')
      );
    });
  });

  describe('getApiKey - Connection URL Behavior', () => {
    // NOTE: Elasticsearch is NOT a placeholder - it's a connection-based provider
    it('should return connection URL when ELASTIC_DB_URL is set', () => {
      process.env.ELASTIC_DB_URL = 'https://user:pass@es.example.com:9243';
      const token = new ElasticsearchApiToken();

      const result = token.getApiKey();

      expect(result.apiKey).toBe('https://user:pass@es.example.com:9243');
      expect(result.authType).toBe('connection_string');
      expect(result.hasCredentials).toBe(true);
      expect(result.isPlaceholder).toBe(false);
    });

    it('should build URL from components when env var not set', () => {
      process.env.ELASTIC_DB_HOST = 'localhost';
      process.env.ELASTIC_DB_PORT = '9200';
      const token = new ElasticsearchApiToken();

      const result = token.getApiKey();

      expect(result.apiKey).toBe('http://localhost:9200');
      expect(result.authType).toBe('connection_string');
      expect(result.hasCredentials).toBe(true);
    });

    it('should use default URL when no env vars set', () => {
      const token = new ElasticsearchApiToken();

      const result = token.getApiKey();

      // Default is http://localhost:9200
      expect(result.apiKey).toBe('http://localhost:9200');
      expect(result.hasCredentials).toBe(true);
    });

    it('should include auth in URL when username and password set', () => {
      process.env.ELASTIC_DB_HOST = 'es.example.com';
      process.env.ELASTIC_DB_PORT = '9243';
      process.env.ELASTIC_DB_USERNAME = 'elastic';
      process.env.ELASTIC_DB_ACCESS_KEY = 'secretkey';
      const token = new ElasticsearchApiToken();

      const result = token.getApiKey();

      // Port 9243 is TLS by default
      expect(result.apiKey).toContain('https://');
      expect(result.apiKey).toContain('elastic:secretkey@');
      expect(result.hasCredentials).toBe(true);
    });
  });

  describe('Log Verification', () => {
    it('should log start of connection URL resolution', () => {
      const token = new ElasticsearchApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Starting')
      );
    });

    it('should log building URL from components', () => {
      const token = new ElasticsearchApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Building URL from components')
      );
    });
  });
});
