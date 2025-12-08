/**
 * Figma API token getter.
 *
 * Figma uses the X-Figma-Token header for authentication.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.figma: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.figma: ${msg}`),
};

export class FigmaApiToken extends BaseApiToken {
  get providerName() {
    return 'figma';
  }

  get healthEndpoint() {
    logger.debug('FigmaApiToken.healthEndpoint: Returning /v1/me');
    return '/v1/me';
  }

  getApiKey() {
    logger.debug('FigmaApiToken.getApiKey: Starting API key resolution');

    const apiKey = this._lookupEnvApiKey();

    if (apiKey) {
      logger.debug(
        `FigmaApiToken.getApiKey: Found API key ` +
        `(length=${apiKey.length}, masked=${maskSensitive(apiKey)})`
      );
      const result = new ApiKeyResult({
        apiKey,
        authType: 'x-api-key',
        headerName: 'X-Figma-Token',
      });
      logger.debug(
        `FigmaApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    } else {
      logger.warn(
        'FigmaApiToken.getApiKey: No API key found. ' +
        'Ensure FIGMA_TOKEN environment variable is set.'
      );
      const result = new ApiKeyResult({
        apiKey: null,
        authType: 'x-api-key',
        headerName: 'X-Figma-Token',
      });
      logger.debug(
        `FigmaApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
