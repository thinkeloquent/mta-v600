/**
 * Redis connection getter.
 */
import { BaseApiToken, ApiKeyResult } from './base.mjs';

export class RedisApiToken extends BaseApiToken {
  get providerName() {
    return 'redis';
  }

  get healthEndpoint() {
    return 'PING';
  }

  _buildConnectionUrl() {
    const host = process.env.REDIS_HOST || 'localhost';
    const port = process.env.REDIS_PORT || '6379';
    const password = process.env.REDIS_PASSWORD;
    const db = process.env.REDIS_DB || '0';
    const username = process.env.REDIS_USERNAME;

    if (password) {
      if (username) {
        return `redis://${username}:${password}@${host}:${port}/${db}`;
      }
      return `redis://:${password}@${host}:${port}/${db}`;
    }
    return `redis://${host}:${port}/${db}`;
  }

  getConnectionUrl() {
    const providerConfig = this._getProviderConfig();
    const envUrl = providerConfig?.env_connection_url || 'REDIS_URL';
    let url = process.env[envUrl];
    if (!url) {
      url = this._buildConnectionUrl();
    }
    return url;
  }

  async getClient() {
    let Redis;
    try {
      const ioredis = await import('ioredis');
      Redis = ioredis.default;
    } catch {
      return null;
    }

    const connectionUrl = this.getConnectionUrl();
    if (!connectionUrl) return null;

    try {
      const client = new Redis(connectionUrl);
      return client;
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
