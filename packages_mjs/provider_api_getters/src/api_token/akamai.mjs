/**
 * Akamai Edge API token getter.
 *
 * This module provides API token resolution for Akamai Edge APIs.
 * Akamai uses EdgeGrid authentication, which requires:
 * - client_token
 * - client_secret
 * - access_token
 * - host
 *
 * These can be provided via environment variables or .edgerc file.
 *
 * API Documentation:
 *     https://techdocs.akamai.com/developer/docs/authenticate-with-edgegrid
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';
import { existsSync, readFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

// Simple logger
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters.akamai: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters.akamai: ${msg}`),
};

// Default .edgerc file location
const DEFAULT_EDGERC_PATH = join(homedir(), '.edgerc');

/**
 * EdgeGrid credentials container.
 */
class EdgeGridCredentials {
  constructor({ clientToken = null, clientSecret = null, accessToken = null, host = null } = {}) {
    this.clientToken = clientToken;
    this.clientSecret = clientSecret;
    this.accessToken = accessToken;
    this.host = host;
  }

  get isValid() {
    return !!(this.clientToken && this.clientSecret && this.accessToken && this.host);
  }
}

/**
 * Parse .edgerc INI file format.
 * @param {string} content - File content
 * @param {string} section - Section name to parse
 * @returns {Object} - Parsed key-value pairs
 */
function parseEdgerc(content, section = 'default') {
  const result = {};
  let currentSection = null;

  for (const line of content.split('\n')) {
    const trimmed = line.trim();

    // Skip empty lines and comments
    if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith(';')) {
      continue;
    }

    // Check for section header
    const sectionMatch = trimmed.match(/^\[([^\]]+)\]$/);
    if (sectionMatch) {
      currentSection = sectionMatch[1];
      continue;
    }

    // Parse key = value
    if (currentSection === section) {
      const eqIndex = trimmed.indexOf('=');
      if (eqIndex !== -1) {
        const key = trimmed.slice(0, eqIndex).trim();
        const value = trimmed.slice(eqIndex + 1).trim();
        result[key] = value;
      }
    }
  }

  return result;
}

export class AkamaiApiToken extends BaseApiToken {
  get providerName() {
    return 'akamai';
  }

  get healthEndpoint() {
    logger.debug('AkamaiApiToken.healthEndpoint: Returning /-/client-api/active-grants/implicit');
    return '/-/client-api/active-grants/implicit';
  }

  /**
   * Get environment variable name from config for a specific key.
   * @param {string} key
   * @returns {string|null}
   */
  _getEnvVarName(key) {
    const providerConfig = this._getProviderConfig();
    if (providerConfig) {
      return providerConfig[`env_${key}`] || null;
    }
    return null;
  }

  /**
   * Get EdgeGrid credentials from environment variables.
   * @returns {EdgeGridCredentials}
   */
  _getCredentialsFromEnv() {
    logger.debug('AkamaiApiToken._getCredentialsFromEnv: Checking environment variables');

    const clientTokenVar = this._getEnvVarName('client_token') || 'AKAMAI_CLIENT_TOKEN';
    const clientSecretVar = this._getEnvVarName('client_secret') || 'AKAMAI_CLIENT_SECRET';
    const accessTokenVar = this._getEnvVarName('access_token') || 'AKAMAI_ACCESS_TOKEN';
    const hostVar = this._getEnvVarName('host') || 'AKAMAI_HOST';

    const credentials = new EdgeGridCredentials({
      clientToken: process.env[clientTokenVar],
      clientSecret: process.env[clientSecretVar],
      accessToken: process.env[accessTokenVar],
      host: process.env[hostVar],
    });

    if (credentials.isValid) {
      logger.debug('AkamaiApiToken._getCredentialsFromEnv: Found valid credentials in environment');
    } else {
      const missing = [];
      if (!credentials.clientToken) missing.push(clientTokenVar);
      if (!credentials.clientSecret) missing.push(clientSecretVar);
      if (!credentials.accessToken) missing.push(accessTokenVar);
      if (!credentials.host) missing.push(hostVar);
      logger.debug(`AkamaiApiToken._getCredentialsFromEnv: Missing env vars: [${missing.join(', ')}]`);
    }

    return credentials;
  }

