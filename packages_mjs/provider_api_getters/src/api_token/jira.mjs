/**
 * Jira API token getter.
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

export class JiraApiToken extends BaseApiToken {
  get providerName() {
    return 'jira';
  }

  get healthEndpoint() {
    return '/rest/api/2/myself';
  }

  _getEmail() {
    const providerConfig = this._getProviderConfig();
    const envEmail = providerConfig?.env_email || 'JIRA_EMAIL';
    return process.env[envEmail] || null;
  }

  getApiKey() {
    const apiToken = this._lookupEnvApiKey();
    const email = this._getEmail();

    if (apiToken && email) {
      const credentials = `${email}:${apiToken}`;
      const encoded = Buffer.from(credentials).toString('base64');
      return new ApiKeyResult({
        apiKey: `Basic ${encoded}`,
        authType: 'basic',
        headerName: 'Authorization',
        username: email,
      });
    }

    return new ApiKeyResult({
      apiKey: null,
      authType: 'basic',
      headerName: 'Authorization',
      username: email,
    });
  }

  getBaseUrl() {
    const baseUrl = super.getBaseUrl();
    if (baseUrl) return baseUrl;
    return process.env.JIRA_BASE_URL || null;
  }
}
