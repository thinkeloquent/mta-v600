/**
 * Jira API token getter.
 *
 * Jira Cloud uses Basic Authentication with email:api_token format.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.jira: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.jira: ${msg}`),
  error: (msg) => console.error(`[ERROR] provider_api_getters.jira: ${msg}`),
};

// Default environment variable names
const DEFAULT_EMAIL_ENV_VAR = 'JIRA_EMAIL';
const DEFAULT_BASE_URL_ENV_VAR = 'JIRA_BASE_URL';

export class JiraApiToken extends BaseApiToken {
  get providerName() {
    return 'jira';
  }

  get healthEndpoint() {
    logger.debug('JiraApiToken.healthEndpoint: Returning /rest/api/2/myself');
    return '/rest/api/2/myself';
  }

  /**
   * Get the environment variable name for the email.
   * @returns {string}
   */
  _getEmailEnvVarName() {
    logger.debug('JiraApiToken._getEmailEnvVarName: Getting email env var name');

    const providerConfig = this._getProviderConfig();
    const envEmail = providerConfig?.env_email || DEFAULT_EMAIL_ENV_VAR;

    logger.debug(
      `JiraApiToken._getEmailEnvVarName: Using env var '${envEmail}' ` +
      `(fromConfig=${providerConfig?.env_email !== undefined})`
    );

    return envEmail;
  }

  /**
   * Get Jira email from environment.
   * @returns {string|null}
   */
  _getEmail() {
    logger.debug('JiraApiToken._getEmail: Getting email from environment');

    const envEmailName = this._getEmailEnvVarName();
    const email = process.env[envEmailName] || null;

    if (email) {
      const maskedEmail = email.length > 3
        ? `${email.substring(0, 3)}***@***`
        : '***@***';
      logger.debug(
        `JiraApiToken._getEmail: Found email in env var '${envEmailName}': '${maskedEmail}' (masked)`
      );
    } else {
      logger.debug(
        `JiraApiToken._getEmail: Env var '${envEmailName}' is not set`
      );
    }

    return email;
  }

  /**
   * Encode email and token for Basic Authentication.
   * @param {string} email
   * @param {string} token
   * @returns {string}
   */
  _encodeBasicAuth(email, token) {
    logger.debug('JiraApiToken._encodeBasicAuth: Encoding credentials');

    if (!email || !token) {
      logger.error(
        `JiraApiToken._encodeBasicAuth: Invalid inputs - ` +
        `emailEmpty=${!email}, tokenEmpty=${!token}`
      );
      throw new Error('Both email and token are required for Basic Auth encoding');
    }

    const credentials = `${email}:${token}`;
    const encoded = Buffer.from(credentials).toString('base64');

    logger.debug(
      `JiraApiToken._encodeBasicAuth: Encoded credentials (length=${encoded.length})`
    );

    return `Basic ${encoded}`;
  }

  getApiKey() {
    logger.debug('JiraApiToken.getApiKey: Starting API key resolution');

    const apiToken = this._lookupEnvApiKey();
    const email = this._getEmail();

    // Log the state of both required credentials
    logger.debug(
      `JiraApiToken.getApiKey: Credential state - ` +
      `hasToken=${apiToken !== null}, hasEmail=${email !== null}`
    );

    let result;

    if (apiToken && email) {
      logger.debug(
        'JiraApiToken.getApiKey: Both email and token found, encoding Basic Auth credentials'
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
          `JiraApiToken.getApiKey: Successfully created Basic Auth result for user '${maskedEmail}'`
        );
      } catch (e) {
        logger.error(`JiraApiToken.getApiKey: Failed to encode credentials: ${e.message}`);
        result = new ApiKeyResult({
          apiKey: null,
          authType: 'basic',
          headerName: 'Authorization',
          username: email,
        });
      }
    } else if (apiToken && !email) {
      logger.warn(
        'JiraApiToken.getApiKey: API token found but email is missing. ' +
        'Set JIRA_EMAIL environment variable.'
      );
      result = new ApiKeyResult({
        apiKey: null,
        authType: 'basic',
        headerName: 'Authorization',
        username: null,
      });
    } else if (email && !apiToken) {
      logger.warn(
        'JiraApiToken.getApiKey: Email found but API token is missing. ' +
        'Set JIRA_API_TOKEN environment variable.'
      );
      result = new ApiKeyResult({
        apiKey: null,
        authType: 'basic',
        headerName: 'Authorization',
        username: email,
      });
    } else {
      logger.warn(
        'JiraApiToken.getApiKey: Neither email nor token found. ' +
        'Set both JIRA_EMAIL and JIRA_API_TOKEN environment variables.'
      );
      result = new ApiKeyResult({
        apiKey: null,
        authType: 'basic',
        headerName: 'Authorization',
        username: null,
      });
    }

    logger.debug(
      `JiraApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`
    );
    return result;
  }

  getBaseUrl() {
    logger.debug('JiraApiToken.getBaseUrl: Getting base URL');

    // First try the standard config resolution
    const baseUrl = super.getBaseUrl();

    if (baseUrl) {
      logger.debug(`JiraApiToken.getBaseUrl: Found base URL from config: '${baseUrl}'`);
      return baseUrl;
    }

    // Fall back to JIRA_BASE_URL env var
    logger.debug(
      `JiraApiToken.getBaseUrl: Checking fallback env var '${DEFAULT_BASE_URL_ENV_VAR}'`
    );
    const envBaseUrl = process.env[DEFAULT_BASE_URL_ENV_VAR] || null;

    if (envBaseUrl) {
      logger.debug(`JiraApiToken.getBaseUrl: Found base URL from env var: '${envBaseUrl}'`);
    } else {
      logger.warn(
        `JiraApiToken.getBaseUrl: No base URL configured. ` +
        `Set ${DEFAULT_BASE_URL_ENV_VAR} environment variable.`
      );
    }

    return envBaseUrl;
  }
}
