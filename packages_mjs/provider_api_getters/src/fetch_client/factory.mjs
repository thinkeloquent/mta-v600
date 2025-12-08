/**
 * Factory for creating pre-configured HTTP clients for providers.
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

export async function getProviderClient(providerName) {
  if (_factory === null) {
    _factory = new ProviderClientFactory();
  }
  return _factory.getClient(providerName);
}
