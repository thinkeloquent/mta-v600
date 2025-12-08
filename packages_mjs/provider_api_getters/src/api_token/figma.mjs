/**
 * Figma API token getter.
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

export class FigmaApiToken extends BaseApiToken {
  get providerName() {
    return 'figma';
  }

  get healthEndpoint() {
    return '/v1/me';
  }

  getApiKey() {
    const apiKey = this._lookupEnvApiKey();
    return new ApiKeyResult({
      apiKey,
      authType: 'x-api-key',
      headerName: 'X-Figma-Token',
    });
  }
}
