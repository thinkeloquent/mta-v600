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

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
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

  describe('getApiKey - Placeholder Behavior', () => {
    it('should return placeholder result with default message', () => {
      const token = new ElasticsearchApiToken();

      const result = token.getApiKey();

      expect(result.apiKey).toBeNull();
      expect(result.isPlaceholder).toBe(true);
      expect(result.placeholderMessage).toBe('Elasticsearch integration not implemented');
      expect(result.hasCredentials).toBe(false);
    });

    it('should use custom message from config', () => {
      const mockStore = createMockStore({ elasticsearch: { message: 'Custom ES message' } });
      const token = new ElasticsearchApiToken(mockStore);

      const result = token.getApiKey();

      expect(result.placeholderMessage).toBe('Custom ES message');
    });

    it('should use default message when config has no message', () => {
      const mockStore = createMockStore({ elasticsearch: {} });
      const token = new ElasticsearchApiToken(mockStore);

      const result = token.getApiKey();

      expect(result.placeholderMessage).toBe('Elasticsearch integration not implemented');
    });
  });

  describe('Log Verification', () => {
    it('should log start of API key resolution as placeholder', () => {
      const token = new ElasticsearchApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Starting API key resolution (placeholder)')
      );
    });

    it('should log warning with placeholder message', () => {
      const token = new ElasticsearchApiToken();
      token.getApiKey();

      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('Returning placeholder result')
      );
    });

    it('should log checking for custom message in config', () => {
      const token = new ElasticsearchApiToken();
      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Checking for custom placeholder message in config')
      );
    });
  });
});
