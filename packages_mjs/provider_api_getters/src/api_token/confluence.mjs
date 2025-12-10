/**
 * Confluence API token getter.
 *
 * Confluence Cloud uses Basic Authentication with email:api_token format.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';
import { AuthHeaderFactory } from './auth_header_factory.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.confluence: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.confluence: ${msg}`),
  error: (msg) => console.error(`[ERROR] provider_api_getters.confluence: ${msg}`),
};

// Default environment variable names
const DEFAULT_EMAIL_ENV_VAR = 'CONFLUENCE_EMAIL';
const DEFAULT_BASE_URL_ENV_VAR = 'CONFLUENCE_BASE_URL';

// Fallback to Jira credentials (same Atlassian account)
const FALLBACK_EMAIL_ENV_VAR = 'JIRA_EMAIL';
const FALLBACK_API_TOKEN_ENV_VAR = 'JIRA_API_TOKEN';
const FALLBACK_BASE_URL_ENV_VAR = 'JIRA_BASE_URL';

export class ConfluenceApiToken extends BaseApiToken {
  get providerName() {
    return 'confluence';
  }

  get healthEndpoint() {
    // Note: base_url already includes /wiki path
    logger.debug('ConfluenceApiToken.healthEndpoint: Returning /rest/api/user/current');
    return '/rest/api/user/current';
  }

  /**
   * Get Confluence email from environment.
   * Uses base class _lookupEmail() which reads from env_email in YAML config.
   * Falls back to DEFAULT_EMAIL_ENV_VAR, then FALLBACK_EMAIL_ENV_VAR (JIRA_EMAIL).
   * @returns {string|null}
   */
  _getEmail() {
    logger.debug('ConfluenceApiToken._getEmail: Getting email from environment');

    // Try base class lookup (from env_email in config)
    let email = this._lookupEmail();

    if (email) {
      const maskedEmail = email.length > 3
        ? `${email.substring(0, 3)}***@***`
        : '***@***';
      logger.debug(
        `ConfluenceApiToken._getEmail: Found email via base class lookup: '${maskedEmail}' (masked)`
      );
      return email;
    }

    // Fall back to default env var
    logger.debug(
      `ConfluenceApiToken._getEmail: Base class lookup returned null, ` +
      `trying default env var '${DEFAULT_EMAIL_ENV_VAR}'`
    );
    email = process.env[DEFAULT_EMAIL_ENV_VAR] || null;

    if (email) {
      const maskedEmail = email.length > 3
        ? `${email.substring(0, 3)}***@***`
        : '***@***';
      logger.debug(
        `ConfluenceApiToken._getEmail: Found email in default env var ` +
        `'${DEFAULT_EMAIL_ENV_VAR}': '${maskedEmail}' (masked)`
      );
      return email;
    }

    // Fallback to JIRA_EMAIL (same Atlassian account)
    logger.debug(
      `ConfluenceApiToken._getEmail: Default env var not set, ` +
      `trying fallback '${FALLBACK_EMAIL_ENV_VAR}'`
    );
    email = process.env[FALLBACK_EMAIL_ENV_VAR] || null;

    if (email) {
      const maskedEmail = email.length > 3
        ? `${email.substring(0, 3)}***@***`
        : '***@***';
      logger.debug(
        `ConfluenceApiToken._getEmail: Found email in fallback env var ` +
        `'${FALLBACK_EMAIL_ENV_VAR}': '${maskedEmail}' (masked)`
      );
    } else {
      logger.debug(
        `ConfluenceApiToken._getEmail: Neither default nor fallback env vars are set`
      );
    }

    return email;
  }

  /**
   * Lookup API token from environment variable.
   * Checks CONFLUENCE_API_TOKEN first, then falls back to JIRA_API_TOKEN.
   * @returns {string|null}
   */
  _lookupEnvApiKey() {
    logger.debug('ConfluenceApiToken._lookupEnvApiKey: Looking up API token');

    // First try the standard lookup (CONFLUENCE_API_TOKEN)
    const apiToken = super._lookupEnvApiKey();

    if (apiToken) {
      return apiToken;
    }

    // Fallback to JIRA_API_TOKEN (same Atlassian account)
    logger.debug(
      `ConfluenceApiToken._lookupEnvApiKey: Primary env var not set, ` +
      `trying fallback '${FALLBACK_API_TOKEN_ENV_VAR}'`
    );
    const fallbackToken = process.env[FALLBACK_API_TOKEN_ENV_VAR] || null;

    if (fallbackToken) {
      logger.debug(
        `ConfluenceApiToken._lookupEnvApiKey: Found API token in fallback env var ` +
        `'${FALLBACK_API_TOKEN_ENV_VAR}' (length=${fallbackToken.length})`
      );
    } else {
      logger.debug(
        `ConfluenceApiToken._lookupEnvApiKey: Fallback env var ` +
        `'${FALLBACK_API_TOKEN_ENV_VAR}' is also not set`
      );
    }

    return fallbackToken;
  }

  /**
   * Encode email and token for Basic Authentication.
   * Uses AuthHeaderFactory for RFC-compliant encoding.
   * @param {string} email
   * @param {string} token
   * @returns {string}
   */
  _encodeBasicAuth(email, token) {
    logger.debug('ConfluenceApiToken._encodeBasicAuth: Encoding credentials via AuthHeaderFactory');

    if (!email || !token) {
      logger.error(
        `ConfluenceApiToken._encodeBasicAuth: Invalid inputs - ` +
        `emailEmpty=${!email}, tokenEmpty=${!token}`
      );
      throw new Error('Both email and token are required for Basic Auth encoding');
    }

    const authHeader = AuthHeaderFactory.createBasic(email, token);

    logger.debug(
      `ConfluenceApiToken._encodeBasicAuth: Encoded credentials (length=${authHeader.headerValue.length})`
    );

    return authHeader.headerValue;
  }

  getApiKey() {
    logger.debug('ConfluenceApiToken.getApiKey: Starting API key resolution');

    const apiToken = this._lookupEnvApiKey();
    const email = this._getEmail();

    // Log the state of both required credentials
    logger.debug(
      `ConfluenceApiToken.getApiKey: Credential state - ` +
      `hasToken=${apiToken !== null}, hasEmail=${email !== null}`
    );

    let result;

    if (apiToken && email) {
      logger.debug(
        'ConfluenceApiToken.getApiKey: Both email and token found, encoding Basic Auth credentials'
      );
      try {
        const encodedAuth = this._encodeBasicAuth(email, apiToken);
        const maskedEmail = email.length > 3
          ? `${email.substring(0, 3)}***@***`
          : '***@***';
        result = new ApiKeyResult({
          apiKey: encodedAuth,
          authType: 'basic',
          headerName: 'Authorization',
          username: email,
          email: email,
          rawApiKey: apiToken,
        });
        logger.debug(
          `ConfluenceApiToken.getApiKey: Successfully created Basic Auth result for user '${maskedEmail}'`
        );
      } catch (e) {
        logger.error(`ConfluenceApiToken.getApiKey: Failed to encode credentials: ${e.message}`);
        result = new ApiKeyResult({
          apiKey: null,
          authType: 'basic',
          headerName: 'Authorization',
          username: email,
          email: email,
          rawApiKey: apiToken,
        });
      }
    } else if (apiToken && !email) {
      logger.warn(
        'ConfluenceApiToken.getApiKey: API token found but email is missing. ' +
        'Set CONFLUENCE_EMAIL environment variable.'
      );
      result = new ApiKeyResult({
        apiKey: null,
        authType: 'basic',
        headerName: 'Authorization',
        username: null,
        email: null,
        rawApiKey: apiToken,
      });
    } else if (email && !apiToken) {
      logger.warn(
        'ConfluenceApiToken.getApiKey: Email found but API token is missing. ' +
        'Set CONFLUENCE_API_TOKEN environment variable.'
      );
      result = new ApiKeyResult({
        apiKey: null,
        authType: 'basic',
        headerName: 'Authorization',
        username: email,
        email: email,
        rawApiKey: null,
      });
    } else {
      logger.warn(
        'ConfluenceApiToken.getApiKey: Neither email nor token found. ' +
        'Set both CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN environment variables.'
      );
      result = new ApiKeyResult({
        apiKey: null,
        authType: 'basic',
        headerName: 'Authorization',
        username: null,
        email: null,
        rawApiKey: null,
      });
    }

    logger.debug(
      `ConfluenceApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
    );
    return result;
  }

  getBaseUrl() {
    logger.debug('ConfluenceApiToken.getBaseUrl: Getting base URL');

    // First try the standard config resolution
    let baseUrl = super.getBaseUrl();

    if (baseUrl) {
      logger.debug(`ConfluenceApiToken.getBaseUrl: Found base URL from config: '${baseUrl}'`);
      return baseUrl;
    }

    // Fall back to CONFLUENCE_BASE_URL env var
    logger.debug(
      `ConfluenceApiToken.getBaseUrl: Checking env var '${DEFAULT_BASE_URL_ENV_VAR}'`
    );
    baseUrl = process.env[DEFAULT_BASE_URL_ENV_VAR] || null;

    if (baseUrl) {
      logger.debug(`ConfluenceApiToken.getBaseUrl: Found base URL from env var: '${baseUrl}'`);
      return baseUrl;
    }

    // Fallback: derive from JIRA_BASE_URL (append /wiki)
    logger.debug(
      `ConfluenceApiToken.getBaseUrl: Checking fallback env var '${FALLBACK_BASE_URL_ENV_VAR}'`
    );
    const jiraBaseUrl = process.env[FALLBACK_BASE_URL_ENV_VAR] || null;

    if (jiraBaseUrl) {
      // Remove trailing slash and append /wiki
      baseUrl = jiraBaseUrl.replace(/\/+$/, '') + '/wiki';
      logger.debug(
        `ConfluenceApiToken.getBaseUrl: Derived base URL from JIRA_BASE_URL: '${baseUrl}'`
      );
      return baseUrl;
    }

    logger.warn(
      `ConfluenceApiToken.getBaseUrl: No base URL configured. ` +
      `Set ${DEFAULT_BASE_URL_ENV_VAR} or ${FALLBACK_BASE_URL_ENV_VAR} environment variable.`
    );

    return null;
  }

  /**
   * Get provider-specific network/proxy configuration.
   *
   * Reads from YAML config fields:
   * - proxy_url: Proxy URL for requests
   * - ca_bundle: CA bundle path for SSL verification
   * - cert: Client certificate path
   * - cert_verify: SSL certificate verification flag
   * - agent_proxy.http_proxy: HTTP proxy for agent
   * - agent_proxy.https_proxy: HTTPS proxy for agent
   *
   * @returns {Object} Network configuration values
   */
  getNetworkConfig() {
    logger.debug('ConfluenceApiToken.getNetworkConfig: Getting network configuration');

    const providerConfig = this._getProviderConfig();

    // Get agent_proxy nested config
    const agentProxy = providerConfig.agent_proxy || {};

    const config = {
      proxyUrl: providerConfig.proxy_url || null,
      caBundle: providerConfig.ca_bundle || null,
      cert: providerConfig.cert || null,
      certVerify: providerConfig.cert_verify ?? false,
      agentProxy: {
        httpProxy: agentProxy.http_proxy || null,
        httpsProxy: agentProxy.https_proxy || null,
      },
    };

    logger.debug(
      `ConfluenceApiToken.getNetworkConfig: Resolved config - ` +
      `proxyUrl=${config.proxyUrl}, ` +
      `caBundle=${config.caBundle}, ` +
      `cert=${config.cert}, ` +
      `certVerify=${config.certVerify}, ` +
      `agentProxy=${JSON.stringify(config.agentProxy)}`
    );

    return config;
  }

  /**
   * Get service configuration from static config.
   * @returns {Object} Service configuration from .services.{providerName}
   * @private
   */
  _getServiceConfig() {
    logger.debug(`ConfluenceApiToken._getServiceConfig: Getting service config for '${this.providerName}'`);

    try {
      const config = this.configStore.getNested('services', this.providerName);
      if (config === null || config === undefined) {
        logger.debug('ConfluenceApiToken._getServiceConfig: No service config found, returning empty object');
        return {};
      }
      logger.debug(`ConfluenceApiToken._getServiceConfig: Found service config with keys: ${Object.keys(config)}`);
      return config;
    } catch (e) {
      logger.error(`ConfluenceApiToken._getServiceConfig: Exception while getting config: ${e.message}`);
      return {};
    }
  }

  /**
   * Get downstream service configuration.
   *
   * Returns the entire service configuration dictionary from .services.confluence
   * which can contain arbitrary key-value pairs for downstream service config.
   *
   * @returns {Object} Dictionary with all service configuration values
   */
  getServiceConfig() {
    logger.debug('ConfluenceApiToken.getServiceConfig: Getting service configuration');

    const serviceConfig = this._getServiceConfig();

    logger.debug(
      `ConfluenceApiToken.getServiceConfig: Returning config with ` +
      `${Object.keys(serviceConfig).length} keys: ${Object.keys(serviceConfig)}`
    );

    return serviceConfig;
  }

  /**
   * Get environment variable value by name from service config.
   *
   * Looks up env_{name} in the service config to get the environment variable name,
   * then resolves the actual value from the environment.
   *
   * Example:
   *   YAML config:
   *     services:
   *       confluence:
   *         env_space_key: "CONFLUENCE_SPACE_KEY"
   *
   *   Code:
   *     const spaceKey = provider.getEnvByName("space_key");
   *     // Reads env var name from config: "CONFLUENCE_SPACE_KEY"
   *     // Returns process.env.CONFLUENCE_SPACE_KEY
   *
   * @param {string} name - The name suffix (without 'env_' prefix)
   * @param {string|null} defaultValue - Default value if env var is not set
   * @returns {string|null} Environment variable value or default
   */
  getEnvByName(name, defaultValue = null) {
    logger.debug(`ConfluenceApiToken.getEnvByName: Looking up env_${name}`);

    const serviceConfig = this._getServiceConfig();
    const envKey = `env_${name}`;
    const envVarName = serviceConfig[envKey];

    if (!envVarName) {
      logger.debug(
        `ConfluenceApiToken.getEnvByName: No '${envKey}' found in service config, ` +
        `returning default: ${defaultValue}`
      );
      return defaultValue;
    }

    const value = process.env[envVarName] || defaultValue;

    logger.debug(
      `ConfluenceApiToken.getEnvByName: Resolved ${envKey}='${envVarName}' -> ` +
      `value=${value ? '<set>' : '<not set>'}`
    );

    return value;
  }

  /**
   * Get default headers from service configuration.
   * @returns {Object} Dictionary of default headers for API requests
   */
  getHeaders() {
    logger.debug('ConfluenceApiToken.getHeaders: Getting default headers');

    const serviceConfig = this._getServiceConfig();
    const headers = serviceConfig.headers || {};

    logger.debug(
      `ConfluenceApiToken.getHeaders: Found ${Object.keys(headers).length} headers: ${Object.keys(headers)}`
    );

    return headers;
  }

  /**
   * Get API endpoints from service configuration.
   * @returns {Object} Dictionary of endpoint paths
   */
  getEndpoints() {
    logger.debug('ConfluenceApiToken.getEndpoints: Getting endpoints');

    const serviceConfig = this._getServiceConfig();
    const endpoints = serviceConfig.endpoints || {};

    logger.debug(
      `ConfluenceApiToken.getEndpoints: Found ${Object.keys(endpoints).length} endpoints: ${Object.keys(endpoints)}`
    );

    return endpoints;
  }

  /**
   * Get pagination defaults from service configuration.
   * @returns {Object} Dictionary with pagination settings (limit, start, etc.)
   */
  getPaginationDefaults() {
    logger.debug('ConfluenceApiToken.getPaginationDefaults: Getting pagination defaults');

    const serviceConfig = this._getServiceConfig();
    const pagination = serviceConfig.pagination || {};

    logger.debug(
      `ConfluenceApiToken.getPaginationDefaults: Found pagination config: ${JSON.stringify(pagination)}`
    );

    return pagination;
  }
}
