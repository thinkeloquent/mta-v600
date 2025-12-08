/**
 * Elasticsearch API token getter (placeholder).
 *
 * This is a placeholder implementation for future Elasticsearch integration.
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.elasticsearch: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.elasticsearch: ${msg}`),
};

// Default placeholder message
const DEFAULT_PLACEHOLDER_MESSAGE = 'Elasticsearch integration not implemented';

export class ElasticsearchApiToken extends BaseApiToken {
  get providerName() {
    return 'elasticsearch';
  }

  get healthEndpoint() {
    logger.debug('ElasticsearchApiToken.healthEndpoint: Returning /_cluster/health');
    return '/_cluster/health';
  }

  getApiKey() {
    logger.debug('ElasticsearchApiToken.getApiKey: Starting API key resolution (placeholder)');

    const providerConfig = this._getProviderConfig();

    logger.debug(
      `ElasticsearchApiToken.getApiKey: Checking for custom placeholder message in config ` +
      `(hasConfig=${providerConfig !== null && providerConfig !== undefined})`
    );

    let message;
    if (providerConfig?.message) {
      message = providerConfig.message;
      logger.debug(
        `ElasticsearchApiToken.getApiKey: Using custom message from config: '${message}'`
      );
    } else {
      message = DEFAULT_PLACEHOLDER_MESSAGE;
      logger.debug(
        `ElasticsearchApiToken.getApiKey: Using default placeholder message: '${message}'`
      );
    }

    logger.warn(
      `ElasticsearchApiToken.getApiKey: Returning placeholder result - ${message}`
    );

    const result = new ApiKeyResult({
      apiKey: null,
      isPlaceholder: true,
      placeholderMessage: message,
    });

    logger.debug(
      `ElasticsearchApiToken.getApiKey: Returning result ` +
      `hasCredentials=${result.hasCredentials}, isPlaceholder=${result.isPlaceholder}`
    );

    return result;
  }
}
