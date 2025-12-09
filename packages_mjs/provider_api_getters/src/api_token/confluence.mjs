/**
 * Confluence API token getter.
 *
 * Confluence Cloud uses Basic Authentication with email:api_token format.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

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
   * Get the environment variable name for the email.
   * @returns {string}
   */
  _getEmailEnvVarName() {
    logger.debug('ConfluenceApiToken._getEmailEnvVarName: Getting email env var name');

    const providerConfig = this._getProviderConfig();
    const envEmail = providerConfig?.env_email || DEFAULT_EMAIL_ENV_VAR;

    logger.debug(
      `ConfluenceApiToken._getEmailEnvVarName: Using env var '${envEmail}' ` +
      `(fromConfig=${providerConfig?.env_email !== undefined})`
    );

    return envEmail;
  }

  /**
   * Get Confluence email from environment.
   * Checks CONFLUENCE_EMAIL first, then falls back to JIRA_EMAIL.
   * @returns {string|null}
   */
  _getEmail() {
    logger.debug('ConfluenceApiToken._getEmail: Getting email from environment');

    const envEmailName = this._getEmailEnvVarName();
    let email = process.env[envEmailName] || null;

    if (email) {
      const maskedEmail = email.length > 3
        ? `${email.substring(0, 3)}***@***`
        : '***@***';
      logger.debug(
        `ConfluenceApiToken._getEmail: Found email in env var '${envEmailName}': '${maskedEmail}' (masked)`
      );
      return email;
    }

    // Fallback to JIRA_EMAIL (same Atlassian account)
    logger.debug(
      `ConfluenceApiToken._getEmail: Env var '${envEmailName}' not set, ` +
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
        `ConfluenceApiToken._getEmail: Neither '${envEmailName}' nor ` +
        `'${FALLBACK_EMAIL_ENV_VAR}' is set`
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
   * @param {string} email
   * @param {string} token
   * @returns {string}
   */
  _encodeBasicAuth(email, token) {
    logger.debug('ConfluenceApiToken._encodeBasicAuth: Encoding credentials');

    if (!email || !token) {
      logger.error(
        `ConfluenceApiToken._encodeBasicAuth: Invalid inputs - ` +
        `emailEmpty=${!email}, tokenEmpty=${!token}`
      );
      throw new Error('Both email and token are required for Basic Auth encoding');
    }

    const credentials = `${email}:${token}`;
    const encoded = Buffer.from(credentials).toString('base64');

    logger.debug(
      `ConfluenceApiToken._encodeBasicAuth: Encoded credentials (length=${encoded.length})`
    );

    return `Basic ${encoded}`;
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
}
