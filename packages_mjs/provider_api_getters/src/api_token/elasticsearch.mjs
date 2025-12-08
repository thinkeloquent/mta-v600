/**
 * Elasticsearch connection getter.
 *
 * Returns an Elasticsearch connection URL or client instance.
 *
 * Environment Variables:
 *   ELASTIC_DB_USERNAME: Elasticsearch username
 *   ELASTIC_DB_ACCESS_KEY: Elasticsearch password/access key
 *   ELASTIC_DB_HOST: Elasticsearch host (default: localhost)
 *   ELASTIC_DB_PORT: Elasticsearch port (default: 9200)
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.elasticsearch: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.elasticsearch: ${msg}`),
  error: (msg) => console.error(`[ERROR] provider_api_getters.elasticsearch: ${msg}`),
};

export class ElasticsearchApiToken extends BaseApiToken {
  get providerName() {
    return 'elasticsearch';
  }

  get healthEndpoint() {
    logger.debug('ElasticsearchApiToken.healthEndpoint: Returning /_cluster/health');
    return '/_cluster/health';
  }

  /**
   * Build connection URL from individual environment variables.
   * Uses https:// when ELASTIC_DB_TLS=true or port is 443/9243.
   * @returns {string|null}
   */
  _buildConnectionUrl() {
    logger.debug('ElasticsearchApiToken._buildConnectionUrl: Building URL from components');

    const host = process.env.ELASTIC_DB_HOST || 'localhost';
    const port = process.env.ELASTIC_DB_PORT || '9200';
    const username = process.env.ELASTIC_DB_USERNAME;
    const password = process.env.ELASTIC_DB_ACCESS_KEY;

    // Determine if TLS should be used
    // - Explicit ELASTIC_DB_TLS=true
    // - Known TLS ports (443, 9243 is Elastic Cloud, 25060 is DigitalOcean)
    const elasticTls = ['true', '1', 'yes'].includes((process.env.ELASTIC_DB_TLS || '').toLowerCase());
    const tlsPorts = new Set(['443', '9243', '25060']);
    const useTls = elasticTls || tlsPorts.has(port);

    const scheme = useTls ? 'https' : 'http';

    logger.debug(
      `ElasticsearchApiToken._buildConnectionUrl: Components - ` +
      `host=${host}, port=${port}, ` +
      `username=${username !== undefined ? username : '<none>'}, ` +
      `password=${password ? '***' : undefined}, ` +
      `useTls=${useTls}, scheme=${scheme}`
    );

    let url;
    if (username && password) {
      url = `${scheme}://${username}:${password}@${host}:${port}`;
      logger.debug(
        `ElasticsearchApiToken._buildConnectionUrl: Built URL with username and password ` +
        `(masked=${maskSensitive(url)})`
      );
    } else if (password) {
      // Some setups use API key as password without username
      url = `${scheme}://:${password}@${host}:${port}`;
      logger.debug(
        `ElasticsearchApiToken._buildConnectionUrl: Built URL with password only ` +
        `(masked=${maskSensitive(url)})`
      );
    } else {
      url = `${scheme}://${host}:${port}`;
      logger.debug(
        `ElasticsearchApiToken._buildConnectionUrl: Built URL without authentication ` +
        `(url=${url})`
      );
    }

    return url;
  }

  /**
   * Get Elasticsearch connection URL.
   * @returns {string}
   */
  getConnectionUrl() {
    logger.debug('ElasticsearchApiToken.getConnectionUrl: Starting connection URL resolution');

    // Get env var name from config
    const providerConfig = this._getProviderConfig();
    const envUrl = providerConfig?.env_connection_url || 'ELASTIC_DB_URL';

    logger.debug(`ElasticsearchApiToken.getConnectionUrl: Checking env var '${envUrl}'`);

    const url = process.env[envUrl];

    if (url) {
      logger.debug(
        `ElasticsearchApiToken.getConnectionUrl: Found URL in env var '${envUrl}' ` +
        `(masked=${maskSensitive(url)})`
      );
      return url;
    } else {
      logger.debug(
        `ElasticsearchApiToken.getConnectionUrl: Env var '${envUrl}' not set, ` +
        'building from components'
      );
    }

    // Build from components
    const builtUrl = this._buildConnectionUrl();
    logger.debug('ElasticsearchApiToken.getConnectionUrl: Successfully built URL from components');

    return builtUrl;
  }

  /**
   * Get connection configuration object for @elastic/elasticsearch client.
   * @returns {Object}
   */
  getConnectionConfig() {
    logger.debug('ElasticsearchApiToken.getConnectionConfig: Building connection config');

    const host = process.env.ELASTIC_DB_HOST || 'localhost';
    const port = process.env.ELASTIC_DB_PORT || '9200';
    const username = process.env.ELASTIC_DB_USERNAME;
    const password = process.env.ELASTIC_DB_ACCESS_KEY;

    // Determine if TLS should be used
    const elasticTls = ['true', '1', 'yes'].includes((process.env.ELASTIC_DB_TLS || '').toLowerCase());
    const tlsPorts = new Set(['443', '9243', '25060']);
    const useTls = elasticTls || tlsPorts.has(port);

    const scheme = useTls ? 'https' : 'http';
    const node = `${scheme}://${host}:${port}`;

    const config = { node };

    if (username && password) {
      config.auth = { username, password };
      logger.debug(
        `ElasticsearchApiToken.getConnectionConfig: Built config with basic auth ` +
        `(node=${node}, username=${username})`
      );
    } else if (password) {
      // API key authentication
      config.auth = { apiKey: password };
      logger.debug(
        `ElasticsearchApiToken.getConnectionConfig: Built config with API key auth ` +
        `(node=${node})`
      );
    } else {
      logger.debug(
        `ElasticsearchApiToken.getConnectionConfig: Built config without auth ` +
        `(node=${node})`
      );
    }

    return config;
  }

  /**
   * Get Elasticsearch client (@elastic/elasticsearch).
   * @returns {Promise<any|null>}
   */
  async getClient() {
    logger.debug('ElasticsearchApiToken.getClient: Getting Elasticsearch client');

    let Client;
    try {
      const elastic = await import('@elastic/elasticsearch');
      Client = elastic.Client;
      logger.debug('ElasticsearchApiToken.getClient: @elastic/elasticsearch module imported successfully');
    } catch (error) {
      logger.warn(
        'ElasticsearchApiToken.getClient: @elastic/elasticsearch not installed. ' +
        'Install with: npm install @elastic/elasticsearch'
      );
      return null;
    }

    const config = this.getConnectionConfig();

    logger.debug('ElasticsearchApiToken.getClient: Creating Elasticsearch client');

    try {
      const client = new Client(config);
      logger.debug('ElasticsearchApiToken.getClient: Elasticsearch client created successfully');
      return client;
    } catch (error) {
      logger.error(
        `ElasticsearchApiToken.getClient: Failed to create client: ${error.name}: ${error.message}`
      );
      return null;
    }
  }

  getApiKey() {
    logger.debug('ElasticsearchApiToken.getApiKey: Starting API key resolution');

    const connectionUrl = this.getConnectionUrl();

    logger.debug(
      `ElasticsearchApiToken.getApiKey: Connection URL resolved ` +
      `(hasUrl=${connectionUrl !== null && connectionUrl !== undefined}, ` +
      `masked=${maskSensitive(connectionUrl)})`
    );

    const result = new ApiKeyResult({
      apiKey: connectionUrl,
      authType: 'connection_string',
      headerName: '',
      client: null,
    });

    logger.debug(
      `ElasticsearchApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
    );

    return result;
  }
}
