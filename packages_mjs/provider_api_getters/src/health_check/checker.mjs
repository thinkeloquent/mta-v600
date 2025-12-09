/**
 * Provider health check implementation.
 */
import { getApiTokenClass } from '../api_token/index.mjs';
import { ProviderClientFactory } from '../fetch_client/factory.mjs';

/**
 * Response from a provider connection health check.
 */
export class ProviderConnectionResponse {
  constructor({
    provider,
    status,
    latencyMs = null,
    message = null,
    error = null,
    timestamp = null,
    configUsed = null,
  }) {
    this.provider = provider;
    this.status = status;
    this.latency_ms = latencyMs;
    this.message = message;
    this.error = error;
    this.timestamp = timestamp || new Date().toISOString();
    this.config_used = configUsed;
  }

  toJSON() {
    return {
      provider: this.provider,
      status: this.status,
      latency_ms: this.latency_ms,
      message: this.message,
      error: this.error,
      timestamp: this.timestamp,
      config_used: this.config_used,
    };
  }
}

export class ProviderHealthChecker {
  #configStore = null;
  #clientFactory = null;
  #runtimeOverride = null;

  /**
   * @param {Object} configStore - Static config store
   * @param {Object} runtimeOverride - Optional runtime override for proxy/client settings
   */
  constructor(configStore = null, runtimeOverride = null) {
    this.#configStore = configStore;
    this.#runtimeOverride = runtimeOverride;
    this.#clientFactory = new ProviderClientFactory(configStore);
  }

  get configStore() {
    return this.#configStore;
  }

  set configStore(value) {
    this.#configStore = value;
    this.#clientFactory.configStore = value;
  }

  get runtimeOverride() {
    return this.#runtimeOverride;
  }

  /**
   * Build config_used object for response
   */
  _buildConfigUsed(providerName, apiToken) {
    const mergedConfig = this.#clientFactory._getMergedConfigForProvider(
      providerName,
      this.#runtimeOverride
    );

