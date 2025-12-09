/**
 * Redis connection getter.
 *
 * Returns a Redis connection URL or client instance.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.redis: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.redis: ${msg}`),
  error: (msg) => console.error(`[ERROR] provider_api_getters.redis: ${msg}`),
};

// Default environment variable name
const DEFAULT_CONNECTION_URL_ENV_VAR = 'REDIS_URL';

export class RedisApiToken extends BaseApiToken {
  get providerName() {
    return 'redis';
  }

  get healthEndpoint() {
    logger.debug('RedisApiToken.healthEndpoint: Returning PING');
    return 'PING';
  }

  /**
   * Build connection URL from individual environment variables.
   * Uses rediss:// (TLS) when REDIS_TLS=true or port is a known TLS port (25061).
   * @returns {string}
   */
  _buildConnectionUrl() {
    logger.debug('RedisApiToken._buildConnectionUrl: Building URL from components');

    const host = process.env.REDIS_HOST || 'localhost';
    const port = process.env.REDIS_PORT || '6379';
    const password = process.env.REDIS_PASSWORD;
    const db = process.env.REDIS_DB || '0';
    const username = process.env.REDIS_USERNAME;

    // Determine if TLS should be used
    // - Explicit REDIS_TLS=true
    // - Known TLS ports (25061 is DigitalOcean's TLS port)
    const redisTls = ['true', '1', 'yes'].includes((process.env.REDIS_TLS || '').toLowerCase());
    const tlsPorts = new Set(['25061', '6380']); // Common TLS ports
    const useTls = redisTls || tlsPorts.has(port);

    const scheme = useTls ? 'rediss' : 'redis';

    logger.debug(
      `RedisApiToken._buildConnectionUrl: Components - ` +
      `host=${host}, port=${port}, ` +
      `username=${username !== undefined ? username : '<default>'}, ` +
      `password=${password ? '***' : undefined}, ` +
      `db=${db}, useTls=${useTls}, scheme=${scheme}`
    );

    let url;
    if (password) {
      logger.debug(
        'RedisApiToken._buildConnectionUrl: Password is present, checking for username'
      );
      if (username) {
        url = `${scheme}://${username}:${password}@${host}:${port}/${db}`;
        logger.debug(
          `RedisApiToken._buildConnectionUrl: Built URL with username and password ` +
          `(masked=${maskSensitive(url)})`
        );
      } else {
        url = `${scheme}://:${password}@${host}:${port}/${db}`;
        logger.debug(
          `RedisApiToken._buildConnectionUrl: Built URL with password only ` +
          `(masked=${maskSensitive(url)})`
        );
      }
    } else {
      url = `${scheme}://${host}:${port}/${db}`;
      logger.debug(
        `RedisApiToken._buildConnectionUrl: Built URL without authentication ` +
        `(url=${url})`
      );
    }

    return url;
  }

  /**
   * Get Redis connection URL.
   * @returns {string}
   */
  getConnectionUrl() {
    logger.debug('RedisApiToken.getConnectionUrl: Starting connection URL resolution');

    // Get env var name from config
    const providerConfig = this._getProviderConfig();
    const envUrl = providerConfig?.env_connection_url || DEFAULT_CONNECTION_URL_ENV_VAR;

    logger.debug(`RedisApiToken.getConnectionUrl: Checking env var '${envUrl}'`);

    const url = process.env[envUrl];

    if (url) {
      logger.debug(
        `RedisApiToken.getConnectionUrl: Found URL in env var '${envUrl}' ` +
        `(masked=${maskSensitive(url)})`
      );
      return url;
    } else {
      logger.debug(
        `RedisApiToken.getConnectionUrl: Env var '${envUrl}' not set, ` +
        'building from components'
      );
    }

    // Build from components
    const builtUrl = this._buildConnectionUrl();
    logger.debug('RedisApiToken.getConnectionUrl: Successfully built URL from components');

    return builtUrl;
  }

  /**
   * Get Redis client (ioredis).
   * @returns {Promise<any|null>}
   */
  async getClient() {
    logger.debug('RedisApiToken.getClient: Getting Redis client');

    let Redis;
    try {
      const ioredis = await import('ioredis');
      Redis = ioredis.default;
      logger.debug('RedisApiToken.getClient: ioredis module imported successfully');
    } catch (error) {
      logger.warn(
        'RedisApiToken.getClient: ioredis not installed. ' +
        'Install with: npm install ioredis'
      );
      return null;
    }

    const connectionUrl = this.getConnectionUrl();

    if (!connectionUrl) {
      logger.warn('RedisApiToken.getClient: No connection URL available');
      return null;
    }

    logger.debug('RedisApiToken.getClient: Creating Redis client');

    try {
      const client = new Redis(connectionUrl);
      logger.debug('RedisApiToken.getClient: Redis client created successfully');
      return client;
    } catch (error) {
      logger.error(
        `RedisApiToken.getClient: Failed to create client: ${error.name}: ${error.message}`
      );
      return null;
    }
  }

  getApiKey() {
    logger.debug('RedisApiToken.getApiKey: Starting API key resolution');

    const connectionUrl = this.getConnectionUrl();

    logger.debug(
      `RedisApiToken.getApiKey: Connection URL resolved ` +
      `(hasUrl=${connectionUrl !== null && connectionUrl !== undefined}, ` +
      `masked=${maskSensitive(connectionUrl)})`
    );

    // Get raw credentials for the result
    const redisUsername = process.env.REDIS_USERNAME;
    const redisPassword = process.env.REDIS_PASSWORD;

    const result = new ApiKeyResult({
      apiKey: connectionUrl,
      authType: 'connection_string',
      headerName: '',
      client: null,
      email: redisUsername,
      rawApiKey: redisPassword,
    });

    logger.debug(
      `RedisApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
    );

    return result;
  }
}
