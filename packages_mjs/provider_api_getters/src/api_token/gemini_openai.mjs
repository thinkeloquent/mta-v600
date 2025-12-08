/**
 * Gemini/OpenAI API token getter.
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

export class GeminiOpenAIApiToken extends BaseApiToken {
  get providerName() {
    return 'gemini';
  }

  get healthEndpoint() {
    return '/models';
  }

  getApiKey() {
    const apiKey = this._lookupEnvApiKey();
    return new ApiKeyResult({
      apiKey,
      authType: 'bearer',
      headerName: 'Authorization',
    });
  }
}
