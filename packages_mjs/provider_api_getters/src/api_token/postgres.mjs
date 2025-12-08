/**
 * PostgreSQL connection getter.
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

export class PostgresApiToken extends BaseApiToken {
  get providerName() {
    return 'postgres';
  }

  get healthEndpoint() {
    return 'SELECT 1';
  }

  _buildConnectionUrl() {
    const host = process.env.POSTGRES_HOST;
    const port = process.env.POSTGRES_PORT || '5432';
    const user = process.env.POSTGRES_USER;
    const password = process.env.POSTGRES_PASSWORD;
    const database = process.env.POSTGRES_DB;

    if (host && user && database) {
      if (password) {
        return `postgresql://${user}:${password}@${host}:${port}/${database}`;
      }
      return `postgresql://${user}@${host}:${port}/${database}`;
    }
    return null;
  }

  getConnectionUrl() {
    const providerConfig = this._getProviderConfig();
    const envUrl = providerConfig?.env_connection_url || 'DATABASE_URL';
    let url = process.env[envUrl];
    if (!url) {
      url = this._buildConnectionUrl();
    }
    return url;
  }

  async getClient() {
    let pg;
    try {
      pg = await import('pg');
    } catch {
      return null;
    }

    const connectionUrl = this.getConnectionUrl();
    if (!connectionUrl) return null;

    try {
      const pool = new pg.default.Pool({ connectionString: connectionUrl, max: 1 });
      return pool;
    } catch {
      return null;
    }
  }

  getApiKey() {
    const connectionUrl = this.getConnectionUrl();
    return new ApiKeyResult({
      apiKey: connectionUrl,
      authType: 'connection_string',
      headerName: '',
      client: null,
    });
  }
}
