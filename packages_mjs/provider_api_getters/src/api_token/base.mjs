/**
 * Base class for API token getters.
 *
 * This module provides the foundation for all provider API token getters
 * with defensive programming principles: hyper-observability via logging
 * at every control flow point.
 */

// Import token registry for dynamic token resolution
import { tokenRegistry } from '../token_resolver/index.mjs';

// Import auth header factory for header construction
import { AuthHeaderFactory } from './auth_header_factory.mjs';

// Simple console logger for defensive programming
const logger = {
  debug: (msg) => console.debug(`[DEBUG] provider_api_getters: ${msg}`),
  info: (msg) => console.info(`[INFO] provider_api_getters: ${msg}`),
  warn: (msg) => console.warn(`[WARN] provider_api_getters: ${msg}`),
  error: (msg) => console.error(`[ERROR] provider_api_getters: ${msg}`),
};

// Valid auth types for validation
// Extended types match fetch-client config.mts and packages_py base.py
const VALID_AUTH_TYPES = new Set([
  // Basic auth family
  'basic',
  'basic_email_token',
  'basic_token',
  'basic_email',
  // Bearer auth family
  'bearer',
  'bearer_oauth',
  'bearer_jwt',
  'bearer_username_token',
  'bearer_username_password',
  'bearer_email_token',
  'bearer_email_password',
  // Custom/API Key
  'x-api-key',
  'custom',
  'custom_header',
  // HMAC (stub)
  'hmac',
  // Connection string (for databases)
  'connection_string',
  // EdgeGrid (Akamai)
  'edgegrid',
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
 * @property {string|null} [apiKey] - The API key or token (may be encoded for basic auth)
 * @property {string} [authType] - Auth type
 * @property {string} [headerName] - Header name for auth
 * @property {string|null} [username] - Username for basic auth (alias for email)
 * @property {string|null} [email] - Email address for basic auth scenarios
 * @property {string|null} [rawApiKey] - The raw/unencoded API key or token
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
    email = null,
    rawApiKey = null,
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
    this.email = email;
    this.rawApiKey = rawApiKey;
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
      hasEmail: this.email !== null,
      hasRawApiKey: this.rawApiKey !== null,
      hasClient: this.client !== null,
      isPlaceholder: this.isPlaceholder,
    };

    if (includeSensitive) {
      if (this.apiKey) {
        result.apiKeyMasked = maskSensitive(this.apiKey);
      }
      if (this.rawApiKey) {
        result.rawApiKeyMasked = maskSensitive(this.rawApiKey);
      }
      if (this.username) {
        result.username = this.username;
      }
      if (this.email) {
        result.email = this.email;
      }
    }

    return result;
  }

  /**
   * Get an AuthHeader instance from this result.
   *
   * Uses the AuthHeaderFactory to create an RFC-compliant Authorization header
   * based on the authType and credentials in this result.
   *
   * @returns {AuthHeader} AuthHeader instance for use in HTTP requests
   */
  getAuthHeader() {
    logger.debug(
      `ApiKeyResult.getAuthHeader: Creating auth header ` +
      `authType=${this.authType}, hasApiKey=${this.apiKey !== null}`
    );

    if (!this.apiKey && !this.client) {
      logger.warn(
        'ApiKeyResult.getAuthHeader: No apiKey or client available, ' +
        'returning null-safe header'
      );
    }

    return AuthHeaderFactory.fromApiKeyResult(this);
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
   * Get the fallback environment variable names for the API key.
   * @returns {string[]}
   */
  _getEnvApiKeyFallbacks() {
    const className = this.constructor.name;
    logger.debug(`${className}._getEnvApiKeyFallbacks: Getting fallback env vars`);

    const providerConfig = this._getProviderConfig();
    const fallbacks = providerConfig?.env_api_key_fallbacks || [];

    if (fallbacks.length > 0) {
      logger.debug(
        `${className}._getEnvApiKeyFallbacks: Found ${fallbacks.length} fallbacks: ` +
        `[${fallbacks.join(', ')}]`
      );
    } else {
      logger.debug(`${className}._getEnvApiKeyFallbacks: No fallbacks configured`);
    }

    return fallbacks;
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
   * Get the environment variable name for the email/username.
   * @returns {string|null}
   */
  _getEnvEmailName() {
    const className = this.constructor.name;
    logger.debug(`${className}._getEnvEmailName: Getting env email name`);

    const providerConfig = this._getProviderConfig();
    const envEmailName = providerConfig?.env_email || null;

    if (envEmailName) {
      logger.debug(`${className}._getEnvEmailName: Found env_email='${envEmailName}'`);
    } else {
      logger.debug(`${className}._getEnvEmailName: No env_email configured`);
    }

    return envEmailName;
  }

  /**
   * Lookup email/username from environment variable.
   * @returns {string|null}
   */
  _lookupEmail() {
    const className = this.constructor.name;
    logger.debug(`${className}._lookupEmail: Looking up email`);

    const envEmailName = this._getEnvEmailName();

    if (!envEmailName) {
      logger.debug(`${className}._lookupEmail: No env_email configured, returning null`);
      return null;
    }

    const email = process.env[envEmailName];

    if (email) {
      logger.debug(`${className}._lookupEmail: Found email in env var '${envEmailName}'`);
    } else {
      logger.debug(`${className}._lookupEmail: Env var '${envEmailName}' is not set or empty`);
    }

    return email || null;
  }

  /**
   * Lookup raw API key from environment variable.
   *
   * This is identical to _lookupEnvApiKey but named for semantic clarity
   * when used alongside _lookupEmail for basic auth scenarios.
   *
   * @returns {string|null}
   */
  _lookupRawApiKey() {
    const className = this.constructor.name;
    logger.debug(`${className}._lookupRawApiKey: Looking up raw API key`);
    return this._lookupEnvApiKey();
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
   * Async API key resolution with registry integration.
   *
   * Resolution priority:
   * 1. Token registry (Option A: setAPIToken, Option C: registerResolver)
   * 2. Subclass getApiKey() implementation (env var lookup)
   *
   * @returns {Promise<ApiKeyResult>}
   */
  async getApiKeyAsync() {
    const className = this.constructor.name;
    logger.debug(`${className}.getApiKeyAsync: Starting async API key resolution`);

    const providerConfig = this._getProviderConfig();

    // 1. Check token registry (Option A/B/C)
    try {
      const registryToken = await tokenRegistry.getToken(
        this.providerName,
        null,
        providerConfig
      );

      if (registryToken) {
        logger.debug(
          `${className}.getApiKeyAsync: Found token from registry ` +
          `(length=${registryToken.length})`
        );
        return new ApiKeyResult({
          apiKey: registryToken,
          authType: this.getAuthType(),
          headerName: this.getHeaderName(),
        });
      }
    } catch (error) {
      logger.error(
        `${className}.getApiKeyAsync: Registry lookup failed: ${error.message}`
      );
    }

    // 2. Fall back to subclass implementation (env var lookup)
    logger.debug(
      `${className}.getApiKeyAsync: No registry token, ` +
      `falling back to getApiKey()`
    );
    return this.getApiKey();
  }

  /**
   * Async API key resolution for request context.
   *
   * Used for per-request token resolution (token_resolver: "request").
   *
   * @param {RequestContext} context - Request context
   * @returns {Promise<ApiKeyResult>}
   */
  async getApiKeyForRequestAsync(context) {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getApiKeyForRequestAsync: Starting async request API key resolution`
    );

    if (context?.tenantId) {
      logger.debug(
        `${className}.getApiKeyForRequestAsync: tenantId=${context.tenantId}`
      );
    }

    if (context?.userId) {
      logger.debug(
        `${className}.getApiKeyForRequestAsync: userId=${context.userId}`
      );
    }

    const providerConfig = this._getProviderConfig();

    // 1. Check token registry with context (for per-request tokens)
    try {
      const registryToken = await tokenRegistry.getToken(
        this.providerName,
        context,
        providerConfig
      );

      if (registryToken) {
        logger.debug(
          `${className}.getApiKeyForRequestAsync: Found token from registry ` +
          `(length=${registryToken.length})`
        );
        return new ApiKeyResult({
          apiKey: registryToken,
          authType: this.getAuthType(),
          headerName: this.getHeaderName(),
        });
      }
    } catch (error) {
      logger.error(
        `${className}.getApiKeyForRequestAsync: Registry lookup failed: ${error.message}`
      );
    }

    // 2. Fall back to subclass implementation
    logger.debug(
      `${className}.getApiKeyForRequestAsync: No registry token, ` +
      `falling back to getApiKeyForRequest()`
    );
    return this.getApiKeyForRequest(context);
  }

  /**
   * Get the base URL for this provider.
   * @returns {string|null}
   */
  getBaseUrl() {
    return this._getBaseUrl();
  }

  /**
   * Default auth type for this provider.
   * Subclasses can override to set provider-specific defaults.
   * @returns {string}
   */
  get _defaultAuthType() {
    return 'bearer';
  }

  /**
   * Default header name for auth.
   * Subclasses can override for custom headers.
   * @returns {string}
   */
  get _defaultHeaderName() {
    return 'Authorization';
  }

  /**
   * Get the auth type for this provider.
   *
   * Resolution priority:
   * 1. YAML config: providers.{name}.api_auth_type
   * 2. Subclass default: _defaultAuthType property
   *
   * @returns {string} Auth type (bearer, basic, x-api-key, custom, connection_string)
   */
  getAuthType() {
    const className = this.constructor.name;
    logger.debug(`${className}.getAuthType: Getting auth type`);

    // 1. Check YAML config
    const providerConfig = this._getProviderConfig();
    const configAuthType = providerConfig?.api_auth_type;

    if (configAuthType) {
      // Validate auth type
      if (!VALID_AUTH_TYPES.has(configAuthType)) {
        logger.warn(
          `${className}.getAuthType: Invalid api_auth_type '${configAuthType}' in config, ` +
          `expected one of [${[...VALID_AUTH_TYPES].join(', ')}], ` +
          `falling back to default '${this._defaultAuthType}'`
        );
        return this._defaultAuthType;
      }

      logger.debug(
        `${className}.getAuthType: Using api_auth_type from config: '${configAuthType}'`
      );
      return configAuthType;
    }

    // 2. Fall back to provider default
    logger.debug(
      `${className}.getAuthType: No api_auth_type in config, ` +
      `using provider default: '${this._defaultAuthType}'`
    );
    return this._defaultAuthType;
  }

  /**
   * Get the header name for auth.
   *
   * Resolution based on auth type:
   * - bearer: Authorization
   * - x-api-key: X-Api-Key
   * - basic: Authorization
   * - custom: Subclass default
   *
   * @returns {string} Header name
   */
  getHeaderName() {
    const className = this.constructor.name;
    logger.debug(`${className}.getHeaderName: Getting header name`);

    const authType = this.getAuthType();

    let headerName;
    switch (authType) {
      case 'bearer':
      case 'basic':
        headerName = 'Authorization';
        break;
      case 'x-api-key':
        headerName = 'X-Api-Key';
        break;
      case 'custom_header': {
        // Read header name from provider config's api_auth_header_name
        const providerConfig = this._getProviderConfig();
        headerName = providerConfig?.api_auth_header_name || this._defaultHeaderName || 'Authorization';
        break;
      }
      case 'custom':
      case 'connection_string':
      default:
        headerName = this._defaultHeaderName;
    }

    logger.debug(
      `${className}.getHeaderName: authType='${authType}' -> headerName='${headerName}'`
    );
    return headerName;
  }

  /**
   * Get the token resolver type for this provider.
   *
   * @returns {string} Token resolver type (static, startup, request)
   */
  getTokenResolverType() {
    const className = this.constructor.name;
    logger.debug(`${className}.getTokenResolverType: Getting token resolver type`);

    const providerConfig = this._getProviderConfig();
    const resolverType = providerConfig?.token_resolver || 'static';

    // Validate resolver type
    const validTypes = new Set(['static', 'startup', 'request']);
    if (!validTypes.has(resolverType)) {
      logger.warn(
        `${className}.getTokenResolverType: Invalid token_resolver '${resolverType}' in config, ` +
        `expected one of [${[...validTypes].join(', ')}], defaulting to 'static'`
      );
      return 'static';
    }

    logger.debug(
      `${className}.getTokenResolverType: Resolved token_resolver='${resolverType}'`
    );
    return resolverType;
  }

  /**
   * Get the runtime_import configuration for this provider.
   *
   * Supports two formats:
   * - Object: { fastify: "path.mjs", fastapi: "module.path" }
   * - String: "path.mjs" (single platform)
   *
   * @param {string} platform - Platform key ('fastify' or 'fastapi')
   * @returns {string|null} Import path for the platform or null
   */
  getRuntimeImport(platform = 'fastify') {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getRuntimeImport: Getting runtime_import for platform='${platform}'`
    );

    const providerConfig = this._getProviderConfig();
    const runtimeImport = providerConfig?.runtime_import;

    if (!runtimeImport) {
      logger.debug(`${className}.getRuntimeImport: No runtime_import configured`);
      return null;
    }

    let importPath = null;

    if (typeof runtimeImport === 'object' && runtimeImport[platform]) {
      importPath = runtimeImport[platform];
      logger.debug(
        `${className}.getRuntimeImport: Found platform-specific import: '${importPath}'`
      );
    } else if (typeof runtimeImport === 'string') {
      importPath = runtimeImport;
      logger.debug(
        `${className}.getRuntimeImport: Found string import (single platform): '${importPath}'`
      );
    }

    return importPath;
  }

  /**
   * Get provider-specific proxy configuration.
   *
   * @returns {Object|null} Proxy config dictionary or null if not configured
   */
  getProxyUrl() {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getProxyUrl: Getting proxy URL from provider config`
    );
    const providerConfig = this._getProviderConfig();
    return providerConfig.proxy_url || null;
  }

  getNetworkConfig() {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getNetworkConfig: Getting network config from provider config`
    );
    const providerConfig = this._getProviderConfig();
    const networkConfig = providerConfig.network || null;

    if (networkConfig) {
      logger.debug(
        `${className}.getNetworkConfig: Found network config with keys: ${Object.keys(
          networkConfig
        )}`
      );
    } else {
      logger.debug(
        `${className}.getNetworkConfig: No network config in provider config`
      );
    }
    return networkConfig;
  }

  getProxyConfig() {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getProxyConfig: Getting proxy config from provider config`
    );

    const providerConfig = this._getProviderConfig();
    const proxyConfig = providerConfig?.proxy || null;

    if (proxyConfig) {
      logger.debug(
        `${className}.getProxyConfig: Found proxy config with keys: ` +
        `[${Object.keys(proxyConfig).join(', ')}]`
      );
    } else {
      logger.debug(`${className}.getProxyConfig: No proxy config in provider config`);
    }

    return proxyConfig;
  }

  /**
   * Get provider-specific client configuration.
   *
   * @returns {Object|null} Client config dictionary or null if not configured
   */
  getClientConfig() {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getClientConfig: Getting client config from provider config`
    );

    const providerConfig = this._getProviderConfig();
    const clientConfig = providerConfig?.client || null;

    if (clientConfig) {
      logger.debug(
        `${className}.getClientConfig: Found client config with keys: ` +
        `[${Object.keys(clientConfig).join(', ')}]`
      );
    } else {
      logger.debug(`${className}.getClientConfig: No client config in provider config`);
    }

    return clientConfig;
  }

  /**
   * Get provider-specific network configuration.
   *
   * @returns {Object|null} Network config dictionary or null if not configured
   */
  getNetworkConfig() {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getNetworkConfig: Getting network config from provider config`
    );

    const providerConfig = this._getProviderConfig();
    const networkConfig = providerConfig?.network || null;

    if (networkConfig) {
      logger.debug(
        `${className}.getNetworkConfig: Found network config with keys: ` +
        `[${Object.keys(networkConfig).join(', ')}]`
      );
    } else {
      logger.debug(`${className}.getNetworkConfig: No network config in provider config`);
    }

    return networkConfig;
  }

  /**
   * Get provider-specific proxy configuration.
   *
   * @returns {Object|null} Proxy config dictionary or null if not configured
   */
  getProxyConfig() {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getProxyConfig: Getting proxy config from provider config`
    );

    const providerConfig = this._getProviderConfig();
    const proxyConfig = providerConfig?.proxy || null;

    if (proxyConfig) {
      logger.debug(
        `${className}.getProxyConfig: Found proxy config with keys: ` +
        `[${Object.keys(proxyConfig).join(', ')}]`
      );
    } else {
      logger.debug(`${className}.getProxyConfig: No proxy config in provider config`);
    }

    return proxyConfig;
  }

  /**
   * Get provider-specific headers configuration.
   *
   * @returns {Object|null} Headers config dictionary or null if not configured
   */
  getHeadersConfig() {
    const className = this.constructor.name;
    logger.debug(
      `${className}.getHeadersConfig: Getting headers config from provider config`
    );

    const providerConfig = this._getProviderConfig();
    const headersConfig = providerConfig?.headers || null;

    if (headersConfig) {
      logger.debug(
        `${className}.getHeadersConfig: Found headers config with keys: ` +
        `[${Object.keys(headersConfig).join(', ')}]`
      );
    } else {
      logger.debug(`${className}.getHeadersConfig: No headers config in provider config`);
    }

    return headersConfig;
  }

  /**
   * Get default HTTP headers from provider configuration.
   *
   * Reads from providers.{name}.headers in YAML config.
   * These are provider-specific default headers for API requests.
   *
   * @returns {Object} Dictionary of header name -> value
   */
  getHeaders() {
    const className = this.constructor.name;
    logger.debug(`${className}.getHeaders: Getting default headers from provider config`);

    const providerConfig = this._getProviderConfig();
    const headers = providerConfig?.headers || {};

    if (Object.keys(headers).length > 0) {
      logger.debug(
        `${className}.getHeaders: Found ${Object.keys(headers).length} headers: ` +
        `[${Object.keys(headers).join(', ')}]`
      );
    } else {
      logger.debug(`${className}.getHeaders: No headers configured for provider`);
    }

    return headers;
  }

  /**
   * Get environment variable value by name from provider config.
   *
   * Looks up env_{name} in the provider config to get the environment variable name,
   * then resolves the actual value from the environment.
   *
   * Example:
   *   YAML config:
   *     providers:
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
    const className = this.constructor.name;
    logger.debug(`${className}.getEnvByName: Looking up env_${name}`);

    const providerConfig = this._getProviderConfig();
    const envKey = `env_${name}`;
    const envVarName = providerConfig?.[envKey];

    if (!envVarName) {
      logger.debug(
        `${className}.getEnvByName: No '${envKey}' found in provider config, ` +
        `returning default: ${defaultValue}`
      );
      return defaultValue;
    }

    const value = process.env[envVarName] || defaultValue;

    logger.debug(
      `${className}.getEnvByName: Resolved ${envKey}='${envVarName}' -> ` +
      `value=${value ? '<set>' : '<not set>'}`
    );

    return value;
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
