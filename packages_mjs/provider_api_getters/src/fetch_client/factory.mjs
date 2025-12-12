/**
 * Factory for creating pre-configured HTTP clients for providers.
 *
 * This module uses the ConfigStore singleton from @internal/app-static-config-yaml
 * and the proxy dispatcher from @internal/fetch-proxy-dispatcher.
 *
 * Reads proxy configuration from YAML:
 * - proxy.default_environment: Environment name for proxy selection
 * - proxy.proxy_urls: Per-environment proxy URLs (DEV, STAGE, QA, PROD)
 * - proxy.agent_proxy: Agent proxy (http_proxy, https_proxy)
 * - proxy.cert_verify: SSL verification (false = disable)
 *
 * Falls back to ENV if YAML value is undefined (not present).
 * Does nothing if YAML value is explicitly null.
 */
import pino from 'pino';
import { getApiTokenClass } from '../api_token/index.mjs';
import { deepMerge } from '../utils/deep_merge.mjs';
import { resolveAuthConfig, getAuthTypeCategory } from '../utils/authResolver.mjs';

// Create pino logger with pretty printing
const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true,
    },
  },
});

export class ProviderClientFactory {
  #configStore = null;

  constructor(configStore = null) {
    this.#configStore = configStore;
  }

  get configStore() {
    return this.#configStore;
  }

  set configStore(value) {
    this.#configStore = value;
  }

  _getProxyConfig() {
    try {
      if (!this.configStore) return {};
      return this.configStore.getNested('proxy') || {};
    } catch {
      return {};
    }
  }

  _getClientConfig() {
    try {
      if (!this.configStore) return {};
      return this.configStore.getNested('client') || {};
    } catch {
      return {};
    }
  }

  /**
   * Get merged configuration for a provider, combining global config with provider overrides.
   *
   * Resolution priority (deep merge):
   * 1. runtime_override (if provided via POST endpoint)
   * 2. providers.{name}.overwrite_root_config.* (provider-specific)
   * 3. Global settings (proxy.*, client.*)
   *
   * @param {string} providerName - Provider name
   * @param {Object} runtimeOverride - Optional runtime override from POST request
   * @returns {Object} Merged configuration with proxy, client, and headers
   */
  _getMergedConfigForProvider(providerName, runtimeOverride = null) {
    const apiToken = this.getApiToken(providerName);
    if (!apiToken) {
      return {
        proxy: this._getProxyConfig(),
        client: this._getClientConfig(),
        headers: {},
        has_provider_override: false,
        has_runtime_override: false,
      };
    }

    // Get specific overrides directly from provider config
    // These correspond to providers.{name}.proxy, .client, .headers
    const providerProxy = apiToken.getProxyConfig() || {};
    const providerClient = apiToken.getClientConfig() || {};
    const providerHeaders = apiToken.getHeadersConfig() || {};

    const globalProxy = this._getProxyConfig();
    const globalClient = this._getClientConfig();

    // Priority: runtime_override > provider_specific > global
    let mergedProxy = deepMerge(globalProxy, providerProxy);
    let mergedClient = deepMerge(globalClient, providerClient);
    let headers = { ...providerHeaders };

    // Apply runtime override if provided
    if (runtimeOverride) {
      if (runtimeOverride.proxy) {
        mergedProxy = deepMerge(mergedProxy, runtimeOverride.proxy);
      }
      if (runtimeOverride.client) {
        mergedClient = deepMerge(mergedClient, runtimeOverride.client);
      }
      if (runtimeOverride.headers) {
        headers = { ...headers, ...runtimeOverride.headers };
      }
    }

    const hasOverrides =
      Object.keys(providerProxy).length > 0 ||
      Object.keys(providerClient).length > 0 ||
      Object.keys(providerHeaders).length > 0;

    if (hasOverrides) {
      logger.info(
        { providerName },
        'Provider-specific overrides applied'
      );
    }

    if (runtimeOverride && Object.keys(runtimeOverride).length > 0) {
      logger.info(
        { providerName, runtimeOverrideKeys: Object.keys(runtimeOverride) },
        'Runtime override applied'
      );
    }

    return {
      proxy: mergedProxy,
      client: mergedClient,
      headers,
      has_provider_override: hasOverrides,
      has_runtime_override: runtimeOverride && Object.keys(runtimeOverride).length > 0,
    };
  }