  /**
   * Get EdgeGrid credentials from .edgerc file.
   * @param {string} section - Section name (default: 'default')
   * @returns {EdgeGridCredentials}
   */
  _getCredentialsFromEdgerc(section = 'default') {
    logger.debug(`AkamaiApiToken._getCredentialsFromEdgerc: Checking ${DEFAULT_EDGERC_PATH}`);

    if (!existsSync(DEFAULT_EDGERC_PATH)) {
      logger.debug(`AkamaiApiToken._getCredentialsFromEdgerc: File not found: ${DEFAULT_EDGERC_PATH}`);
      return new EdgeGridCredentials();
    }

    try {
      const content = readFileSync(DEFAULT_EDGERC_PATH, 'utf-8');
      const parsed = parseEdgerc(content, section);

      const credentials = new EdgeGridCredentials({
        clientToken: parsed.client_token || null,
        clientSecret: parsed.client_secret || null,
        accessToken: parsed.access_token || null,
        host: parsed.host || null,
      });

      if (credentials.isValid) {
        logger.debug(`AkamaiApiToken._getCredentialsFromEdgerc: Found valid credentials in [${section}]`);
      } else {
        logger.debug(`AkamaiApiToken._getCredentialsFromEdgerc: Incomplete credentials in [${section}]`);
      }

      return credentials;
    } catch (e) {
      logger.warn(`AkamaiApiToken._getCredentialsFromEdgerc: Error reading .edgerc: ${e.message}`);
      return new EdgeGridCredentials();
    }
  }

  /**
   * Get EdgeGrid credentials from environment or .edgerc file.
   * @returns {EdgeGridCredentials}
   */
  getCredentials() {
    // Try environment variables first
    let credentials = this._getCredentialsFromEnv();
    if (credentials.isValid) {
      return credentials;
    }

    // Fall back to .edgerc file
    credentials = this._getCredentialsFromEdgerc();
    return credentials;
  }

  getApiKey() {
    logger.debug('AkamaiApiToken.getApiKey: Starting credential resolution');

    const credentials = this.getCredentials();

    if (credentials.isValid) {
      // Store credentials as JSON in apiKey field
      const credentialsJson = JSON.stringify({
        client_token: credentials.clientToken,
        client_secret: credentials.clientSecret,
        access_token: credentials.accessToken,
        host: credentials.host,
      });

      logger.debug(
        `AkamaiApiToken.getApiKey: Found credentials for host ${maskSensitive(credentials.host || '')}`
      );

      const result = new ApiKeyResult({
        apiKey: credentialsJson,
        authType: 'edgegrid',
        headerName: 'Authorization',
        email: null,
        rawApiKey: credentials.accessToken,
        username: credentials.clientToken,
      });

      logger.debug(`AkamaiApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`);
      return result;
    } else {
      logger.warn(
        'AkamaiApiToken.getApiKey: No valid credentials found. ' +
        'Set AKAMAI_CLIENT_TOKEN, AKAMAI_CLIENT_SECRET, AKAMAI_ACCESS_TOKEN, ' +
        'AKAMAI_HOST environment variables or create ~/.edgerc file.'
      );

      const result = new ApiKeyResult({
        apiKey: null,
        authType: 'edgegrid',
        headerName: 'Authorization',
        email: null,
        rawApiKey: null,
      });

      logger.debug(`AkamaiApiToken.getApiKey: Returning result hasCredentials=${result.hasCredentials}`);
      return result;
    }
  }

  getBaseUrl() {
    const credentials = this.getCredentials();
    if (credentials.host) {
      // Ensure host has https:// prefix
      let host = credentials.host;
      if (!host.startsWith('https://')) {
        host = `https://${host}`;
      }
      return host;
    }
    return super.getBaseUrl();
  }
}
