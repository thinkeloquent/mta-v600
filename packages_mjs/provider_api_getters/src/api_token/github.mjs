/**
 * GitHub API token getter.
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

const FALLBACK_ENV_VARS = ['GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_ACCESS_TOKEN', 'GITHUB_PAT'];

export class GithubApiToken extends BaseApiToken {
  get providerName() {
    return 'github';
  }

  get healthEndpoint() {
    return '/user';
  }

  getApiKey() {
    let apiKey = this._lookupEnvApiKey();

    if (!apiKey) {
      for (const envVar of FALLBACK_ENV_VARS) {
        apiKey = process.env[envVar];
        if (apiKey) break;
      }
    }

    return new ApiKeyResult({
      apiKey,
      authType: 'bearer',
      headerName: 'Authorization',
    });
  }
}
