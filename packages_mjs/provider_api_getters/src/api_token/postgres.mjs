/**
 * PostgreSQL connection getter.
 *
 * Returns a database connection URL or client instance.
 */
import { fileURLToPath } from 'url';
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Get current file path for logging
const __filename = fileURLToPath(import.meta.url);
const LOG_PREFIX = `[POSTGRES:${__filename}]`;

// Logger with file path for tracing
const logger = {
  info: (msg) => console.log(`${LOG_PREFIX} ${msg}`),
  debug: (msg) => console.debug(`${LOG_PREFIX} ${msg}`),
  warn: (msg) => console.warn(`${LOG_PREFIX} ${msg}`),
  error: (msg) => console.error(`${LOG_PREFIX} ${msg}`),
};

// Default environment variable name
const DEFAULT_CONNECTION_URL_ENV_VAR = 'DATABASE_URL';

export class PostgresApiToken extends BaseApiToken {
  get providerName() {
    return 'postgres';
  }

  get healthEndpoint() {
    logger.debug('healthEndpoint: Returning SELECT 1');
    return 'SELECT 1';
  }

  /**
   * Build connection URL from individual environment variables.
   * @returns {string|null}
   */
  _buildConnectionUrl() {
    logger.info('_buildConnectionUrl: START - Building URL from environment variables');

    const host = process.env.POSTGRES_HOST;
    const port = process.env.POSTGRES_PORT || '5432';
    const user = process.env.POSTGRES_USER;
    const password = process.env.POSTGRES_PASSWORD;
    const database = process.env.POSTGRES_DB;
    const sslmode = process.env.POSTGRES_SSLMODE;
    const sslCertVerify = process.env.SSL_CERT_VERIFY;
    const nodeTls = process.env.NODE_TLS_REJECT_UNAUTHORIZED;

    // Log all environment variable states
    logger.info(
      `_buildConnectionUrl: Environment variables:\n` +
      `  POSTGRES_HOST=${host ?? '<not set>'}\n` +
      `  POSTGRES_PORT=${port}\n` +
      `  POSTGRES_USER=${user ? maskSensitive(user) : '<not set>'}\n` +
      `  POSTGRES_PASSWORD=${password ? '<set>' : '<not set>'}\n` +
      `  POSTGRES_DB=${database ?? '<not set>'}\n` +
      `  POSTGRES_SSLMODE=${sslmode ?? '<not set>'}\n` +
      `  SSL_CERT_VERIFY=${sslCertVerify ?? '<not set>'}\n` +
      `  NODE_TLS_REJECT_UNAUTHORIZED=${nodeTls ?? '<not set>'}`
    );

    if (host && user && database) {
      logger.info(
        `_buildConnectionUrl: All required components present ` +
        `(host=${host}, user=${maskSensitive(user)}, database=${database})`
      );
      let url;
      // URL-encode user and password to handle special characters
      const encodedUser = encodeURIComponent(user);
      // Note: SSL is configured via Sequelize dialectOptions, not URL sslmode parameter
      if (password) {
        const encodedPassword = encodeURIComponent(password);
        url = `postgresql://${encodedUser}:${encodedPassword}@${host}:${port}/${database}`;
        logger.debug('_buildConnectionUrl: URL built with password');
      } else {
        url = `postgresql://${encodedUser}@${host}:${port}/${database}`;
        logger.warn('_buildConnectionUrl: URL built WITHOUT password');
      }

      logger.info(
        `_buildConnectionUrl: SUCCESS - Built URL: ` +
        `postgresql://${maskSensitive(user)}:****@${host}:${port}/${database}`
      );
      return url;
    } else {
      const missing = [];
      if (!host) missing.push('POSTGRES_HOST');
      if (!user) missing.push('POSTGRES_USER');
      if (!database) missing.push('POSTGRES_DB');

      logger.warn(
        `_buildConnectionUrl: FAILED - Missing required env vars: [${missing.join(', ')}]`
      );
      return null;
    }
  }

