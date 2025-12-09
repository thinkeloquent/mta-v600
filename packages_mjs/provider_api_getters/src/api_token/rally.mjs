/**
 * Rally API token getter (placeholder).
 *
 * This is a placeholder implementation for future Rally integration.
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.rally: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.rally: ${msg}`),
};

// Default placeholder message
const DEFAULT_PLACEHOLDER_MESSAGE = 'Rally integration not implemented';

export class RallyApiToken extends BaseApiToken {
  get providerName() {
    return 'rally';
  }

  get healthEndpoint() {
    logger.debug('RallyApiToken.healthEndpoint: Returning /');
    return '/';
  }

  getApiKey() {
    logger.debug('RallyApiToken.getApiKey: Starting API key resolution (placeholder)');

    const providerConfig = this._getProviderConfig();

    logger.debug(
      `RallyApiToken.getApiKey: Checking for custom placeholder message in config ` +
      `(hasConfig=${providerConfig !== null && providerConfig !== undefined})`
    );

    let message;
    if (providerConfig?.message) {
      message = providerConfig.message;
      logger.debug(
        `RallyApiToken.getApiKey: Using custom message from config: '${message}'`
      );
    } else {
      message = DEFAULT_PLACEHOLDER_MESSAGE;
      logger.debug(
        `RallyApiToken.getApiKey: Using default placeholder message: '${message}'`
      );
    }

    logger.warn(
      `RallyApiToken.getApiKey: Returning placeholder result - ${message}`
    );

    const result = new ApiKeyResult({
      apiKey: null,
      isPlaceholder: true,
      placeholderMessage: message,
      email: null,
      rawApiKey: null,
    });

    logger.debug(
      `RallyApiToken.getApiKey: Returning result ` +
      `hasCredentials=${result.hasCredentials}, isPlaceholder=${result.isPlaceholder}`
    );

    return result;
  }
}
