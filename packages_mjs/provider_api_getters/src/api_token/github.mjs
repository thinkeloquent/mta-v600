/**
 * GitHub API token getter.
 *
 * Supports multiple fallback environment variable names for flexibility.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.github: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.github: ${msg}`),
};

// Fallback environment variable names (in order of priority)
export const GITHUB_FALLBACK_ENV_VARS = [
  'GITHUB_TOKEN',
  'GH_TOKEN',
  'GITHUB_ACCESS_TOKEN',
  'GITHUB_PAT',
];

export class GithubApiToken extends BaseApiToken {
  get providerName() {
    return 'github';
  }

  get healthEndpoint() {
    logger.debug('GithubApiToken.healthEndpoint: Returning /user');
    return '/user';
  }

  /**
   * Get the list of fallback environment variable names.
   * @returns {string[]}
   */
  _getFallbackEnvVars() {
    return GITHUB_FALLBACK_ENV_VARS;
  }

  /**
   * Lookup API key with fallbacks.
   * @returns {{apiKey: string|null, sourceVar: string|null}}
   */
  _lookupWithFallbacks() {
    logger.debug('GithubApiToken._lookupWithFallbacks: Starting lookup with fallbacks');

    // First try the configured env key
    const configuredKey = this._getEnvApiKeyName();
    if (configuredKey) {
      logger.debug(
        `GithubApiToken._lookupWithFallbacks: Checking configured env var '${configuredKey}'`
      );
      const apiKey = process.env[configuredKey];
      if (apiKey) {
        logger.debug(
          `GithubApiToken._lookupWithFallbacks: Found key in configured env var '${configuredKey}'`
        );
        return { apiKey, sourceVar: configuredKey };
      } else {
        logger.debug(
          `GithubApiToken._lookupWithFallbacks: Configured env var '${configuredKey}' is not set`
        );
      }
    }

    // Fall back to standard env var names
    const fallbackVars = this._getFallbackEnvVars();
    logger.debug(
      `GithubApiToken._lookupWithFallbacks: Checking ${fallbackVars.length} fallback env vars: ` +
      `[${fallbackVars.join(', ')}]`
    );

    for (let i = 0; i < fallbackVars.length; i++) {
      const envVar = fallbackVars[i];
      logger.debug(
        `GithubApiToken._lookupWithFallbacks: Checking fallback [${i + 1}/${fallbackVars.length}]: '${envVar}'`
      );
      const apiKey = process.env[envVar];
      if (apiKey) {
        logger.debug(
          `GithubApiToken._lookupWithFallbacks: Found key in fallback env var '${envVar}' ` +
          `(length=${apiKey.length}, masked=${maskSensitive(apiKey)})`
        );
        return { apiKey, sourceVar: envVar };
      } else {
        logger.debug(
          `GithubApiToken._lookupWithFallbacks: Fallback env var '${envVar}' is not set`
        );
      }
    }

    logger.debug('GithubApiToken._lookupWithFallbacks: No API key found in any env var');
    return { apiKey: null, sourceVar: null };
  }

  getApiKey() {
    logger.debug('GithubApiToken.getApiKey: Starting API key resolution');

    const { apiKey, sourceVar } = this._lookupWithFallbacks();

    if (apiKey) {
      logger.debug(
        `GithubApiToken.getApiKey: Found API key from '${sourceVar}' ` +
        `(length=${apiKey.length}, masked=${maskSensitive(apiKey)})`
      );
      const result = new ApiKeyResult({
        apiKey,
        authType: 'bearer',
        headerName: 'Authorization',
      });
      logger.debug(
        `GithubApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    } else {
      logger.warn(
        'GithubApiToken.getApiKey: No API key found. ' +
        `Ensure one of these environment variables is set: [${GITHUB_FALLBACK_ENV_VARS.join(', ')}]`
      );
      const result = new ApiKeyResult({
        apiKey: null,
        authType: 'bearer',
        headerName: 'Authorization',
      });
      logger.debug(
        `GithubApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
