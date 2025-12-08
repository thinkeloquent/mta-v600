/**
 * Elasticsearch API token getter (placeholder).
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

export class ElasticsearchApiToken extends BaseApiToken {
  get providerName() {
    return 'elasticsearch';
  }

  get healthEndpoint() {
    return '/_cluster/health';
  }

  getApiKey() {
    const providerConfig = this._getProviderConfig();
    const message = providerConfig?.message || 'Elasticsearch integration not implemented';

    return new ApiKeyResult({
      apiKey: null,
      isPlaceholder: true,
      placeholderMessage: message,
    });
  }
}
