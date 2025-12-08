/**
 * Memory store implementations for cache-request
 */

import type {
  CacheRequestStore,
  StoredResponse,
  SingleflightStore,
  InFlightRequest,
} from '../types.mjs';

/**
 * In-memory cache store for idempotency responses
 */
export class MemoryCacheStore implements CacheRequestStore {
  private cache: Map<string, StoredResponse> = new Map();
  private cleanupInterval: ReturnType<typeof setInterval> | null = null;
  private readonly cleanupIntervalMs: number;

  constructor(options: { cleanupIntervalMs?: number } = {}) {
    this.cleanupIntervalMs = options.cleanupIntervalMs ?? 60000; // 1 minute default
    this.startCleanup();
  }

  private startCleanup(): void {
    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, this.cleanupIntervalMs);
  }

  private cleanup(): void {
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (entry.expiresAt <= now) {
        this.cache.delete(key);
      }
    }
  }

  async get<T>(key: string): Promise<StoredResponse<T> | null> {
    const entry = this.cache.get(key);
    if (!entry) {
      return null;
    }

    // Check if expired
    if (entry.expiresAt <= Date.now()) {
      this.cache.delete(key);
      return null;
    }

    return entry as StoredResponse<T>;
  }

  async set<T>(key: string, response: StoredResponse<T>): Promise<void> {
    this.cache.set(key, response as StoredResponse);
  }

  async has(key: string): Promise<boolean> {
    const entry = this.cache.get(key);
    if (!entry) {
      return false;
    }

    // Check if expired
    if (entry.expiresAt <= Date.now()) {
      this.cache.delete(key);
      return false;
    }

    return true;
  }

  async delete(key: string): Promise<boolean> {
    return this.cache.delete(key);
  }

  async clear(): Promise<void> {
    this.cache.clear();
  }

  async size(): Promise<number> {
    // Clean up expired entries first
    this.cleanup();
    return this.cache.size;
  }

  async close(): Promise<void> {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.cache.clear();
  }
}

/**
 * In-memory store for tracking in-flight requests (singleflight)
 */
export class MemorySingleflightStore implements SingleflightStore {
  private inFlight: Map<string, InFlightRequest> = new Map();

  get<T>(fingerprint: string): InFlightRequest<T> | null {
    return (this.inFlight.get(fingerprint) as InFlightRequest<T>) ?? null;
  }

  set<T>(fingerprint: string, request: InFlightRequest<T>): void {
    this.inFlight.set(fingerprint, request as InFlightRequest);
  }

  delete(fingerprint: string): boolean {
    return this.inFlight.delete(fingerprint);
  }

  has(fingerprint: string): boolean {
    return this.inFlight.has(fingerprint);
  }

  size(): number {
    return this.inFlight.size;
  }

  clear(): void {
    this.inFlight.clear();
  }
}

/**
 * Create a memory cache store
 */
export function createMemoryCacheStore(
  options: { cleanupIntervalMs?: number } = {}
): MemoryCacheStore {
  return new MemoryCacheStore(options);
}

/**
 * Create a memory singleflight store
 */
export function createMemorySingleflightStore(): MemorySingleflightStore {
  return new MemorySingleflightStore();
}
