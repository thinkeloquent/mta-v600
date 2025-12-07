/**
 * In-memory rate limit store implementation
 * Suitable for single-process applications
 */

import type { RateLimitStore } from '../types.mjs';

interface StoreEntry {
  count: number;
  expiresAt: number;
}

/**
 * In-memory implementation of RateLimitStore
 * Uses a Map with automatic cleanup of expired entries
 */
export class MemoryStore implements RateLimitStore {
  private store: Map<string, StoreEntry> = new Map();
  private cleanupInterval: NodeJS.Timeout | null = null;
  private readonly cleanupIntervalMs: number;

  /**
   * Create a new MemoryStore
   *
   * @param cleanupIntervalMs - How often to run cleanup (ms). Default: 60000 (1 minute)
   */
  constructor(cleanupIntervalMs: number = 60000) {
    this.cleanupIntervalMs = cleanupIntervalMs;
    this.startCleanup();
  }

  /**
   * Start the cleanup interval
   */
  private startCleanup(): void {
    if (this.cleanupInterval) {
      return;
    }

    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, this.cleanupIntervalMs);

    // Don't prevent the process from exiting
    this.cleanupInterval.unref();
  }

  /**
   * Remove expired entries
   */
  private cleanup(): void {
    const now = Date.now();
    for (const [key, entry] of this.store) {
      if (entry.expiresAt <= now) {
        this.store.delete(key);
      }
    }
  }

  /**
   * Get the current count for a key
   */
  async getCount(key: string): Promise<number> {
    const entry = this.store.get(key);
    if (!entry) {
      return 0;
    }

    if (entry.expiresAt <= Date.now()) {
      this.store.delete(key);
      return 0;
    }

    return entry.count;
  }

  /**
   * Increment the count for a key
   */
  async increment(key: string, ttlMs: number): Promise<number> {
    const now = Date.now();
    const entry = this.store.get(key);

    if (!entry || entry.expiresAt <= now) {
      // Create new entry
      this.store.set(key, {
        count: 1,
        expiresAt: now + ttlMs,
      });
      return 1;
    }

    // Increment existing entry
    entry.count += 1;
    return entry.count;
  }

  /**
   * Get the TTL remaining for a key
   */
  async getTTL(key: string): Promise<number> {
    const entry = this.store.get(key);
    if (!entry) {
      return 0;
    }

    const remaining = entry.expiresAt - Date.now();
    return Math.max(0, remaining);
  }

  /**
   * Reset the count for a key
   */
  async reset(key: string): Promise<void> {
    this.store.delete(key);
  }

  /**
   * Close the store and cleanup resources
   */
  async close(): Promise<void> {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.store.clear();
  }

  /**
   * Get the current size of the store (for debugging)
   */
  get size(): number {
    return this.store.size;
  }
}

/**
 * Create a new MemoryStore instance
 */
export function createMemoryStore(cleanupIntervalMs?: number): MemoryStore {
  return new MemoryStore(cleanupIntervalMs);
}

export default {
  MemoryStore,
  createMemoryStore,
};
