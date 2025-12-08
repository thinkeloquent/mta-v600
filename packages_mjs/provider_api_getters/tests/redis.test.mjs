/**
 * Comprehensive tests for redis.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All if/else paths
 * - Connection URL building: 3 branches (user+pass, pass only, no auth)
 * - Log verification: Console spy checks
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { RedisApiToken } from '../src/api_token/redis.mjs';

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

describe('RedisApiToken', () => {
  let consoleSpy;
  let originalEnv;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    originalEnv = { ...process.env };
    // Clear redis env vars
    delete process.env.REDIS_URL;
    delete process.env.REDIS_HOST;
    delete process.env.REDIS_PORT;
    delete process.env.REDIS_USERNAME;
    delete process.env.REDIS_PASSWORD;
    delete process.env.REDIS_DB;
    delete process.env.REDIS_TLS;
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    process.env = originalEnv;
  });

  describe('Provider Properties', () => {
    it('should return correct provider name', () => {
      const token = new RedisApiToken();
      expect(token.providerName).toBe('redis');
    });

    it('should return correct health endpoint', () => {
      const token = new RedisApiToken();
      expect(token.healthEndpoint).toBe('PING');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Returning PING')
      );
    });
  });

  describe('_buildConnectionUrl - 3-Branch Coverage', () => {
    it('Branch 1: No password - should build URL without auth', () => {
      const token = new RedisApiToken();

      const url = token._buildConnectionUrl();

      expect(url).toBe('redis://localhost:6379/0');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Built URL without authentication')
      );
    });

    it('Branch 2: Password only - should build URL with password only', () => {
      const token = new RedisApiToken();
      process.env.REDIS_PASSWORD = 'secret';

      const url = token._buildConnectionUrl();

      expect(url).toBe('redis://:secret@localhost:6379/0');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Built URL with password only')
      );
    });

    it('Branch 3: Password and username - should build URL with both', () => {
      const token = new RedisApiToken();
      process.env.REDIS_PASSWORD = 'secret';
      process.env.REDIS_USERNAME = 'myuser';

      const url = token._buildConnectionUrl();

      expect(url).toBe('redis://myuser:secret@localhost:6379/0');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Built URL with username and password')
      );
    });

    it('should use custom host', () => {
      const token = new RedisApiToken();
      process.env.REDIS_HOST = 'redis.example.com';

      const url = token._buildConnectionUrl();

      expect(url).toBe('redis://redis.example.com:6379/0');
    });

    it('should use custom port (non-TLS)', () => {
      const token = new RedisApiToken();
      process.env.REDIS_PORT = '6381'; // Non-TLS port

      const url = token._buildConnectionUrl();

      expect(url).toBe('redis://localhost:6381/0');
    });

    it('should auto-detect TLS for port 6380', () => {
      const token = new RedisApiToken();
      process.env.REDIS_PORT = '6380'; // TLS port

      const url = token._buildConnectionUrl();

      expect(url).toBe('rediss://localhost:6380/0');
    });

    it('should auto-detect TLS for port 25061 (DigitalOcean)', () => {
      const token = new RedisApiToken();
      process.env.REDIS_PORT = '25061';
      process.env.REDIS_PASSWORD = 'secret';

      const url = token._buildConnectionUrl();

      expect(url).toMatch(/^rediss:\/\//);
      expect(url).toContain(':25061');
    });

    it('should use TLS when REDIS_TLS=true', () => {
      const token = new RedisApiToken();
      process.env.REDIS_TLS = 'true';

      const url = token._buildConnectionUrl();

      expect(url).toBe('rediss://localhost:6379/0');
    });

    it('should use custom database', () => {
      const token = new RedisApiToken();
      process.env.REDIS_DB = '5';

      const url = token._buildConnectionUrl();

      expect(url).toBe('redis://localhost:6379/5');
    });

    it('should use all custom values', () => {
      const token = new RedisApiToken();
      process.env.REDIS_HOST = 'custom.host';
      process.env.REDIS_PORT = '16379';
      process.env.REDIS_USERNAME = 'admin';
      process.env.REDIS_PASSWORD = 'adminpass';
      process.env.REDIS_DB = '2';

      const url = token._buildConnectionUrl();

      expect(url).toBe('redis://admin:adminpass@custom.host:16379/2');
    });

    it('should log component state', () => {
      const token = new RedisApiToken();
      token._buildConnectionUrl();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('Components -')
      );
    });
  });

  describe('getConnectionUrl - Decision Coverage', () => {
    it('should return URL from REDIS_URL env var', () => {
      const token = new RedisApiToken();
      process.env.REDIS_URL = 'redis://user:pass@host:6379/1';

      const url = token.getConnectionUrl();

      expect(url).toBe('redis://user:pass@host:6379/1');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining("Found URL in env var 'REDIS_URL'")
      );
    });

    it('should use custom env var name from config', () => {
      const mockStore = createMockStore({ redis: { env_connection_url: 'CUSTOM_REDIS_URL' } });
      const token = new RedisApiToken(mockStore);
      process.env.CUSTOM_REDIS_URL = 'redis://custom@host/2';

      const url = token.getConnectionUrl();

      expect(url).toBe('redis://custom@host/2');
    });

    it('should fall back to building URL when env var not set', () => {
      const token = new RedisApiToken();
      process.env.REDIS_HOST = 'myhost';

      const url = token.getConnectionUrl();

      expect(url).toBe('redis://myhost:6379/0');
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('building from components')
      );
    });
  });

  describe('getApiKey', () => {
    it('should return connection URL as apiKey', () => {
      const token = new RedisApiToken();
      process.env.REDIS_URL = 'redis://user:pass@host/1';

      const result = token.getApiKey();

      expect(result.apiKey).toBe('redis://user:pass@host/1');
      expect(result.authType).toBe('connection_string');
      expect(result.headerName).toBe('Authorization'); // Normalized from empty string
    });

    it('should always have credentials (default URL)', () => {
      const token = new RedisApiToken();

      const result = token.getApiKey();

      // Redis always builds a URL even with defaults
      expect(result.apiKey).toBe('redis://localhost:6379/0');
      expect(result.hasCredentials).toBe(true);
    });

    it('should log hasCredentials in result', () => {
      const token = new RedisApiToken();

      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('hasCredentials=')
      );
    });

    it('should log masked URL', () => {
      const token = new RedisApiToken();
      process.env.REDIS_PASSWORD = 'secret';

      token.getApiKey();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining('masked=')
      );
    });
  });

  describe('getClient', () => {
    it('should attempt to create client or warn if ioredis not installed', async () => {
      const token = new RedisApiToken();

      // getClient will either:
      // 1. Return a client if ioredis is installed
      // 2. Return null if ioredis is not installed
      const client = await token.getClient();

      if (client === null) {
        // ioredis not installed
        expect(consoleSpy.warn).toHaveBeenCalledWith(
          expect.stringContaining('ioredis not installed')
        );
      } else {
        // ioredis is installed, client was created
        expect(client).toBeDefined();
        // Clean up the connection
        if (client && typeof client.quit === 'function') {
          await client.quit();
        }
      }
    });
  });
});
