/**
 * PostgreSQL connection getter.
 *
 * Returns a database connection URL or client instance.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.postgres: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.postgres: ${msg}`),
  error: (msg) => console.error(`[ERROR] provider_api_getters.postgres: ${msg}`),
};

// Default environment variable name
const DEFAULT_CONNECTION_URL_ENV_VAR = 'DATABASE_URL';

export class PostgresApiToken extends BaseApiToken {
  get providerName() {
    return 'postgres';
  }

  get healthEndpoint() {
    logger.debug('PostgresApiToken.healthEndpoint: Returning SELECT 1');
    return 'SELECT 1';
  }

  /**
   * Build connection URL from individual environment variables.
   * @returns {string|null}
   */
  _buildConnectionUrl() {
    logger.debug('PostgresApiToken._buildConnectionUrl: Building URL from components');

    const host = process.env.POSTGRES_HOST;
    const port = process.env.POSTGRES_PORT || '5432';
    const user = process.env.POSTGRES_USER;
    const password = process.env.POSTGRES_PASSWORD;
    const database = process.env.POSTGRES_DB;

    logger.debug(
      `PostgresApiToken._buildConnectionUrl: Components - ` +
      `host=${host !== undefined}, port=${port}, ` +
      `user=${user !== undefined}, password=${password ? '***' : undefined}, ` +
      `database=${database !== undefined}`
    );

    if (host && user && database) {
      logger.debug(
        'PostgresApiToken._buildConnectionUrl: Required components present, building URL'
      );
      let url;
      if (password) {
        url = `postgresql://${user}:${password}@${host}:${port}/${database}`;
        logger.debug(
          `PostgresApiToken._buildConnectionUrl: Built URL with password ` +
          `(masked=${maskSensitive(url)})`
        );
      } else {
        url = `postgresql://${user}@${host}:${port}/${database}`;
        logger.debug(
          `PostgresApiToken._buildConnectionUrl: Built URL without password ` +
          `(masked=${maskSensitive(url)})`
        );
      }
      return url;
    } else {
      const missing = [];
      if (!host) missing.push('POSTGRES_HOST');
      if (!user) missing.push('POSTGRES_USER');
      if (!database) missing.push('POSTGRES_DB');

      logger.debug(
        `PostgresApiToken._buildConnectionUrl: Missing required components: [${missing.join(', ')}]`
      );
      return null;
    }
  }

  /**
   * Get PostgreSQL connection URL.
   * @returns {string|null}
   */
  getConnectionUrl() {
    logger.debug('PostgresApiToken.getConnectionUrl: Starting connection URL resolution');

    // Get env var name from config
    const providerConfig = this._getProviderConfig();
    const envUrl = providerConfig?.env_connection_url || DEFAULT_CONNECTION_URL_ENV_VAR;

    logger.debug(`PostgresApiToken.getConnectionUrl: Checking env var '${envUrl}'`);

    const url = process.env[envUrl];

    if (url) {
      logger.debug(
        `PostgresApiToken.getConnectionUrl: Found URL in env var '${envUrl}' ` +
        `(masked=${maskSensitive(url)})`
      );
      return url;
    } else {
      logger.debug(
        `PostgresApiToken.getConnectionUrl: Env var '${envUrl}' not set, ` +
        'attempting to build from components'
      );
    }

    // Fall back to building from components
    const builtUrl = this._buildConnectionUrl();

    if (builtUrl) {
      logger.debug(
        'PostgresApiToken.getConnectionUrl: Successfully built URL from components'
      );
    } else {
      logger.warn(
        'PostgresApiToken.getConnectionUrl: No connection URL available. ' +
        `Set ${envUrl} or individual POSTGRES_* environment variables.`
      );
    }

    return builtUrl;
  }

  /**
   * Get PostgreSQL client (pg Pool).
   * @returns {Promise<any|null>}
   */
  async getClient() {
    logger.debug('PostgresApiToken.getClient: Getting PostgreSQL client');

    let pg;
    try {
      pg = await import('pg');
      logger.debug('PostgresApiToken.getClient: pg module imported successfully');
    } catch (error) {
      logger.warn(
        'PostgresApiToken.getClient: pg not installed. ' +
        'Install with: npm install pg'
      );
      return null;
    }

    const connectionUrl = this.getConnectionUrl();

    if (!connectionUrl) {
      logger.warn('PostgresApiToken.getClient: No connection URL available');
      return null;
    }

    logger.debug('PostgresApiToken.getClient: Creating connection pool');

    try {
      const pool = new pg.default.Pool({ connectionString: connectionUrl, max: 1 });
      logger.debug('PostgresApiToken.getClient: Connection pool created successfully');
      return pool;
    } catch (error) {
      logger.error(
        `PostgresApiToken.getClient: Failed to create pool: ${error.name}: ${error.message}`
      );
      return null;
    }
  }

  getApiKey() {
    logger.debug('PostgresApiToken.getApiKey: Starting API key resolution');

    const connectionUrl = this.getConnectionUrl();

    if (connectionUrl) {
      logger.debug(
        `PostgresApiToken.getApiKey: Found connection URL ` +
        `(masked=${maskSensitive(connectionUrl)})`
      );
      const result = new ApiKeyResult({
        apiKey: connectionUrl,
        authType: 'connection_string',
        headerName: '',
        client: null,
      });
      logger.debug(
        `PostgresApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    } else {
      logger.warn('PostgresApiToken.getApiKey: No connection URL available');
      const result = new ApiKeyResult({
        apiKey: null,
        authType: 'connection_string',
        headerName: '',
        client: null,
      });
      logger.debug(
        `PostgresApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
