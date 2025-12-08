/**
 * Request coalescing (Singleflight) implementation
 *
 * When multiple identical requests are made concurrently, only one
 * actually executes - others wait and receive the same result.
 */

import { createHash } from 'node:crypto';
import type {
  SingleflightConfig,
  SingleflightStore,
  InFlightRequest,
  RequestFingerprint,
  SingleflightResult,
  CacheRequestEvent,
  CacheRequestEventListener,
} from './types.mjs';
import { MemorySingleflightStore } from './stores/memory.mjs';

/**
 * Default singleflight configuration
 */
export const DEFAULT_SINGLEFLIGHT_CONFIG: Required<SingleflightConfig> = {
  ttlMs: 30000, // 30 seconds
  methods: ['GET', 'HEAD'],
  fingerprintGenerator: defaultFingerprintGenerator,
  includeHeaders: false,
  headerKeys: [],
};

/**
 * Default fingerprint generator using SHA-256
 */
function defaultFingerprintGenerator(request: RequestFingerprint): string {
  const hash = createHash('sha256');
  hash.update(request.method);
  hash.update(request.url);

  if (request.body) {
    const bodyData =
      typeof request.body === 'string'
        ? request.body
        : request.body.toString('base64');
    hash.update(bodyData);
  }

  if (request.headers) {
    const sortedHeaders = Object.keys(request.headers)
      .sort()
      .map((k) => `${k}:${request.headers![k]}`)
      .join('|');
    hash.update(sortedHeaders);
  }

  return hash.digest('hex');
}

/**
 * Merge user config with defaults
 */
export function mergeSingleflightConfig(
  config?: SingleflightConfig
): Required<SingleflightConfig> {
  return {
    ...DEFAULT_SINGLEFLIGHT_CONFIG,
    ...config,
  };
}

/**
 * Singleflight - Request coalescing for concurrent identical requests
 *
 * Implements the "singleflight" pattern (popularized by Go's sync/singleflight):
 * When multiple goroutines/promises request the same resource simultaneously,
 * only one request is made and the result is shared with all waiters.
 *
 * @example
 * const sf = new Singleflight();
 *
 * // These 50 concurrent calls result in only 1 actual fetch
 * const results = await Promise.all(
 *   Array(50).fill(null).map(() =>
 *     sf.do({ method: 'GET', url: '/api/data' }, () => fetch('/api/data'))
 *   )
 * );
 *
 * // All 50 results are identical
 * console.log(results[0].shared); // true for 49, false for 1
 */
export class Singleflight {
  private readonly config: Required<SingleflightConfig>;
  private readonly store: SingleflightStore;
  private readonly listeners: Set<CacheRequestEventListener> = new Set();

  constructor(config?: SingleflightConfig, store?: SingleflightStore) {
    this.config = mergeSingleflightConfig(config);
    this.store = store ?? new MemorySingleflightStore();
  }

  /**
   * Check if a request method supports coalescing
   */
  supportsCoalescing(method: string): boolean {
    return this.config.methods.includes(method.toUpperCase());
  }

  /**
   * Generate a fingerprint for a request
   */
  generateFingerprint(request: RequestFingerprint): string {
    // Filter headers if needed
    let filteredRequest = request;
    if (this.config.includeHeaders && request.headers) {
      const filteredHeaders: Record<string, string> = {};
      for (const key of this.config.headerKeys) {
        const lowerKey = key.toLowerCase();
        for (const [k, v] of Object.entries(request.headers)) {
          if (k.toLowerCase() === lowerKey) {
            filteredHeaders[k] = v;
          }
        }
      }
      filteredRequest = { ...request, headers: filteredHeaders };
    } else if (!this.config.includeHeaders) {
      filteredRequest = { ...request, headers: undefined };
    }

    return this.config.fingerprintGenerator(filteredRequest);
  }

  /**
   * Execute a function with request coalescing
   *
   * If an identical request is already in-flight, wait for it and share the result.
   * Otherwise, execute the function and share the result with any subsequent waiters.
   */
  async do<T>(
    request: RequestFingerprint,
    fn: () => Promise<T>
  ): Promise<SingleflightResult<T>> {
    const fingerprint = this.generateFingerprint(request);

    // Check for in-flight request
    const existing = this.store.get<T>(fingerprint);
    if (existing) {
      existing.subscribers++;

      this.emit({
        type: 'singleflight:join',
        key: fingerprint,
        timestamp: Date.now(),
        metadata: { subscribers: existing.subscribers },
      });

      try {
        const value = await existing.promise;
        return {
          value,
          shared: true,
          subscribers: existing.subscribers,
        };
      } catch (error) {
        throw error;
      }
    }

    // Create new in-flight request
    let resolvePromise: (value: T) => void;
    let rejectPromise: (error: unknown) => void;

    const promise = new Promise<T>((resolve, reject) => {
      resolvePromise = resolve;
      rejectPromise = reject;
    });

    const inFlight: InFlightRequest<T> = {
      promise,
      subscribers: 1,
      startedAt: Date.now(),
    };

    this.store.set(fingerprint, inFlight);

    this.emit({
      type: 'singleflight:lead',
      key: fingerprint,
      timestamp: Date.now(),
    });

    try {
      const value = await fn();

      resolvePromise!(value);

      const finalSubscribers = this.store.get<T>(fingerprint)?.subscribers ?? 1;

      this.emit({
        type: 'singleflight:complete',
        key: fingerprint,
        timestamp: Date.now(),
        metadata: {
          subscribers: finalSubscribers,
          durationMs: Date.now() - inFlight.startedAt,
        },
      });

      this.store.delete(fingerprint);

      return {
        value,
        shared: false,
        subscribers: finalSubscribers,
      };
    } catch (error) {
      rejectPromise!(error);

      this.emit({
        type: 'singleflight:error',
        key: fingerprint,
        timestamp: Date.now(),
        metadata: { error: String(error) },
      });

      this.store.delete(fingerprint);

      throw error;
    }
  }

  /**
   * Check if a request is currently in-flight
   */
  isInFlight(request: RequestFingerprint): boolean {
    const fingerprint = this.generateFingerprint(request);
    return this.store.has(fingerprint);
  }

  /**
   * Get the number of subscribers for an in-flight request
   */
  getSubscribers(request: RequestFingerprint): number {
    const fingerprint = this.generateFingerprint(request);
    return this.store.get(fingerprint)?.subscribers ?? 0;
  }

  /**
   * Get statistics about in-flight requests
   */
  getStats(): { inFlight: number } {
    return { inFlight: this.store.size() };
  }

  /**
   * Get configuration
   */
  getConfig(): Required<SingleflightConfig> {
    return { ...this.config };
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
   * Clear all in-flight requests (use with caution)
   */
  clear(): void {
    this.store.clear();
  }

  /**
   * Close and release resources
   */
  close(): void {
    this.store.clear();
    this.listeners.clear();
  }
}

/**
 * Create a singleflight instance
 */
export function createSingleflight(
  config?: SingleflightConfig,
  store?: SingleflightStore
): Singleflight {
  return new Singleflight(config, store);
}
