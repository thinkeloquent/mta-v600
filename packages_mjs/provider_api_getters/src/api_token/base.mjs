/**
 * Base class for API token getters.
 */

/**
 * @typedef {Object} RequestContext
 * @property {any} [request] - Request object (Fastify Request)
 * @property {any} [appState] - Application state
 * @property {string} [tenantId] - Multi-tenant support
 * @property {string} [userId] - User context
 * @property {Object} [extra] - Additional context
 */

/**
 * @typedef {Object} ApiKeyResult
 * @property {string|null} apiKey - The API key or token
 * @property {string} authType - Auth type: 'bearer', 'x-api-key', 'basic', 'custom', 'connection_string'
 * @property {string} headerName - Header name for auth
 * @property {string|null} [username] - Username for basic auth
 * @property {any} [client] - Pre-configured client (for DB connections)
 * @property {boolean} isPlaceholder - Whether this is a placeholder
 * @property {string|null} [placeholderMessage] - Message for placeholder
 */

export class RequestContext {
  constructor({
    request = null,
    appState = null,
    tenantId = null,
    userId = null,
    extra = {},
  } = {}) {
    this.request = request;
    this.appState = appState;
    this.tenantId = tenantId;
    this.userId = userId;
    this.extra = extra;
  }
}

export class ApiKeyResult {
  constructor({
    apiKey = null,
    authType = 'bearer',
    headerName = 'Authorization',
    username = null,
    client = null,
    isPlaceholder = false,
    placeholderMessage = null,
  } = {}) {
    this.apiKey = apiKey;
    this.authType = authType;
    this.headerName = headerName;
    this.username = username;
    this.client = client;
    this.isPlaceholder = isPlaceholder;
    this.placeholderMessage = placeholderMessage;
  }

  get hasCredentials() {
    if (this.isPlaceholder) return false;
    if (this.client !== null) return true;
    return this.apiKey !== null;
  }
}

/**
 * Base class for all provider API token getters.
 */
export class BaseApiToken {
  #configStore = null;

  constructor(configStore = null) {
    this.#configStore = configStore;
  }

  get configStore() {
    if (this.#configStore === null) {
      // Lazy import - will be set by factory
      return null;
    }
    return this.#configStore;
  }

  set configStore(value) {
    this.#configStore = value;
  }

  /**
   * The provider name as defined in static config.
   * @returns {string}
   */
  get providerName() {
    throw new Error('providerName must be implemented by subclass');
  }

  /**
   * The endpoint to use for health checks.
   * @returns {string}
   */
  get healthEndpoint() {
    const providerConfig = this._getProviderConfig();
    return providerConfig?.health_endpoint || '/';
  }

  /**
   * Get provider configuration from static config.
   * @returns {Object}
   */
  _getProviderConfig() {
    try {
      if (!this.configStore) return {};
      return this.configStore.getNested('providers', this.providerName) || {};
    } catch {
      return {};
    }
  }

  /**
   * Get the environment variable name for the API key.
   * @returns {string|null}
   */
  _getEnvApiKeyName() {
    const providerConfig = this._getProviderConfig();
    return providerConfig?.env_api_key || null;
  }

  /**
   * Get the base URL from config or environment.
   * @returns {string|null}
   */
  _getBaseUrl() {
    const providerConfig = this._getProviderConfig();
    const baseUrl = providerConfig?.base_url;
    if (baseUrl) return baseUrl;

    const envBaseUrl = providerConfig?.env_base_url;
    if (envBaseUrl) {
      return process.env[envBaseUrl] || null;
    }
    return null;
  }

  /**
   * Lookup API key from environment variable.
   * @returns {string|null}
   */
  _lookupEnvApiKey() {
    const envKeyName = this._getEnvApiKeyName();
    if (envKeyName) {
      return process.env[envKeyName] || null;
    }
    return null;
  }

  /**
   * Simple API key lookup from environment variable.
   * @returns {ApiKeyResult}
   */
  getApiKey() {
    throw new Error('getApiKey must be implemented by subclass');
  }

  /**
   * Computed API key based on request context.
   * @param {RequestContext} context
   * @returns {ApiKeyResult}
   */
  getApiKeyForRequest(context) {
    return this.getApiKey();
  }

  /**
   * Get the base URL for this provider.
   * @returns {string|null}
   */
  getBaseUrl() {
    return this._getBaseUrl();
  }
}
