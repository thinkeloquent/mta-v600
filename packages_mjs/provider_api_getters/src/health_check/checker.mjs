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
  }) {
    this.provider = provider;
    this.status = status;
    this.latency_ms = latencyMs;
    this.message = message;
    this.error = error;
    this.timestamp = timestamp || new Date().toISOString();
  }

  toJSON() {
    return {
      provider: this.provider,
      status: this.status,
      latency_ms: this.latency_ms,
      message: this.message,
      error: this.error,
      timestamp: this.timestamp,
    };
  }
}

export class ProviderHealthChecker {
  #configStore = null;
  #clientFactory = null;

  constructor(configStore = null) {
    this.#configStore = configStore;
    this.#clientFactory = new ProviderClientFactory(configStore);
  }

  get configStore() {
    return this.#configStore;
  }

  set configStore(value) {
    this.#configStore = value;
    this.#clientFactory.configStore = value;
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

    if (apiKeyResult.isPlaceholder) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'not_implemented',
        message: apiKeyResult.placeholderMessage,
      });
    }

    if (providerNameLower === 'postgres') {
      return this._checkPostgres(apiToken);
    } else if (providerNameLower === 'redis') {
      return this._checkRedis(apiToken);
    } else if (providerNameLower === 'elasticsearch') {
      return this._checkElasticsearch(apiToken);
    } else {
      return this._checkHttp(providerName, apiToken, apiKeyResult);
    }
  }

  async _checkPostgres(apiToken) {
    const startTime = performance.now();

    try {
      const pool = await apiToken.getClient();
      if (!pool) {
        return new ProviderConnectionResponse({
          provider: 'postgres',
          status: 'error',
          error: 'Failed to create connection pool. Check pg installation and credentials.',
        });
      }

      const client = await pool.connect();
      const result = await client.query('SELECT 1 as result');
      const latencyMs = performance.now() - startTime;

      client.release();
      await pool.end();

      if (result.rows[0]?.result === 1) {
        return new ProviderConnectionResponse({
          provider: 'postgres',
          status: 'connected',
          latencyMs: Math.round(latencyMs * 100) / 100,
          message: 'PostgreSQL connection successful',
        });
      }

      return new ProviderConnectionResponse({
        provider: 'postgres',
        status: 'error',
        error: 'Unexpected query result',
      });
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      return new ProviderConnectionResponse({
        provider: 'postgres',
        status: 'error',
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
      });
    }
  }

  async _checkRedis(apiToken) {
    const startTime = performance.now();

    try {
      const client = await apiToken.getClient();
      if (!client) {
        return new ProviderConnectionResponse({
          provider: 'redis',
          status: 'error',
          error: 'Failed to create Redis client. Check ioredis installation and credentials.',
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
        });
      }

      return new ProviderConnectionResponse({
        provider: 'redis',
        status: 'error',
        error: 'PING did not return expected response',
      });
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      return new ProviderConnectionResponse({
        provider: 'redis',
        status: 'error',
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
      });
    }
  }

  async _checkElasticsearch(apiToken) {
    // Use HTTP directly to support both Elasticsearch and OpenSearch
    // (the official @elastic/elasticsearch client rejects OpenSearch servers)
    // Uses proxy factory with YAML config for fetch dispatcher
    const startTime = performance.now();

    try {
      const connectionUrl = apiToken.getConnectionUrl();
      const healthUrl = `${connectionUrl}/_cluster/health`;

      // Get dispatcher from factory with YAML proxy config
      const dispatcher = await this.#clientFactory._createDispatcher();

      const fetchOptions = {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
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
          });
        }

        return new ProviderConnectionResponse({
          provider: 'elasticsearch',
          status: 'error',
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: 'Unexpected response from cluster health check',
        });
      } else {
        const text = await response.text();
        return new ProviderConnectionResponse({
          provider: 'elasticsearch',
          status: 'error',
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: `HTTP ${response.status}: ${text.substring(0, 200)}`,
        });
      }
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      return new ProviderConnectionResponse({
        provider: 'elasticsearch',
        status: 'error',
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
      });
    }
  }

  async _checkHttp(providerName, apiToken, apiKeyResult) {
    const startTime = performance.now();

    if (!apiKeyResult.hasCredentials) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        error: 'No API credentials configured',
      });
    }

    const baseUrl = apiToken.getBaseUrl();
    if (!baseUrl) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        error: 'No base URL configured',
      });
    }

    const client = await this.#clientFactory.getClient(apiToken.providerName);
    if (!client) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        error: 'Failed to create HTTP client',
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
          message,
        });
      } else {
        return new ProviderConnectionResponse({
          provider: providerName,
          status: 'error',
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: `HTTP ${response.status}: ${JSON.stringify(response.data)}`,
        });
      }
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      return new ProviderConnectionResponse({
        provider: providerName,
        status: 'error',
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
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