  /**
   * Get PostgreSQL connection URL.
   * @returns {string|null}
   */
  getConnectionUrl() {
    logger.info('getConnectionUrl: START - Resolving connection URL');

    // Get env var name from config
    const providerConfig = this._getProviderConfig();
    const envUrl = providerConfig?.env_connection_url || DEFAULT_CONNECTION_URL_ENV_VAR;

    // Step 1: Check DATABASE_URL first
    logger.info(`getConnectionUrl: Step 1 - Checking env var '${envUrl}'`);
    const url = process.env[envUrl];

    if (url) {
      logger.info(
        `getConnectionUrl: SUCCESS - Found URL in env var '${envUrl}'\n` +
        `  URL (masked): ${maskSensitive(url)}`
      );
      return url;
    } else {
      logger.info(
        `getConnectionUrl: Step 2 - Env var '${envUrl}' not set, trying POSTGRES_* env vars`
      );
    }

    // Fall back to building from components
    const builtUrl = this._buildConnectionUrl();

    if (builtUrl) {
      logger.info('getConnectionUrl: SUCCESS - Built URL from POSTGRES_* env vars');
    } else {
      logger.error(
        `getConnectionUrl: FAILED - No connection URL available.\n` +
        `  Set ${envUrl} env var with full connection string, OR\n` +
        `  Set POSTGRES_HOST + POSTGRES_USER + POSTGRES_DB env vars`
      );
    }

    return builtUrl;
  }

  /**
   * Get PostgreSQL client (Sequelize instance).
   * @returns {Promise<any|null>}
   */
  async getClient() {
    logger.info('getClient: START - Creating Sequelize PostgreSQL client');

    // Step 1: Import Sequelize
    let Sequelize;
    try {
      const sequelizeModule = await import('sequelize');
      Sequelize = sequelizeModule.Sequelize;
      logger.info('getClient: Sequelize module imported successfully');
    } catch (error) {
      logger.error(
        `getClient: FAILED - Sequelize not installed!\n` +
        `  Error: ${error.message}\n` +
        `  Fix: npm install sequelize pg`
      );
      return null;
    }

    // Step 2: Get connection URL
    logger.info('getClient: Step 2 - Getting connection URL');
    const connectionUrl = this.getConnectionUrl();

    if (!connectionUrl) {
      logger.error(
        'getClient: FAILED - No connection URL available\n' +
        '  Check POSTGRES_* env vars or DATABASE_URL'
      );
      return null;
    }

    // Step 3: Determine SSL configuration
    logger.info('getClient: Step 3 - Determining SSL configuration');

    // Check SSL config from YAML or env
    const providerConfig = this._getProviderConfig();
    const sslConfig = providerConfig?.ssl;
    const sslMode = process.env.POSTGRES_SSLMODE || '';

    // Check if SSL should be disabled via environment variables
    // SSL_CERT_VERIFY=0 or NODE_TLS_REJECT_UNAUTHORIZED=0 means disable SSL
    const sslCertVerify = process.env.SSL_CERT_VERIFY || '';
    const nodeTls = process.env.NODE_TLS_REJECT_UNAUTHORIZED || '';
    const disableSslByEnv = sslCertVerify === '0' || nodeTls === '0';

    logger.info(
      `getClient: SSL-related env vars:\n` +
      `  POSTGRES_SSLMODE=${sslMode || '<not set>'}\n` +
      `  SSL_CERT_VERIFY=${sslCertVerify || '<not set>'}\n` +
      `  NODE_TLS_REJECT_UNAUTHORIZED=${nodeTls || '<not set>'}`
    );

    // Build dialectOptions for SSL
    // For Sequelize, SSL config must be inside dialectOptions.ssl
    const dialectOptions = {};
    let sslDesc = '';

    if (disableSslByEnv) {
      dialectOptions.ssl = false;
      sslDesc = 'DISABLED via SSL_CERT_VERIFY=0 or NODE_TLS_REJECT_UNAUTHORIZED=0';
      logger.info(
        `getClient: SSL DISABLED via env var override\n` +
        `  Reason: SSL_CERT_VERIFY=${sslCertVerify || '<not set>'} or NODE_TLS_REJECT_UNAUTHORIZED=${nodeTls || '<not set>'}\n` +
        `  dialectOptions.ssl = false`
      );
    } else if (sslMode === 'disable' || sslMode === 'false' || sslMode === '0') {
      dialectOptions.ssl = false;
      sslDesc = 'DISABLED via POSTGRES_SSLMODE';
      logger.info(
        `getClient: SSL DISABLED explicitly\n` +
        `  Reason: POSTGRES_SSLMODE=${sslMode}\n` +
        `  dialectOptions.ssl = false`
      );
    } else if (sslConfig) {
      // Use SSL config from YAML
      const rejectUnauthorized = sslConfig.rejectUnauthorized === false ? false : true;
      dialectOptions.ssl = {
        require: true,
        rejectUnauthorized,
      };
      sslDesc = `ENABLED from YAML config (rejectUnauthorized=${rejectUnauthorized})`;
      logger.info(
        `getClient: SSL ENABLED from YAML config\n` +
        `  rejectUnauthorized=${rejectUnauthorized}\n` +
        `  dialectOptions.ssl = { require: true, rejectUnauthorized: ${rejectUnauthorized} }`
      );
    } else if (sslMode === 'require' || sslMode === 'prefer' || sslMode === 'true' || sslMode === '1') {
      // Default: accept self-signed certificates from managed database providers
      dialectOptions.ssl = {
        require: true,
        rejectUnauthorized: false,
      };
      sslDesc = 'ENABLED without cert verification (default for managed DBs)';
      logger.info(
        `getClient: SSL ENABLED without cert verification\n` +
        `  POSTGRES_SSLMODE=${sslMode}\n` +
        `  dialectOptions.ssl = { require: true, rejectUnauthorized: false }`
      );
    } else {
      // No SSL mode set - default to no SSL
      sslDesc = 'DISABLED (no POSTGRES_SSLMODE set, defaulting to no SSL)';
      logger.info(
        `getClient: SSL DISABLED (default)\n` +
        `  Reason: POSTGRES_SSLMODE not set\n` +
        `  dialectOptions.ssl = undefined (Sequelize default)`
      );
    }

    // Step 4: Create Sequelize instance
    logger.info(
      `getClient: Step 4 - Creating Sequelize instance\n` +
      `  URL (masked): ${maskSensitive(connectionUrl)}\n` +
      `  SSL: ${sslDesc}\n` +
      `  Pool config: max=1, min=0, acquire=30000, idle=10000`
    );

    try {
      const sequelize = new Sequelize(connectionUrl, {
        dialect: 'postgres',
        logging: false,
        pool: {
          max: 1,
          min: 0,
          acquire: 30000,
          idle: 10000,
        },
        dialectOptions,
      });

      logger.info(
        `getClient: SUCCESS - Sequelize instance created!\n` +
        `  Pool size: max=1, min=0`
      );
      return sequelize;
    } catch (error) {
      const errorMsg = error.message || '';
      if (errorMsg.toLowerCase().includes('ssl')) {
        logger.error(
          `getClient: FAILED - SSL connection error!\n` +
          `  Error: ${error.name}: ${error.message}\n` +
          `  Current SSL setting: ${sslDesc}\n` +
          `  If server doesn't support SSL, set SSL_CERT_VERIFY=0 or POSTGRES_SSLMODE=disable`
        );
      } else {
        logger.error(
          `getClient: FAILED - Could not create Sequelize instance!\n` +
          `  Error: ${error.name}: ${error.message}\n` +
          `  URL (masked): ${maskSensitive(connectionUrl)}\n` +
          `  SSL: ${sslDesc}`
        );
      }
      return null;
    }
  }

