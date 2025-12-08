/**
 * Base class for API token getters.
 *
 * This module provides the foundation for all provider API token getters
 * with defensive programming principles: hyper-observability via logging
 * at every control flow point.
 */

// Simple console logger for defensive programming
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters: ${msg}`),
  info: (msg) => console.info(`[INFO] provider_api_getters: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters: ${msg}`),
  error: (msg) => console.error(`[ERROR] provider_api_getters: ${msg}`),
};

// Valid auth types for validation
const VALID_AUTH_TYPES = new Set([
  'bearer',
  'x-api-key',
  'basic',
  'custom',
  'connection_string',
]);

/**
 * Mask sensitive values for safe logging.
 * @param {string|null} value - Value to mask
 * @param {number} visibleChars - Number of characters to show
 * @returns {string}
 */
export function maskSensitive(value, visibleChars = 4) {
  if (value === null || value === undefined) {
    return '<None>';
  }
  if (typeof value !== 'string') {
    return '<invalid-type>';
  }
  if (value.length <= visibleChars) {
    return '*'.repeat(value.length);
  }
  return value.substring(0, visibleChars) + '*'.repeat(value.length - visibleChars);
}

/**
 * @typedef {Object} RequestContextOptions
 * @property {any} [request] - Request object (Fastify Request)
 * @property {any} [appState] - Application state
 * @property {string} [tenantId] - Multi-tenant support
 * @property {string} [userId] - User context
 * @property {Object} [extra] - Additional context
 */

/**
 * Request context for per-request API key resolution.
 */
export class RequestContext {
  constructor({
    request = null,
    appState = null,
    tenantId = null,
    userId = null,
    extra = null,
  } = {}) {
    logger.debug(
      `RequestContext.constructor: Initializing context ` +
      `tenantId=${tenantId}, userId=${userId}, ` +
      `hasRequest=${request !== null}, hasAppState=${appState !== null}`
    );

    this.request = request;
    this.appState = appState;

    // Type coercion for tenantId
    if (tenantId !== null && typeof tenantId !== 'string') {
      logger.warn(
        `RequestContext.constructor: tenantId is not a string (type=${typeof tenantId}), ` +
        `coercing to string`
      );
      this.tenantId = String(tenantId);
    } else {
      this.tenantId = tenantId;
    }

    // Type coercion for userId
    if (userId !== null && typeof userId !== 'string') {
      logger.warn(
        `RequestContext.constructor: userId is not a string (type=${typeof userId}), ` +
        `coercing to string`
      );
      this.userId = String(userId);
    } else {
      this.userId = userId;
    }

    // Normalize extra to empty object
    if (extra === null || extra === undefined) {
      logger.debug('RequestContext.constructor: extra was null, defaulting to empty object');
      this.extra = {};
    } else {
      this.extra = extra;
    }

    logger.debug('RequestContext.constructor: Context initialized successfully');
  }

  /**
   * Convert to dictionary for logging.
   * @returns {Object}
   */
  toDict() {
    logger.debug('RequestContext.toDict: Converting context to dictionary');
    return {
      tenantId: this.tenantId,
      userId: this.userId,
      hasRequest: this.request !== null,
      hasAppState: this.appState !== null,
      extraKeys: Object.keys(this.extra),
    };
  }
}

/**
 * @typedef {Object} ApiKeyResultOptions
 * @property {string|null} [apiKey] - The API key or token
 * @property {string} [authType] - Auth type
 * @property {string} [headerName] - Header name for auth
 * @property {string|null} [username] - Username for basic auth
 * @property {any} [client] - Pre-configured client
 * @property {boolean} [isPlaceholder] - Whether this is a placeholder
 * @property {string|null} [placeholderMessage] - Message for placeholder
 */

/**
 * Result of API key resolution.
 */
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
    logger.debug(
      `ApiKeyResult.constructor: Initializing result ` +
      `authType=${authType}, headerName=${headerName}, ` +
      `hasApiKey=${apiKey !== null}, hasClient=${client !== null}, ` +
      `isPlaceholder=${isPlaceholder}`
    );

    this.apiKey = apiKey;

    // Validate authType
    if (!VALID_AUTH_TYPES.has(authType)) {
      logger.warn(
        `ApiKeyResult.constructor: Invalid authType '${authType}', ` +
        `expected one of [${[...VALID_AUTH_TYPES].join(', ')}]`
      );
    }
    this.authType = authType;

    // Default empty headerName to Authorization
    if (!headerName) {
      logger.debug(
        'ApiKeyResult.constructor: headerName is empty, defaulting to Authorization'
      );
      this.headerName = 'Authorization';
    } else {
      this.headerName = headerName;
    }

    this.username = username;
    this.client = client;
    this.isPlaceholder = isPlaceholder;
    this.placeholderMessage = placeholderMessage;

    // Log inconsistent state
    if (isPlaceholder && apiKey !== null) {
      logger.warn(
        'ApiKeyResult.constructor: isPlaceholder=true but apiKey is set - ' +
        'this is inconsistent'
      );
    }

    logger.debug('ApiKeyResult.constructor: Result initialized successfully');
  }

  /**
   * Check if credentials are available.
   * @returns {boolean}
   */
  get hasCredentials() {
    logger.debug(
      `ApiKeyResult.hasCredentials: Checking credentials ` +
      `isPlaceholder=${this.isPlaceholder}, hasClient=${this.client !== null}, ` +
      `hasApiKey=${this.apiKey !== null}`
    );

    if (this.isPlaceholder) {
      logger.debug('ApiKeyResult.hasCredentials: isPlaceholder=true, returning false');
      return false;
    }

    if (this.client !== null) {
      logger.debug('ApiKeyResult.hasCredentials: client is set, returning true');
      return true;
    }

    const result = this.apiKey !== null;
    logger.debug(`ApiKeyResult.hasCredentials: apiKey check result=${result}`);
    return result;
  }

  /**
   * Convert to dictionary for logging.
   * @param {boolean} includeSensitive - Include sensitive data
   * @returns {Object}
   */
  toDict(includeSensitive = false) {
    logger.debug(
      `ApiKeyResult.toDict: Converting to dictionary includeSensitive=${includeSensitive}`
    );

    const result = {
      authType: this.authType,
      headerName: this.headerName,
      hasApiKey: this.apiKey !== null,
      hasUsername: this.username !== null,
      hasClient: this.client !== null,
      isPlaceholder: this.isPlaceholder,
    };

    if (includeSensitive) {
      if (this.apiKey) {
        result.apiKeyMasked = maskSensitive(this.apiKey);
      }
      if (this.username) {
        result.username = this.username;
      }
    }

    return result;
  }
}

/**
 * Base class for all provider API token getters.
 */
export class BaseApiToken {
  #configStore = null;
  #configCache = null;

  constructor(configStore = null) {
    const className = this.constructor.name;
    logger.debug(
      `${className}.constructor: Initializing with ` +
      `configStore=${configStore !== null ? 'provided' : 'null (will lazy-load)'}`
    );

    this.#configStore = configStore;
    this.#configCache = null;
  }

  get configStore() {
    const className = this.constructor.name;

    if (this.#configStore === null) {
      logger.debug(
        `${className}.configStore: No configStore provided, returning null`
      );
      return null;
    }

    logger.debug(`${className}.configStore: Using provided configStore`);
    return this.#configStore;
  }

  set configStore(value) {
    const className = this.constructor.name;
    logger.debug(`${className}.configStore: Setting configStore`);
    this.#configStore = value;
    this.#configCache = null; // Clear cache when store changes
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
    const className = this.constructor.name;
    logger.debug(`${className}.healthEndpoint: Getting health endpoint`);

    const providerConfig = this._getProviderConfig();
    const endpoint = providerConfig?.health_endpoint || '/';

    logger.debug(
      `${className}.healthEndpoint: Returning '${endpoint}' ` +
      `(fromConfig=${providerConfig?.health_endpoint !== undefined})`
    );
    return endpoint;
  }

  /**
   * Get provider configuration from static config.
   * @returns {Object}
   */
  _getProviderConfig() {
    const className = this.constructor.name;
    logger.debug(
      `${className}._getProviderConfig: Getting config for provider '${this.providerName}'`
    );

    // Return cached config if available
    if (this.#configCache !== null) {
      logger.debug(`${className}._getProviderConfig: Returning cached config`);
      return this.#configCache;
    }

    try {
      if (!this.configStore) {
        logger.debug(
          `${className}._getProviderConfig: No configStore available, returning empty config`
        );
        return {};
      }

      const config = this.configStore.getNested('providers', this.providerName);

      if (config) {
        logger.debug(
          `${className}._getProviderConfig: Found config with keys: ` +
          `[${Object.keys(config).join(', ')}]`
        );
        this.#configCache = config;
        return config;
      } else {
        logger.warn(
          `${className}._getProviderConfig: No config found for provider '${this.providerName}'`
        );
        return {};
      }
    } catch (error) {
      logger.error(
        `${className}._getProviderConfig: Exception while getting config: ` +
        `${error.name}: ${error.message}`
      );
      return {};
    }
  }

  /**
   * Clear the configuration cache.
   */
  clearCache() {
    const className = this.constructor.name;
    logger.debug(`${className}.clearCache: Clearing configuration cache`);
    this.#configCache = null;
  }

  /**
   * Get the environment variable name for the API key.
   * @returns {string|null}
   */
  _getEnvApiKeyName() {
    const className = this.constructor.name;
    logger.debug(`${className}._getEnvApiKeyName: Getting env key name`);

    const providerConfig = this._getProviderConfig();
    const envApiKey = providerConfig?.env_api_key || null;

    if (envApiKey) {
      logger.debug(`${className}._getEnvApiKeyName: Found env_api_key='${envApiKey}'`);
    } else {
      logger.debug(`${className}._getEnvApiKeyName: No env_api_key configured`);
    }

    return envApiKey;
  }

  /**
   * Get the base URL from config or environment.
   * @returns {string|null}
   */
  _getBaseUrl() {
    const className = this.constructor.name;
    logger.debug(`${className}._getBaseUrl: Getting base URL`);

    const providerConfig = this._getProviderConfig();

    // Check for direct base_url in config
    const baseUrl = providerConfig?.base_url;
    if (baseUrl) {
      logger.debug(`${className}._getBaseUrl: Using base_url from config: '${baseUrl}'`);
      return baseUrl;
    }

    // Check for env_base_url
    const envBaseUrl = providerConfig?.env_base_url;
    if (envBaseUrl) {
      logger.debug(`${className}._getBaseUrl: Checking env var '${envBaseUrl}'`);
      const url = process.env[envBaseUrl];
      if (url) {
        logger.debug(`${className}._getBaseUrl: Using base_url from env var: '${url}'`);
        return url;
      } else {
        logger.debug(`${className}._getBaseUrl: Env var '${envBaseUrl}' is not set`);
      }
    } else {
      logger.debug(`${className}._getBaseUrl: No base_url or env_base_url configured`);
    }

    return null;
  }

  /**
   * Lookup API key from environment variable.
   * @returns {string|null}
   */
  _lookupEnvApiKey() {
    const className = this.constructor.name;
    logger.debug(`${className}._lookupEnvApiKey: Looking up API key`);

    const envKeyName = this._getEnvApiKeyName();

    if (!envKeyName) {
      logger.debug(`${className}._lookupEnvApiKey: No env_api_key configured`);
      return null;
    }

    const apiKey = process.env[envKeyName];

    if (apiKey) {
      logger.debug(
        `${className}._lookupEnvApiKey: Found API key in env var '${envKeyName}' ` +
        `(length=${apiKey.length}, masked=${maskSensitive(apiKey)})`
      );
      return apiKey;
    } else {
      logger.debug(
        `${className}._lookupEnvApiKey: Env var '${envKeyName}' is not set or empty`
      );
      return null;
    }
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
    const className = this.constructor.name;
    logger.debug(
      `${className}.getApiKeyForRequest: Getting API key for request context`
    );

    if (context.tenantId) {
      logger.debug(
        `${className}.getApiKeyForRequest: tenantId=${context.tenantId} provided ` +
        `but base implementation ignores it`
      );
    }

    if (context.userId) {
      logger.debug(
        `${className}.getApiKeyForRequest: userId=${context.userId} provided ` +
        `but base implementation ignores it`
      );
    }

    return this.getApiKey();
  }

  /**
   * Get the base URL for this provider.
   * @returns {string|null}
   */
  getBaseUrl() {
    return this._getBaseUrl();
  }

  /**
   * Validate the provider configuration.
   * @returns {Object}
   */
  validate() {
    const className = this.constructor.name;
    logger.debug(`${className}.validate: Validating provider configuration`);

    const issues = [];
    const warnings = [];

    // Check base URL
    const baseUrl = this.getBaseUrl();
    const hasBaseUrl = baseUrl !== null;

    if (!hasBaseUrl) {
      logger.debug(`${className}.validate: No base_url configured`);
      issues.push('No base_url configured');
    }

    // Check credentials
    const apiKeyResult = this.getApiKey();
    const hasCredentials = apiKeyResult.hasCredentials;
    const isPlaceholder = apiKeyResult.isPlaceholder;

    if (isPlaceholder) {
      logger.debug(
        `${className}.validate: Provider is placeholder: ${apiKeyResult.placeholderMessage}`
      );
      warnings.push(`Provider is placeholder: ${apiKeyResult.placeholderMessage}`);
    } else if (!hasCredentials) {
      logger.debug(`${className}.validate: No API credentials available`);
      issues.push('No API credentials available');
    }

    const valid = issues.length === 0;

    logger.debug(
      `${className}.validate: Validation complete ` +
      `valid=${valid}, issues=${issues.length}, warnings=${warnings.length}`
    );

    return {
      valid,
      issues,
      warnings,
      hasBaseUrl,
      hasCredentials,
      isPlaceholder,
    };
  }
}
