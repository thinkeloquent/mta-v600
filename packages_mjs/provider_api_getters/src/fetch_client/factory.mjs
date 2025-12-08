/**
 * Factory for creating pre-configured HTTP clients for providers.
 *
 * This module uses the ConfigStore singleton from @internal/app-static-config-yaml
 * and the proxy dispatcher from @internal/fetch-proxy-dispatcher.
 */
import { getApiTokenClass } from '../api_token/index.mjs';

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

  async _createDispatcher() {
    try {
      const { getProxyDispatcher } = await import('@internal/fetch-proxy-dispatcher');
      const proxyConfig = this._getProxyConfig();
      return getProxyDispatcher({
        disableTls: proxyConfig?.cert_verify === false,
      });
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

    const baseUrl = apiToken.getBaseUrl();
    if (!baseUrl) return null;

    const apiKeyResult = apiToken.getApiKey();
    if (apiKeyResult.isPlaceholder) return null;

    const dispatcher = await this._createDispatcher();

    let auth;
    if (apiKeyResult.apiKey) {
      if (apiKeyResult.authType === 'basic' || apiKeyResult.authType === 'x-api-key') {
        auth = {
          type: 'custom',
          apiKey: apiKeyResult.apiKey,
          headerName: apiKeyResult.headerName,
        };
      } else {
        auth = {
          type: 'bearer',
          apiKey: apiKeyResult.apiKey,
        };
      }
    }

    const client = createClient({
      baseUrl,
      dispatcher,
      auth,
    });

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
