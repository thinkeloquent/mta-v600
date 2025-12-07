/**
 * In-memory DNS cache store implementation
 */

import type { CachedEntry, DnsCacheStore } from '../types.mjs';

/**
 * LRU eviction tracking
 */
interface LruEntry {
  key: string;
  accessedAt: number;
}

/**
 * In-memory DNS cache store with LRU eviction
 */
export class MemoryStore implements DnsCacheStore {
  private readonly cache: Map<string, CachedEntry> = new Map();
  private readonly maxEntries: number;
  private readonly lruOrder: Map<string, number> = new Map();
  private accessCounter = 0;

  constructor(maxEntries: number = 1000) {
    this.maxEntries = maxEntries;
  }

  async get(key: string): Promise<CachedEntry | undefined> {
    const entry = this.cache.get(key);
    if (entry) {
      // Update LRU access time
      this.lruOrder.set(key, ++this.accessCounter);
    }
    return entry;
  }

  async set(key: string, entry: CachedEntry): Promise<void> {
    // Evict if at capacity
    if (!this.cache.has(key) && this.cache.size >= this.maxEntries) {
      await this.evictLru();
    }

    this.cache.set(key, entry);
    this.lruOrder.set(key, ++this.accessCounter);
  }

  async delete(key: string): Promise<boolean> {
    this.lruOrder.delete(key);
    return this.cache.delete(key);
  }

  async has(key: string): Promise<boolean> {
    return this.cache.has(key);
  }

  async keys(): Promise<string[]> {
    return Array.from(this.cache.keys());
  }

  async size(): Promise<number> {
    return this.cache.size;
  }

  async clear(): Promise<void> {
    this.cache.clear();
    this.lruOrder.clear();
    this.accessCounter = 0;
  }

  async close(): Promise<void> {
    await this.clear();
  }

  /**
   * Evict the least recently used entry
   */
  private async evictLru(): Promise<void> {
    let oldestKey: string | undefined;
    let oldestAccess = Infinity;

    for (const [key, accessTime] of this.lruOrder) {
      if (accessTime < oldestAccess) {
        oldestAccess = accessTime;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      await this.delete(oldestKey);
    }
  }

  /**
   * Remove all expired entries
   */
  async pruneExpired(now: number = Date.now()): Promise<number> {
    let pruned = 0;

    for (const [key, entry] of this.cache) {
      if (now >= entry.expiresAt) {
        await this.delete(key);
        pruned++;
      }
    }

    return pruned;
  }

  /**
   * Get all entries (for debugging/stats)
   */
  async entries(): Promise<CachedEntry[]> {
    return Array.from(this.cache.values());
  }
}

/**
 * Create a memory store instance
 */
export function createMemoryStore(maxEntries?: number): MemoryStore {
  return new MemoryStore(maxEntries);
}

export default MemoryStore;
