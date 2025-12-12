/**
 * Native Gemini API token getter.
 *
 * For the native Gemini API at https://generativelanguage.googleapis.com/v1beta/
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.gemini: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.gemini: ${msg}`),
};

// Default environment variable for Gemini API key
const DEFAULT_GEMINI_API_KEY_ENV = 'GEMINI_API_KEY';

export class GeminiApiToken extends BaseApiToken {
  get providerName() {
    return 'gemini';
  }

  get healthEndpoint() {
    // Native Gemini API models endpoint
    logger.debug('GeminiApiToken.healthEndpoint: Returning models');
    return 'models';
  }

  getApiKey() {
    logger.debug('GeminiApiToken.getApiKey: Starting API key resolution');

    // Try config-specified env var first
    let apiKey = this._lookupEnvApiKey();

    // Fall back to default GEMINI_API_KEY
    if (!apiKey) {
      logger.debug(
        `GeminiApiToken.getApiKey: Config lookup failed, ` +
        `trying default env var '${DEFAULT_GEMINI_API_KEY_ENV}'`
      );
      apiKey = process.env[DEFAULT_GEMINI_API_KEY_ENV];
    }

    if (apiKey) {
      logger.debug(
        `GeminiApiToken.getApiKey: Found API key ` +
        `(length=${apiKey.length}, masked=${maskSensitive(apiKey)})`
      );
      const result = new ApiKeyResult({
        apiKey,
        authType: 'bearer',
        headerName: 'Authorization',
        email: null,
        rawApiKey: apiKey,
      });
      logger.debug(
        `GeminiApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    } else {
      logger.warn(
        'GeminiApiToken.getApiKey: No API key found. ' +
        `Ensure ${DEFAULT_GEMINI_API_KEY_ENV} environment variable is set.`
      );
      const result = new ApiKeyResult({
        apiKey: null,
        authType: 'bearer',
        headerName: 'Authorization',
        email: null,
        rawApiKey: null,
      });
      logger.debug(
        `GeminiApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