  /**
   * Create a dispatcher with proxy configuration.
   *
   * Uses ProxyDispatcherFactory with full config:
   * - proxy_urls: per-environment proxy URLs
   * - agent_proxy: http_proxy/https_proxy overrides
   * - default_environment: env for proxy selection
   * - cert_verify: false = disable TLS validation
   * - ca_bundle: path to CA bundle file
   *
   * @param {Object} proxyConfig - Merged proxy configuration (global + provider overrides)
   * @returns {Promise<Dispatcher|undefined>} Dispatcher or undefined
   */
  async _createDispatcher(proxyConfig = null) {
    try {
      const { ProxyDispatcherFactory } = await import('@internal/fetch-proxy-dispatcher');
      // Use provided config or fall back to global
      proxyConfig = proxyConfig || this._getProxyConfig();

      // Build ProxyUrlConfig from YAML (convert to uppercase keys)
      let proxyUrls;
      const yamlProxyUrls = proxyConfig?.proxy_urls;
      if (yamlProxyUrls && typeof yamlProxyUrls === 'object' && Object.keys(yamlProxyUrls).length > 0) {
        proxyUrls = {};
        // Convert keys to uppercase for ProxyUrlConfig (DEV, STAGE, QA, PROD)
        for (const [key, value] of Object.entries(yamlProxyUrls)) {
          if (value) {
            proxyUrls[key.toUpperCase()] = value;
          }
        }
      }

      // Build AgentProxyConfig from YAML
      let agentProxy;
      const yamlAgentProxy = proxyConfig?.agent_proxy;
      if (yamlAgentProxy && typeof yamlAgentProxy === 'object') {
        const httpProxy = yamlAgentProxy.http_proxy;
        const httpsProxy = yamlAgentProxy.https_proxy;
        if (httpProxy || httpsProxy) {
          agentProxy = {
            httpProxy: httpProxy || undefined,
            httpsProxy: httpsProxy || undefined,
          };
        }
      }

      // Get other config values
      const defaultEnvironment = proxyConfig?.default_environment?.toUpperCase();
      const disableTls = proxyConfig?.cert_verify === false;

      // Build factory config
      const factoryConfig = {};
      if (proxyUrls) factoryConfig.proxyUrls = proxyUrls;
      if (agentProxy) factoryConfig.agentProxy = agentProxy;
      if (defaultEnvironment) factoryConfig.defaultEnvironment = defaultEnvironment;

      const factory = new ProxyDispatcherFactory(factoryConfig);
      logger.info({ factoryConfig, disableTls }, 'ProxyDispatcherFactory config');
      return factory.getProxyDispatcher({ disableTls });
    } catch {
      return undefined;
    }
  }

  getApiToken(providerName) {
    const TokenClass = getApiTokenClass(providerName);
    if (!TokenClass) return null;
    const token = new TokenClass(this.configStore);
    return token;
  }

  async getClient(providerName) {
    let createClient;
    try {
      const fetchClient = await import('@internal/fetch-client');
      createClient = fetchClient.createClient;
    } catch {
      return null;
    }

    const apiToken = this.getApiToken(providerName);
    if (!apiToken) return null;
    logger.info({ providerName }, 'API token retrieved');

    const baseUrl = apiToken.getBaseUrl();
    if (!baseUrl) return null;

    // Use async method to support dynamic token resolution
    const apiKeyResult = await apiToken.getApiKeyAsync();
    if (apiKeyResult.isPlaceholder) return null;

    // Get merged config (global + provider overrides)
    const mergedConfig = this._getMergedConfigForProvider(providerName);

    // Check token resolver type for per-request tokens
    const tokenResolverType = apiToken.getTokenResolverType();

    // Create dispatcher with merged proxy config
    const dispatcher = await this._createDispatcher(mergedConfig.proxy);

    let auth;
    if (apiKeyResult.apiKey) {
      // Use getAuthType() and getHeaderName() from apiToken for consistent auth type
      const authType = apiToken.getAuthType();
      const headerName = apiToken.getHeaderName();

      // Use shared auth resolver utility (SINGLE SOURCE OF TRUTH)
      // See: utils/authResolver.mjs for auth type interpretation logic
      auth = resolveAuthConfig(authType, apiKeyResult, headerName);
      const authCategory = getAuthTypeCategory(authType);

      logger.info({ providerName, authType, authCategory, resolvedType: auth.type }, 'Auth config created');
    }

    // Build client options with merged config
    const clientOptions = {
      baseUrl,
      dispatcher,
      auth,
      headers: {
        'User-Agent': 'provider-api-getters/1.0',
      },
    };

    // Apply timeout from merged client config
    if (mergedConfig.client?.timeout_ms) {
      clientOptions.timeout = mergedConfig.client.timeout_ms;
    }

    // Apply additional headers from overwrite_config (merge with defaults)
    if (Object.keys(mergedConfig.headers).length > 0) {
      clientOptions.headers = { ...clientOptions.headers, ...mergedConfig.headers };
    }

    // For per-request tokens, add dynamic auth handler
    if (tokenResolverType === 'request') {
      clientOptions.getApiKeyForRequest = async (context) => {
        const result = await apiToken.getApiKeyForRequestAsync(context);
        return result.apiKey;
      };
      logger.info({ providerName, tokenResolverType }, 'Dynamic auth enabled for per-request tokens');
    }

    const client = createClient(clientOptions);
    logger.info({ providerName, baseUrl, hasOverrideHeaders: Object.keys(mergedConfig.headers).length > 0, tokenResolverType }, 'FetchClient created');

    return client;
  }
}

let _factory = null;

/**
 * Get a pre-configured HTTP client for a provider.
 *
 * Uses the ConfigStore singleton from @internal/app-static-config-yaml
 * to automatically load provider configuration.
 *
 * @param {string} providerName - Provider name (e.g., 'github', 'jira', 'figma')
 * @returns {Promise<FetchClient|null>} Configured client or null
 */
export async function getProviderClient(providerName) {
  if (_factory === null) {
    // Lazy-load ConfigStore singleton to avoid circular dependencies
    try {
      const { config } = await import('@internal/app-static-config-yaml');
      _factory = new ProviderClientFactory(config);
    } catch {
      // Fallback to factory without config (will use env vars)
      _factory = new ProviderClientFactory();
    }
  }
  return _factory.getClient(providerName);
}
