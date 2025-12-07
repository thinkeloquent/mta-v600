/**
 * Redis rate limit store implementation
 * Suitable for distributed applications
 */

import type { RateLimitStore } from '../types.mjs';

/**
 * Redis client interface (compatible with ioredis)
 * We define this interface to avoid hard dependency on ioredis
 */
export interface RedisClient {
  incr(key: string): Promise<number>;
  pexpire(key: string, milliseconds: number): Promise<number>;
  get(key: string): Promise<string | null>;
  pttl(key: string): Promise<number>;
  del(key: string): Promise<number>;
  quit(): Promise<string>;
}

/**
 * Redis implementation of RateLimitStore
 * Uses Redis for distributed rate limiting across multiple processes/servers
 */
export class RedisStore implements RateLimitStore {
  private readonly client: RedisClient;
  private readonly keyPrefix: string;

  /**
   * Create a new RedisStore
   *
   * @param client - Redis client (ioredis instance)
   * @param keyPrefix - Prefix for all keys. Default: 'ratelimit:'
   */
  constructor(client: RedisClient, keyPrefix: string = 'ratelimit:') {
    this.client = client;
    this.keyPrefix = keyPrefix;
  }

  /**
   * Get the full key with prefix
   */
  private getKey(key: string): string {
    return `${this.keyPrefix}${key}`;
  }

  /**
   * Get the current count for a key
   */
  async getCount(key: string): Promise<number> {
    const value = await this.client.get(this.getKey(key));
    return value ? parseInt(value, 10) : 0;
  }

  /**
   * Increment the count for a key
   * Uses INCR + PEXPIRE in sequence (not atomic, but sufficient for rate limiting)
   */
  async increment(key: string, ttlMs: number): Promise<number> {
    const fullKey = this.getKey(key);
    const count = await this.client.incr(fullKey);

    // Set expiry only on first increment (when count is 1)
    if (count === 1) {
      await this.client.pexpire(fullKey, ttlMs);
    }

    return count;
  }

  /**
   * Get the TTL remaining for a key
   */
  async getTTL(key: string): Promise<number> {
    const ttl = await this.client.pttl(this.getKey(key));
    // PTTL returns -2 if key doesn't exist, -1 if no expiry
    return ttl > 0 ? ttl : 0;
  }

  /**
   * Reset the count for a key
   */
  async reset(key: string): Promise<void> {
    await this.client.del(this.getKey(key));
  }

  /**
   * Close the store and cleanup resources
   */
  async close(): Promise<void> {
    await this.client.quit();
  }
}

/**
 * Create a new RedisStore instance
 *
 * @param client - Redis client (ioredis instance)
 * @param keyPrefix - Prefix for all keys
 */
export function createRedisStore(client: RedisClient, keyPrefix?: string): RedisStore {
  return new RedisStore(client, keyPrefix);
}

export default {
  RedisStore,
  createRedisStore,
};
