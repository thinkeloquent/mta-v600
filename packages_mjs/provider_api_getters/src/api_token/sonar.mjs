/**
 * Sonar API token getter.
 *
 * This module provides API token resolution for SonarQube/SonarCloud APIs.
 * Supports multiple fallback environment variable names for flexibility.
 * Fallbacks are configured in server.{APP_ENV}.yaml under providers.sonar.env_api_key_fallbacks.
 *
 * Authentication:
 *     SonarQube/SonarCloud uses Bearer token authentication.
 *     Token is passed in the Authorization header: "Bearer <token>"
 *
 * API Documentation:
 *     SonarCloud: https://sonarcloud.io/web_api
 *     SonarQube: https://docs.sonarqube.org/latest/extension-guide/web-api/
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.sonar: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.sonar: ${msg}`),
};

// Default fallback environment variable names for Sonar tokens
const SONAR_FALLBACK_ENV_VARS = [
  'SONARQUBE_TOKEN',
  'SONARCLOUD_TOKEN',
  'SONAR_API_TOKEN',
];

export class SonarApiToken extends BaseApiToken {
  get providerName() {
    return 'sonar';
  }

  get healthEndpoint() {
    logger.debug('SonarApiToken.healthEndpoint: Returning /api/authentication/validate');
    return '/api/authentication/validate';
  }

  /**
   * Get the list of fallback environment variable names from config.
   * @returns {string[]}
   */
  _getFallbackEnvVars() {
    const fallbacks = this._getEnvApiKeyFallbacks();
    if (fallbacks && fallbacks.length > 0) {
      return fallbacks;
    }
    return SONAR_FALLBACK_ENV_VARS;
  }

  /**
   * Lookup API key with fallbacks.
   * @returns {{apiKey: string|null, sourceVar: string|null}}
   */
  _lookupWithFallbacks() {
    logger.debug('SonarApiToken._lookupWithFallbacks: Starting lookup with fallbacks');

    // First try the configured env key
    const configuredKey = this._getEnvApiKeyName();
    if (configuredKey) {
      logger.debug(
        `SonarApiToken._lookupWithFallbacks: Checking configured env var '${configuredKey}'`
      );
      const apiKey = process.env[configuredKey];
      if (apiKey) {
        logger.debug(
          `SonarApiToken._lookupWithFallbacks: Found key in configured env var '${configuredKey}'`
        );
        return { apiKey, sourceVar: configuredKey };
      } else {
        logger.debug(
          `SonarApiToken._lookupWithFallbacks: Configured env var '${configuredKey}' is not set`
        );
      }
    }

    // Fall back to standard env var names
    const fallbackVars = this._getFallbackEnvVars();
    logger.debug(
      `SonarApiToken._lookupWithFallbacks: Checking ${fallbackVars.length} fallback env vars: ` +
      `[${fallbackVars.join(', ')}]`
    );

    for (let i = 0; i < fallbackVars.length; i++) {
      const envVar = fallbackVars[i];
      logger.debug(
        `SonarApiToken._lookupWithFallbacks: Checking fallback [${i + 1}/${fallbackVars.length}]: '${envVar}'`
      );
      const apiKey = process.env[envVar];
      if (apiKey) {
        logger.debug(
          `SonarApiToken._lookupWithFallbacks: Found key in fallback env var '${envVar}' ` +
          `(length=${apiKey.length}, masked=${maskSensitive(apiKey)})`
        );
        return { apiKey, sourceVar: envVar };
      } else {
        logger.debug(
          `SonarApiToken._lookupWithFallbacks: Fallback env var '${envVar}' is not set`
        );
      }
    }

    logger.debug('SonarApiToken._lookupWithFallbacks: No API key found in any env var');
    return { apiKey: null, sourceVar: null };
  }

  getApiKey() {
    logger.debug('SonarApiToken.getApiKey: Starting API key resolution');

    const { apiKey, sourceVar } = this._lookupWithFallbacks();

    // Get configured auth type from YAML config
    const configAuthType = this.getAuthType();
    logger.debug(`SonarApiToken.getApiKey: Config auth type = '${configAuthType}'`);

    if (apiKey) {
      logger.debug(
        `SonarApiToken.getApiKey: Found API key from '${sourceVar}' ` +
        `(length=${apiKey.length}, masked=${maskSensitive(apiKey)})`
      );
      const result = new ApiKeyResult({
        apiKey,
        authType: configAuthType,
        headerName: 'Authorization',
        email: null,
        rawApiKey: apiKey,
      });
      logger.debug(
        `SonarApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    } else {
      const configuredKey = this._getEnvApiKeyName();
      const fallbackVars = this._getFallbackEnvVars();
      const allVars = configuredKey ? [configuredKey, ...fallbackVars] : fallbackVars;
      logger.warn(
        'SonarApiToken.getApiKey: No API key found. ' +
        `Ensure one of these environment variables is set: [${allVars.join(', ')}]`
      );
      const result = new ApiKeyResult({
        apiKey: null,
        authType: configAuthType,
        headerName: 'Authorization',
        email: null,
        rawApiKey: null,
      });
      logger.debug(
        `SonarApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
