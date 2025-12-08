/**
 * In-memory cache store for RFC 7234 HTTP response caching
 */

import type { CacheResponseStore, CachedResponse } from '../types.mjs';

/**
 * LRU cache entry
 */
interface LruEntry {
  response: CachedResponse;
  size: number;
}

/**
 * In-memory cache store with LRU eviction
 */
export class MemoryCacheStore implements CacheResponseStore {
  private cache: Map<string, LruEntry> = new Map();
  private currentSize: number = 0;
  private cleanupInterval: ReturnType<typeof setInterval> | null = null;

  private readonly maxSize: number;
  private readonly maxEntries: number;
  private readonly maxEntrySize: number;
  private readonly cleanupIntervalMs: number;

  constructor(options: MemoryCacheStoreOptions = {}) {
    this.maxSize = options.maxSize ?? 100 * 1024 * 1024; // 100MB default
    this.maxEntries = options.maxEntries ?? 1000;
    this.maxEntrySize = options.maxEntrySize ?? 5 * 1024 * 1024; // 5MB default
    this.cleanupIntervalMs = options.cleanupIntervalMs ?? 60000; // 1 minute

    this.startCleanup();
  }

  private startCleanup(): void {
    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, this.cleanupIntervalMs);

    // Unref to not prevent process exit
    if (this.cleanupInterval.unref) {
      this.cleanupInterval.unref();
    }
  }

  private cleanup(): void {
    const now = Date.now();
    const keysToDelete: string[] = [];

    for (const [key, entry] of this.cache.entries()) {
      const { metadata } = entry.response;
      const { directives } = metadata;

      // Calculate the total window including stale-while-revalidate and stale-if-error
      const staleWindow = Math.max(
        ((directives?.staleWhileRevalidate ?? 0) * 1000),
        ((directives?.staleIfError ?? 0) * 1000)
      );

      if (metadata.expiresAt + staleWindow <= now) {
        keysToDelete.push(key);
      }
    }

    for (const key of keysToDelete) {
      this.deleteEntry(key);
    }
  }

  private deleteEntry(key: string): boolean {
    const entry = this.cache.get(key);
    if (entry) {
      this.currentSize -= entry.size;
      this.cache.delete(key);
      return true;
    }
    return false;
  }

  private calculateEntrySize(response: CachedResponse): number {
    let size = 0;

    // Body size
    if (response.body) {
      if (Buffer.isBuffer(response.body)) {
        size += response.body.length;
      } else if (typeof response.body === 'string') {
        size += Buffer.byteLength(response.body, 'utf8');
      }
    }

    // Metadata size (rough estimate)
    size += JSON.stringify(response.metadata).length;

    return size;
  }

  private evictIfNeeded(requiredSize: number): void {
    // Evict by size
    while (this.currentSize + requiredSize > this.maxSize && this.cache.size > 0) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey) {
        this.deleteEntry(oldestKey);
      }
    }

    // Evict by entry count
    while (this.cache.size >= this.maxEntries) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey) {
        this.deleteEntry(oldestKey);
      }
    }
  }

  private moveToEnd(key: string): void {
    const entry = this.cache.get(key);
    if (entry) {
      this.cache.delete(key);
      this.cache.set(key, entry);
    }
  }

  async get(key: string): Promise<CachedResponse | null> {
    const entry = this.cache.get(key);
    if (!entry) {
      return null;
    }

    const now = Date.now();
    const { metadata } = entry.response;
    const { directives } = metadata;

    // Calculate the total window including stale-while-revalidate and stale-if-error
    const staleWindow = Math.max(
      ((directives?.staleWhileRevalidate ?? 0) * 1000),
      ((directives?.staleIfError ?? 0) * 1000)
    );

    // Check if expired (including stale window)
    if (metadata.expiresAt + staleWindow <= now) {
      this.deleteEntry(key);
      return null;
    }

    // Move to end for LRU
    this.moveToEnd(key);

    return entry.response;
  }

  async set(key: string, response: CachedResponse): Promise<void> {
    const size = this.calculateEntrySize(response);

    // Don't cache if entry is too large
    if (size > this.maxEntrySize) {
      return;
    }

    // Remove existing entry if present
    if (this.cache.has(key)) {
      this.deleteEntry(key);
    }

    // Evict entries if needed
    this.evictIfNeeded(size);

    // Store new entry
    this.cache.set(key, { response, size });
    this.currentSize += size;
  }

  async has(key: string): Promise<boolean> {
    const entry = this.cache.get(key);
    if (!entry) {
      return false;
    }

    const now = Date.now();
    const { metadata } = entry.response;
    const { directives } = metadata;

    // Calculate the total window including stale-while-revalidate and stale-if-error
    const staleWindow = Math.max(
      ((directives?.staleWhileRevalidate ?? 0) * 1000),
      ((directives?.staleIfError ?? 0) * 1000)
    );

    // Check if expired (including stale window)
    if (metadata.expiresAt + staleWindow <= now) {
      this.deleteEntry(key);
      return false;
    }

    return true;
  }

  async delete(key: string): Promise<boolean> {
    return this.deleteEntry(key);
  }

  async clear(): Promise<void> {
    this.cache.clear();
    this.currentSize = 0;
  }

  async size(): Promise<number> {
    this.cleanup();
    return this.cache.size;
  }

  async keys(): Promise<string[]> {
    this.cleanup();
    return Array.from(this.cache.keys());
  }

  async close(): Promise<void> {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.cache.clear();
    this.currentSize = 0;
  }

  /**
   * Get cache statistics
   */
  getStats(): MemoryCacheStats {
    return {
      entries: this.cache.size,
      sizeBytes: this.currentSize,
      maxSizeBytes: this.maxSize,
      maxEntries: this.maxEntries,
      utilizationPercent: (this.currentSize / this.maxSize) * 100,
    };
  }
}

/**
 * Options for memory cache store
 */
export interface MemoryCacheStoreOptions {
  /** Maximum total cache size in bytes. Default: 100MB */
  maxSize?: number;
  /** Maximum number of entries. Default: 1000 */
  maxEntries?: number;
  /** Maximum size per entry in bytes. Default: 5MB */
  maxEntrySize?: number;
  /** Cleanup interval in milliseconds. Default: 60000 */
  cleanupIntervalMs?: number;
}

/**
 * Memory cache statistics
 */
export interface MemoryCacheStats {
  entries: number;
  sizeBytes: number;
  maxSizeBytes: number;
  maxEntries: number;
  utilizationPercent: number;
}

/**
 * Create a memory cache store
 */
export function createMemoryCacheStore(
  options?: MemoryCacheStoreOptions
): MemoryCacheStore {
  return new MemoryCacheStore(options);
}
