/**
 * Idempotency key management for HTTP requests
 */

import { randomUUID } from 'node:crypto';
import type {
  IdempotencyConfig,
  CacheRequestStore,
  StoredResponse,
  IdempotencyCheckResult,
  RequestFingerprint,
  CacheRequestEvent,
  CacheRequestEventListener,
} from './types.mjs';
import { MemoryCacheStore } from './stores/memory.mjs';

/**
 * Default idempotency configuration
 */
export const DEFAULT_IDEMPOTENCY_CONFIG: Required<IdempotencyConfig> = {
  headerName: 'Idempotency-Key',
  ttlMs: 86400000, // 24 hours
  autoGenerate: true,
  methods: ['POST', 'PATCH'],
  keyGenerator: () => randomUUID(),
};

/**
 * Merge user config with defaults
 */
export function mergeIdempotencyConfig(
  config?: IdempotencyConfig
): Required<IdempotencyConfig> {
  return {
    ...DEFAULT_IDEMPOTENCY_CONFIG,
    ...config,
  };
}

/**
 * Generate a request fingerprint for validation
 */
export function generateFingerprint(request: RequestFingerprint): string {
  const parts = [request.method, request.url];

  if (request.body) {
    const bodyStr =
      typeof request.body === 'string'
        ? request.body
        : request.body.toString('base64');
    parts.push(bodyStr);
  }

  return parts.join('|');
}

/**
 * IdempotencyManager - Manages idempotency keys and cached responses
 *
 * For mutating operations (POST, PATCH), ensures that:
 * 1. Each request intent is processed exactly once
 * 2. Retries use the same idempotency key
 * 3. Duplicate requests return cached responses
 *
 * @example
 * const manager = new IdempotencyManager({ ttlMs: 3600000 });
 *
 * // Check for cached response
 * const check = await manager.check('my-key');
 * if (check.cached) {
 *   return check.response.value;
 * }
 *
 * // Execute request and store response
 * const response = await fetch(url);
 * await manager.store(check.key, response);
 */
export class IdempotencyManager {
  private readonly config: Required<IdempotencyConfig>;
  private readonly store: CacheRequestStore;
  private readonly listeners: Set<CacheRequestEventListener> = new Set();

  constructor(config?: IdempotencyConfig, store?: CacheRequestStore) {
    this.config = mergeIdempotencyConfig(config);
    this.store = store ?? new MemoryCacheStore();
  }

  /**
   * Generate a new idempotency key
   */
  generateKey(): string {
    return this.config.keyGenerator();
  }

  /**
   * Check if a request method requires idempotency
   */
  requiresIdempotency(method: string): boolean {
    return this.config.methods.includes(method.toUpperCase());
  }

  /**
   * Check for a cached response by idempotency key
   */
  async check<T>(
    key: string,
    fingerprint?: RequestFingerprint
  ): Promise<IdempotencyCheckResult<T>> {
    const response = await this.store.get<T>(key);

    if (response) {
      // Validate fingerprint if provided
      if (fingerprint && response.fingerprint) {
        const currentFingerprint = generateFingerprint(fingerprint);
        if (currentFingerprint !== response.fingerprint) {
          // Different request using same key - this is an error
          throw new IdempotencyConflictError(
            `Idempotency key '${key}' is already associated with a different request`
          );
        }
      }

      this.emit({
        type: 'idempotency:hit',
        key,
        timestamp: Date.now(),
        metadata: { cachedAt: response.cachedAt },
      });

      return { cached: true, key, response };
    }

    this.emit({
      type: 'idempotency:miss',
      key,
      timestamp: Date.now(),
    });

    return { cached: false, key };
  }

  /**
   * Store a response with an idempotency key
   */
  async storeResponse<T>(
    key: string,
    value: T,
    fingerprint?: RequestFingerprint
  ): Promise<void> {
    const now = Date.now();
    const response: StoredResponse<T> = {
      value,
      cachedAt: now,
      expiresAt: now + this.config.ttlMs,
      fingerprint: fingerprint ? generateFingerprint(fingerprint) : undefined,
    };

    await this.store.set(key, response);

    this.emit({
      type: 'idempotency:store',
      key,
      timestamp: now,
      metadata: { expiresAt: response.expiresAt },
    });
  }

  /**
   * Invalidate a cached response
   */
  async invalidate(key: string): Promise<boolean> {
    const deleted = await this.store.delete(key);

    if (deleted) {
      this.emit({
        type: 'idempotency:expire',
        key,
        timestamp: Date.now(),
      });
    }

    return deleted;
  }

  /**
   * Get the idempotency header name
   */
  getHeaderName(): string {
    return this.config.headerName;
  }

  /**
   * Get configuration
   */
  getConfig(): Required<IdempotencyConfig> {
    return { ...this.config };
  }

  /**
   * Get store statistics
   */
  async getStats(): Promise<{ size: number }> {
    return { size: await this.store.size() };
  }

  /**
   * Add event listener
   */
  on(listener: CacheRequestEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Remove event listener
   */
  off(listener: CacheRequestEventListener): void {
    this.listeners.delete(listener);
  }

  private emit(event: CacheRequestEvent): void {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch {
        // Ignore listener errors
      }
    }
  }

  /**
   * Close the manager and release resources
   */
  async close(): Promise<void> {
    await this.store.close();
    this.listeners.clear();
  }
}

/**
 * Error thrown when an idempotency key conflict occurs
 */
export class IdempotencyConflictError extends Error {
  readonly code = 'IDEMPOTENCY_CONFLICT';

  constructor(message: string) {
    super(message);
    this.name = 'IdempotencyConflictError';
  }
}

/**
 * Create an idempotency manager
 */
export function createIdempotencyManager(
  config?: IdempotencyConfig,
  store?: CacheRequestStore
): IdempotencyManager {
  return new IdempotencyManager(config, store);
}
