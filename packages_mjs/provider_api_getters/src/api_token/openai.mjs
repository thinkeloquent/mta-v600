/**
 * OpenAI API token getter.
 *
 * Supports OpenAI API.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.openai: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.openai: ${msg}`),
};

// Default environment variable for OpenAI API key
const DEFAULT_OPENAI_API_KEY_ENV = 'OPENAI_API_KEY';

export class OpenAIApiToken extends BaseApiToken {
  get providerName() {
    return 'openai';
  }

  get healthEndpoint() {
    // OpenAI models endpoint
    logger.debug('OpenAIApiToken.healthEndpoint: Returning /models');
    return '/models';
  }

  getApiKey() {
    logger.debug('OpenAIApiToken.getApiKey: Starting API key resolution');

    // Try config-specified env var first
    let apiKey = this._lookupEnvApiKey();

    // Fall back to default OPENAI_API_KEY
    if (!apiKey) {
      logger.debug(
        `OpenAIApiToken.getApiKey: Config lookup failed, ` +
        `trying default env var '${DEFAULT_OPENAI_API_KEY_ENV}'`
      );
      apiKey = process.env[DEFAULT_OPENAI_API_KEY_ENV];
    }

    if (apiKey) {
      logger.debug(
        `OpenAIApiToken.getApiKey: Found API key ` +
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
        `OpenAIApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    } else {
      logger.warn(
        'OpenAIApiToken.getApiKey: No API key found. ' +
        `Ensure ${DEFAULT_OPENAI_API_KEY_ENV} environment variable is set.`
      );
      const result = new ApiKeyResult({
        apiKey: null,
        authType: 'bearer',
        headerName: 'Authorization',
        email: null,
        rawApiKey: null,
      });
      logger.debug(
        `OpenAIApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