    return {
      base_url: apiToken?.getBaseUrl?.() || null,
      proxy: mergedConfig.proxy,
      client: mergedConfig.client,
      auth_type: apiToken?.getAuthType?.() || null,
      has_overwrite_root_config: mergedConfig.has_overwrite_root_config,
      has_runtime_override: mergedConfig.has_runtime_override,
    };
  }

  async check(providerName) {
    const providerNameLower = providerName.toLowerCase();

    const TokenClass = getApiTokenClass(providerNameLower);
    if (!TokenClass) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        error: `Unknown provider: ${providerName}`,
      });
    }

    const apiToken = new TokenClass(this.#configStore);
    const apiKeyResult = apiToken.getApiKey();
    const configUsed = this._buildConfigUsed(providerNameLower, apiToken);

    if (apiKeyResult.isPlaceholder) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'not_implemented',
        message: apiKeyResult.placeholderMessage,
        configUsed,
      });
    }

    if (providerNameLower === 'postgres') {
      return this._checkPostgres(apiToken, configUsed);
    } else if (providerNameLower === 'redis') {
      return this._checkRedis(apiToken, configUsed);
    } else if (providerNameLower === 'elasticsearch') {
      return this._checkElasticsearch(apiToken, configUsed);
    } else {
      return this._checkHttp(providerName, apiToken, apiKeyResult, configUsed);
    }
  }

  async _checkPostgres(apiToken, configUsed = null) {
    const startTime = performance.now();

    try {
      const sequelize = await apiToken.getClient();
      if (!sequelize) {
        return new ProviderConnectionResponse({
          provider: 'postgres',
          status: 'error',
          error: 'Failed to create Sequelize instance. Check sequelize/pg installation and credentials.',
          configUsed,
        });
      }

      // Use Sequelize's authenticate() to test connection
      await sequelize.authenticate();
      const latencyMs = performance.now() - startTime;

      // Close the connection
      await sequelize.close();

      return new ProviderConnectionResponse({
        provider: 'postgres',
        status: 'connected',
        latencyMs: Math.round(latencyMs * 100) / 100,
        message: 'PostgreSQL connection successful (Sequelize)',
        configUsed,
      });
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      return new ProviderConnectionResponse({
        provider: 'postgres',
        status: 'error',
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
        configUsed,
      });
    }
  }

  async _checkRedis(apiToken, configUsed = null) {
    const startTime = performance.now();

    try {
      const client = await apiToken.getClient();
      if (!client) {
        return new ProviderConnectionResponse({
          provider: 'redis',
          status: 'error',
          error: 'Failed to create Redis client. Check ioredis installation and credentials.',
          configUsed,
        });
      }

      const result = await client.ping();
      const latencyMs = performance.now() - startTime;
      await client.quit();

      if (result === 'PONG') {
        return new ProviderConnectionResponse({
          provider: 'redis',
          status: 'connected',
          latencyMs: Math.round(latencyMs * 100) / 100,
          message: 'Redis connection successful (PONG)',
          configUsed,
        });
      }

      return new ProviderConnectionResponse({
        provider: 'redis',
        status: 'error',
        error: 'PING did not return expected response',
        configUsed,
      });
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      return new ProviderConnectionResponse({
        provider: 'redis',
        status: 'error',
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
        configUsed,
      });
    }
  }

  async _checkElasticsearch(apiToken, configUsed = null) {
    // Use HTTP directly to support both Elasticsearch and OpenSearch
    // (the official @elastic/elasticsearch client rejects OpenSearch servers)
    // Uses proxy factory with YAML config for fetch dispatcher
    const startTime = performance.now();

    try {
      const connectionUrl = apiToken.getConnectionUrl();

      // Parse the URL to extract credentials and build auth header
      // fetch() doesn't allow credentials in the URL directly
      const parsedUrl = new URL(connectionUrl);
      const username = parsedUrl.username;
      const password = parsedUrl.password;

      // Remove credentials from URL for fetch
      parsedUrl.username = '';
      parsedUrl.password = '';
      // Build health URL - ensure no double slashes
      const baseUrl = parsedUrl.toString().replace(/\/+$/, '');
      const healthUrl = `${baseUrl}/_cluster/health`;

      // Get dispatcher from factory with YAML proxy config
      const dispatcher = await this.#clientFactory._createDispatcher();

      const headers = { 'Accept': 'application/json' };

      // Add Basic Auth header if credentials were in the URL
      if (username && password) {
        const credentials = Buffer.from(`${username}:${password}`).toString('base64');
        headers['Authorization'] = `Basic ${credentials}`;
      }

      const fetchOptions = {
        method: 'GET',
        headers,
      };

      // Add dispatcher if available (for proxy support)
      if (dispatcher) {
        fetchOptions.dispatcher = dispatcher;
      }

      const response = await fetch(healthUrl, fetchOptions);

      const latencyMs = performance.now() - startTime;

      if (response.ok) {
        const result = await response.json();

        if (result && result.cluster_name) {
          const status = result.status || 'unknown';
          return new ProviderConnectionResponse({
            provider: 'elasticsearch',
            status: 'connected',
            latencyMs: Math.round(latencyMs * 100) / 100,
            message: `Cluster '${result.cluster_name}' is ${status}`,
            configUsed,
          });
        }

        return new ProviderConnectionResponse({
          provider: 'elasticsearch',
          status: 'error',
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: 'Unexpected response from cluster health check',
          configUsed,
        });
      } else {
        const text = await response.text();
        return new ProviderConnectionResponse({
          provider: 'elasticsearch',
          status: 'error',
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: `HTTP ${response.status}: ${text.substring(0, 200)}`,
          configUsed,
        });
      }
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      return new ProviderConnectionResponse({
        provider: 'elasticsearch',
        status: 'error',
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
        configUsed,
      });
    }
  }

  async _checkHttp(providerName, apiToken, apiKeyResult, configUsed = null) {
    const startTime = performance.now();

    if (!apiKeyResult.hasCredentials) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        error: 'No API credentials configured',
        configUsed,
      });
    }

    const baseUrl = apiToken.getBaseUrl();
    if (!baseUrl) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        error: 'No base URL configured',
        configUsed,
      });
    }

    const client = await this.#clientFactory.getClient(apiToken.providerName);
    if (!client) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        error: 'Failed to create HTTP client',
        configUsed,
      });
    }

    try {
      const healthEndpoint = apiToken.healthEndpoint;
      const response = await client.get(healthEndpoint);
      const latencyMs = performance.now() - startTime;

      if (response.status >= 200 && response.status < 300) {
        const message = this._extractSuccessMessage(providerName, response.data);
        return new ProviderConnectionResponse({
          provider: providerName,
          status: 'connected',
          latencyMs: Math.round(latencyMs * 100) / 100,
          configUsed,
          message,
        });
      } else {
        return new ProviderConnectionResponse({
          provider: providerName,
          status: 'error',
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: `HTTP ${response.status}: ${JSON.stringify(response.data)}`,
          configUsed,
        });
      }
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
        configUsed,
      });
    } finally {
      try {
        await client.close();
      } catch {
        // Ignore close errors
      }
    }
  }

  _extractSuccessMessage(providerName, data) {
    if (!data || typeof data !== 'object') {
      return `Connected to ${providerName}`;
    }

    const providerLower = providerName.toLowerCase();

    if (providerLower === 'figma') {
      const email = data.email;
      if (email) return `Connected as ${email}`;
    } else if (providerLower === 'github') {
      const login = data.login;
      if (login) return `Connected as @${login}`;
    } else if (providerLower === 'jira' || providerLower === 'confluence') {
      const displayName = data.displayName;
      const email = data.emailAddress;
      if (displayName) return `Connected as ${displayName}`;
      if (email) return `Connected as ${email}`;
    } else if (['gemini', 'openai', 'gemini_openai'].includes(providerLower)) {
      const models = data.data;
      if (Array.isArray(models)) {
        return `Connected, ${models.length} models available`;
      }
    }

    return `Connected to ${providerName}`;
  }
}

let _checker = null;

/**
 * Check connectivity to a provider.
 *
 * Uses the ConfigStore singleton from @internal/static-config-property-management
 * to automatically load provider configuration.
 *
 * @param {string} providerName - Provider name (e.g., 'github', 'jira', 'figma')
 * @returns {Promise<ProviderConnectionResponse>} Health check result
 */
export async function checkProviderConnection(providerName) {
  if (_checker === null) {
    // Lazy-load ConfigStore singleton to avoid circular dependencies
    try {
      const { config } = await import('@internal/static-config-property-management');
      _checker = new ProviderHealthChecker(config);
    } catch {
      // Fallback to checker without config (will use env vars)
      _checker = new ProviderHealthChecker();
    }
  }
  return _checker.check(providerName);
}
