/**
 * Gemini/OpenAI API token getter.
 *
 * Supports OpenAI-compatible APIs including Gemini.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.gemini: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.gemini: ${msg}`),
};

// Default environment variable for Gemini API key
const DEFAULT_GEMINI_API_KEY_ENV = 'GEMINI_API_KEY';

export class GeminiOpenAIApiToken extends BaseApiToken {
  get providerName() {
    return 'gemini';
  }

  get healthEndpoint() {
    // Use relative path (without leading /) to preserve base_url path
    logger.debug('GeminiOpenAIApiToken.healthEndpoint: Returning models (relative)');
    return 'models';
  }

  getApiKey() {
    logger.debug('GeminiOpenAIApiToken.getApiKey: Starting API key resolution');

    // Try config-specified env var first
    let apiKey = this._lookupEnvApiKey();

    // Fall back to default GEMINI_API_KEY
    if (!apiKey) {
      logger.debug(
        `GeminiOpenAIApiToken.getApiKey: Config lookup failed, ` +
        `trying default env var '${DEFAULT_GEMINI_API_KEY_ENV}'`
      );
      apiKey = process.env[DEFAULT_GEMINI_API_KEY_ENV];
    }

    if (apiKey) {
      logger.debug(
        `GeminiOpenAIApiToken.getApiKey: Found API key ` +
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
        `GeminiOpenAIApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    } else {
      logger.warn(
        'GeminiOpenAIApiToken.getApiKey: No API key found. ' +
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
        `GeminiOpenAIApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
