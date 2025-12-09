/**
 * SauceLabs API token getter.
 *
 * SauceLabs uses Basic authentication with username:access_key.
 * Fallbacks are configured in server.{APP_ENV}.yaml under providers.saucelabs.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';
import { AuthHeaderFactory } from './auth_header_factory.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.saucelabs: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.saucelabs: ${msg}`),
};

export class SaucelabsApiToken extends BaseApiToken {
  get providerName() {
    return 'saucelabs';
  }

  get healthEndpoint() {
    const { username } = this._lookupUsername();
    if (username) {
      const endpoint = `/rest/v1/users/${username}`;
      logger.debug(`SaucelabsApiToken.healthEndpoint: Returning ${endpoint}`);
      return endpoint;
    }
    // Fallback - will fail but provide meaningful error
    logger.debug('SaucelabsApiToken.healthEndpoint: No username found, returning placeholder');
    return '/rest/v1/users/:username';
  }

  /**
   * Get username environment variable names from config.
   * @returns {string[]}
   */
  _getUsernameEnvVars() {
    const providerConfig = this._getProviderConfig();
    const primary = providerConfig?.env_username;
    const fallbacks = providerConfig?.env_username_fallbacks || [];

    if (primary) {
      return [primary, ...fallbacks];
    }
    return fallbacks;
  }

  /**
   * Get access key environment variable names from config.
   * @returns {string[]}
   */
  _getAccessKeyEnvVars() {
    const primary = this._getEnvApiKeyName();
    const fallbacks = this._getEnvApiKeyFallbacks();

    if (primary) {
      return [primary, ...fallbacks];
    }
    return fallbacks;
  }

  /**
   * Lookup SauceLabs username from environment.
   * @returns {{username: string|null, sourceVar: string|null}}
   */
  _lookupUsername() {
    const envVars = this._getUsernameEnvVars();
    for (const envVar of envVars) {
      const username = process.env[envVar];
      if (username) {
        logger.debug(`SaucelabsApiToken._lookupUsername: Found username in '${envVar}'`);
        return { username, sourceVar: envVar };
      }
    }
    return { username: null, sourceVar: null };
  }

  /**
   * Lookup SauceLabs access key from environment.
   * @returns {{accessKey: string|null, sourceVar: string|null}}
   */
  _lookupAccessKey() {
    const envVars = this._getAccessKeyEnvVars();
    for (const envVar of envVars) {
      const accessKey = process.env[envVar];
      if (accessKey) {
        logger.debug(`SaucelabsApiToken._lookupAccessKey: Found access key in '${envVar}'`);
        return { accessKey, sourceVar: envVar };
      }
    }
    return { accessKey: null, sourceVar: null };
  }

  getApiKey() {
    logger.debug('SaucelabsApiToken.getApiKey: Starting API key resolution');

    const { username, sourceVar: usernameVar } = this._lookupUsername();
    const { accessKey, sourceVar: accessKeyVar } = this._lookupAccessKey();

    if (username && accessKey) {
      // Use AuthHeaderFactory for RFC-compliant Basic auth encoding
      const authHeader = AuthHeaderFactory.createBasic(username, accessKey);
      logger.debug(
        `SaucelabsApiToken.getApiKey: Found credentials from ` +
        `'${usernameVar}' and '${accessKeyVar}' (masked=${maskSensitive(`${username}:${accessKey}`)})`
      );
      const result = new ApiKeyResult({
        apiKey: authHeader.headerValue,
        authType: 'basic',
        headerName: 'Authorization',
        username: username,
        email: username,
        rawApiKey: accessKey,
      });
      logger.debug(
        `SaucelabsApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    } else {
      const missing = [];
      if (!username) {
        const usernameVars = this._getUsernameEnvVars();
        missing.push(`username (${usernameVars.join(', ')})`);
      }
      if (!accessKey) {
        const accessKeyVars = this._getAccessKeyEnvVars();
        missing.push(`access_key (${accessKeyVars.join(', ')})`);
      }
      logger.warn(`SaucelabsApiToken.getApiKey: Missing credentials: ${missing.join(', ')}`);
      const result = new ApiKeyResult({
        apiKey: null,
        authType: 'basic',
        headerName: 'Authorization',
        email: username,
        rawApiKey: accessKey,
      });
      logger.debug(
        `SaucelabsApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
      );
      return result;
    }
  }
}
