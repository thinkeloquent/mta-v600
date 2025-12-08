/**
 * Comprehensive tests for postgres.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All if/else paths
 * - Connection URL building with/without password
 * - Log verification: Console spy checks
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { PostgresApiToken } from '../src/api_token/postgres.mjs';

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

describe('PostgresApiToken', () => {
  let consoleSpy;
  let originalEnv;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    originalEnv = { ...process.env };
    // Clear postgres env vars
    delete process.env.DATABASE_URL;
    delete process.env.POSTGRES_HOST;
    delete process.env.POSTGRES_PORT;
    delete process.env.POSTGRES_USER;
    delete process.env.POSTGRES_PASSWORD;
    delete process.env.POSTGRES_DB;
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    process.env = originalEnv;
  });

  describe('Provider Properties', () => {
    it('should return correct provider name', () => {
      const token = new PostgresApiToken();
      expect(token.providerName).toBe('postgres');
    });

    it('should return correct health endpoint', () => {
      const token = new PostgresApiToken();
      expect(token.healthEndpoint).toBe('SELECT 1');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning SELECT 1')
      );
    });
  });

  describe('_buildConnectionUrl - Decision Coverage', () => {
    it('should return null when missing required components', () => {
      const token = new PostgresApiToken();

      const url = token._buildConnectionUrl();

      expect(url).toBeNull();
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Missing required components')
      );
    });

    it('should return null when only host is set', () => {
      const token = new PostgresApiToken();
      process.env.POSTGRES_HOST = 'localhost';

      const url = token._buildConnectionUrl();

      expect(url).toBeNull();
    });

    it('should return null when only user is set', () => {
      const token = new PostgresApiToken();
      process.env.POSTGRES_USER = 'testuser';

      const url = token._buildConnectionUrl();

      expect(url).toBeNull();
    });

    it('should build URL without password when all required components present', () => {
      const token = new PostgresApiToken();
      process.env.POSTGRES_HOST = 'localhost';
      process.env.POSTGRES_USER = 'testuser';
      process.env.POSTGRES_DB = 'testdb';

      const url = token._buildConnectionUrl();

      expect(url).toBe('postgresql://testuser@localhost:5432/testdb');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Built URL without password')
      );
    });

    it('should build URL with password when provided', () => {
      const token = new PostgresApiToken();
      process.env.POSTGRES_HOST = 'localhost';
      process.env.POSTGRES_USER = 'testuser';
      process.env.POSTGRES_PASSWORD = 'secretpass';
      process.env.POSTGRES_DB = 'testdb';

      const url = token._buildConnectionUrl();

      expect(url).toBe('postgresql://testuser:secretpass@localhost:5432/testdb');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Built URL with password')
      );
    });

    it('should use custom port when provided', () => {
      const token = new PostgresApiToken();
      process.env.POSTGRES_HOST = 'localhost';
      process.env.POSTGRES_PORT = '5433';
      process.env.POSTGRES_USER = 'testuser';
      process.env.POSTGRES_DB = 'testdb';

      const url = token._buildConnectionUrl();

      expect(url).toBe('postgresql://testuser@localhost:5433/testdb');
    });

    it('should log missing components', () => {
      const token = new PostgresApiToken();
      process.env.POSTGRES_HOST = 'localhost';

      token._buildConnectionUrl();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('POSTGRES_USER')
      );
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('POSTGRES_DB')
      );
    });
  });

  describe('getConnectionUrl - Decision Coverage', () => {
    it('should return URL from DATABASE_URL env var', () => {
      const token = new PostgresApiToken();
      process.env.DATABASE_URL = 'postgresql://user:pass@host:5432/db';

      const url = token.getConnectionUrl();

      expect(url).toBe('postgresql://user:pass@host:5432/db');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining("Found URL in env var 'DATABASE_URL'")
      );
    });

    it('should use custom env var name from config', () => {
      const mockStore = createMockStore({ postgres: { env_connection_url: 'CUSTOM_DB_URL' } });
      const token = new PostgresApiToken(mockStore);
      process.env.CUSTOM_DB_URL = 'postgresql://custom@host/db';

      const url = token.getConnectionUrl();

      expect(url).toBe('postgresql://custom@host/db');
    });

    it('should fall back to building URL when env var not set', () => {
      const token = new PostgresApiToken();
      process.env.POSTGRES_HOST = 'localhost';
      process.env.POSTGRES_USER = 'user';
      process.env.POSTGRES_DB = 'db';

      const url = token.getConnectionUrl();

      expect(url).toBe('postgresql://user@localhost:5432/db');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('attempting to build from components')
      );
    });

    it('should return null when no URL available', () => {
      const token = new PostgresApiToken();

      const url = token.getConnectionUrl();

      expect(url).toBeNull();
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('No connection URL available')
      );
    });
  });

  describe('getApiKey', () => {
    it('should return connection URL as apiKey', () => {
      const token = new PostgresApiToken();
      process.env.DATABASE_URL = 'postgresql://user:pass@host/db';

      const result = token.getApiKey();

      expect(result.apiKey).toBe('postgresql://user:pass@host/db');
      expect(result.authType).toBe('connection_string');
      expect(result.headerName).toBe('Authorization'); // Normalized from empty string
    });

    it('should return null apiKey when no connection URL', () => {
      const token = new PostgresApiToken();

      const result = token.getApiKey();

      expect(result.apiKey).toBeNull();
      expect(result.hasCredentials).toBe(false);
    });

    it('should log hasCredentials in result', () => {
      const token = new PostgresApiToken();
      process.env.DATABASE_URL = 'postgresql://user@host/db';

      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('hasCredentials=true')
      );
    });
  });

  describe('getClient', () => {
    it('should return null when pg module not available', async () => {
      const token = new PostgresApiToken();
      process.env.DATABASE_URL = 'postgresql://user@host/db';

      // pg module is likely not installed in test env
      const client = await token.getClient();

      // Will be null because pg is not installed
      expect(client).toBeNull();
    });

    it('should return null when no connection URL', async () => {
      const token = new PostgresApiToken();

      const client = await token.getClient();

      expect(client).toBeNull();
    });
  });
});
