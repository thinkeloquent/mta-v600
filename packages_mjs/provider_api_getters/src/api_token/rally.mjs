/**
 * Rally (Broadcom) API token getter.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.rally: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.rally: ${msg}`),
};

// Default environment variables
const DEFAULT_RALLY_API_KEY_ENV = 'RALLY_API_KEY';
const DEFAULT_RALLY_Z_SESSION_ID_ENV = 'RALLY_Z_SESSION_ID';

export class RallyApiToken extends BaseApiToken {
  get providerName() {
    return 'rally';
  }

  get healthEndpoint() {
    // User endpoint to verify connectivity and auth
    return '/slm/webservice/v2.0/user';
  }

  getBaseUrl() {
    logger.debug('RallyApiToken.getBaseUrl: Getting base URL');

    // Try config first
    let baseUrl = super.getBaseUrl();

    // Default if not configured
    if (!baseUrl) {
      baseUrl = 'https://rally1.rallydev.com';
      logger.debug(`Using default base URL: ${baseUrl}`);
    }

    return baseUrl;
  }

  getApiKey() {
    logger.debug('RallyApiToken.getApiKey: Starting resolution');

    // Get API key from env
    let apiKey = this._lookupEnvApiKey();
    if (!apiKey) {
      apiKey = process.env[DEFAULT_RALLY_API_KEY_ENV];
    }
    if (!apiKey) {
      apiKey = process.env[DEFAULT_RALLY_Z_SESSION_ID_ENV];
    }

    if (apiKey) {
      logger.debug(
        `RallyApiToken.getApiKey: Found API key (length=${apiKey.length}, masked=${maskSensitive(apiKey)})`
      );
      return new ApiKeyResult({
        apiKey: apiKey,
        authType: 'header',
        headerName: 'Z-Session-ID',
        rawApiKey: apiKey,
      });
    }

    logger.warn('No API key found for Rally');
    return new ApiKeyResult({
      apiKey: null,
      authType: 'header',
      headerName: 'Z-Session-ID',
      rawApiKey: null,
      isPlaceholder: false,
    });
  }
}
