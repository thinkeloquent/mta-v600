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

  get _defaultAuthType() {
    return 'custom';
  }

  get _defaultHeaderName() {
    return 'X-Figma-Token';
  }

  get healthEndpoint() {
    // Note: base_url already includes /v1
    logger.debug('FigmaApiToken.healthEndpoint: Returning /me');
    return '/me';
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
        authType: 'custom',
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
        authType: 'custom',
        headerName: 'X-Figma-Token',
      });
      logger.debug(
        `FigmaApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
