/**
 * Rally API token getter (placeholder).
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

export class RallyApiToken extends BaseApiToken {
  get providerName() {
    return 'rally';
  }

  get healthEndpoint() {
    return '/';
  }

  getApiKey() {
    const providerConfig = this._getProviderConfig();
    const message = providerConfig?.message || 'Rally integration not implemented';

    return new ApiKeyResult({
      apiKey: null,
      isPlaceholder: true,
      placeholderMessage: message,
    });
  }
}