  getApiKey() {
    logger.info('getApiKey: START - Creating ApiKeyResult for PostgreSQL');

    const connectionUrl = this.getConnectionUrl();

    // Get raw credentials for the result
    const user = process.env.POSTGRES_USER;
    const password = process.env.POSTGRES_PASSWORD;

    logger.info(
      `getApiKey: Credentials:\n` +
      `  POSTGRES_USER=${user ? maskSensitive(user) : '<not set>'}\n` +
      `  POSTGRES_PASSWORD=${password ? '<set>' : '<not set>'}\n` +
      `  connection_url=${connectionUrl ? '<resolved>' : '<not resolved>'}`
    );

    if (connectionUrl) {
      logger.info(
        `getApiKey: SUCCESS - Connection URL resolved\n` +
        `  URL (masked): ${maskSensitive(connectionUrl)}`
      );

      const result = new ApiKeyResult({
        apiKey: connectionUrl,
        authType: 'connection_string',
        headerName: '',
        client: null,
        email: user,
        rawApiKey: password,
      });

      logger.info(
        `getApiKey: RESULT:\n` +
        `  hasCredentials=${result.hasCredentials}\n` +
        `  isPlaceholder=${result.isPlaceholder}\n` +
        `  authType=${result.authType}`
      );
      return result;
    } else {
      logger.warn(
        `getApiKey: WARNING - No connection URL available\n` +
        `  hasCredentials will be false`
      );

      const result = new ApiKeyResult({
        apiKey: null,
        authType: 'connection_string',
        headerName: '',
        client: null,
        email: user,
        rawApiKey: password,
      });

      logger.info(
        `getApiKey: RESULT:\n` +
        `  hasCredentials=${result.hasCredentials}\n` +
        `  isPlaceholder=${result.isPlaceholder}\n` +
        `  authType=${result.authType}`
      );
      return result;
    }
  }
}
