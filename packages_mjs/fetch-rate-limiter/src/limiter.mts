/**
 * Main rate limiter implementation
 */

import type {
  RateLimiterConfig,
  RateLimiterStats,
  RateLimiterEvent,
  RateLimiterEventListener,
  ScheduleOptions,
  ScheduleResult,
  QueuedRequest,
  RateLimitStore,
  RateLimitStatus,
} from './types.mjs';
import {
  mergeConfig,
  calculateBackoffDelay,
  isRetryableError,
  generateRequestId,
  sleep,
} from './config.mjs';
import { PriorityQueue } from './queue.mjs';
import { MemoryStore } from './stores/memory.mjs';

/**
 * API Rate Limiter
 *
 * Manages outgoing API requests with:
 * - Static or dynamic rate limiting
 * - Priority queue with FIFO ordering within priorities
 * - Retry with exponential backoff and jitter
 * - Concurrency control
 * - Distributed state via pluggable stores
 */
export class RateLimiter {
  private readonly config: RateLimiterConfig;
  private readonly queue: PriorityQueue<unknown>;
  private readonly store: RateLimitStore;
  private readonly listeners: Set<RateLimiterEventListener> = new Set();

  private activeRequests = 0;
  private totalProcessed = 0;
  private totalRejected = 0;
  private totalQueueTimeMs = 0;
  private totalExecutionTimeMs = 0;
  private processing = false;
  private destroyed = false;

  /**
   * Create a new RateLimiter
   *
   * @param config - Rate limiter configuration
   * @param store - Optional custom store for distributed rate limiting
   */
  constructor(config: RateLimiterConfig, store?: RateLimitStore) {
    this.config = mergeConfig(config);
    this.queue = new PriorityQueue();
    this.store = store ?? new MemoryStore();
  }

  /**
   * Get the store key for this limiter
   */
  private getStoreKey(): string {
    return `limiter:${this.config.id}`;
  }

  /**
   * Emit an event to all listeners
   */
  private emit(event: RateLimiterEvent): void {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch {
        // Ignore listener errors
      }
    }
  }

  /**
   * Check if we can make a request based on rate limits
   */
  private async canMakeRequest(): Promise<{ allowed: boolean; waitMs: number }> {
    if (this.config.dynamic) {
      try {
        const status = await this.config.dynamic.getRateLimitStatus();
        if (status.remaining <= 0) {
          const waitMs = Math.max(0, status.reset * 1000 - Date.now());
          return { allowed: false, waitMs };
        }
        return { allowed: true, waitMs: 0 };
      } catch {
        // Fall back to static if dynamic fails
        if (this.config.dynamic.fallback) {
          return this.checkStaticLimit(this.config.dynamic.fallback);
        }
        // If no fallback, allow the request
        return { allowed: true, waitMs: 0 };
      }
    }

    if (this.config.static) {
      return this.checkStaticLimit(this.config.static);
    }

    // No rate limiting configured
    return { allowed: true, waitMs: 0 };
  }

  /**
   * Check static rate limit
   */
  private async checkStaticLimit(
    config: { maxRequests: number; intervalMs: number }
  ): Promise<{ allowed: boolean; waitMs: number }> {
    const key = this.getStoreKey();
    const count = await this.store.getCount(key);

    if (count >= config.maxRequests) {
      const ttl = await this.store.getTTL(key);
      return { allowed: false, waitMs: ttl };
    }

    return { allowed: true, waitMs: 0 };
  }

  /**
   * Record a request for rate limiting
   */
  private async recordRequest(): Promise<void> {
    if (this.config.static) {
      const key = this.getStoreKey();
      await this.store.increment(key, this.config.static.intervalMs);
    }
  }

  /**
   * Process the queue
   */
  private async processQueue(): Promise<void> {
    if (this.processing || this.destroyed) {
      return;
    }

    this.processing = true;

    try {
      while (!this.queue.isEmpty() && !this.destroyed) {
        // Check concurrency limit
        if (this.activeRequests >= (this.config.concurrency ?? 1)) {
          break;
        }

        // Remove expired and cancelled requests
        const now = Date.now();
        const expired = this.queue.removeExpired(now);
        for (const req of expired) {
          this.emit({
            type: 'request:expired',
            deadline: req.deadline!,
            metadata: req.metadata,
          });
          req.reject(new Error('Request deadline exceeded'));
          this.totalRejected++;
        }

        const cancelled = this.queue.removeCancelled();
        for (const req of cancelled) {
          req.reject(new Error('Request cancelled'));
          this.totalRejected++;
        }

        // Check rate limit
        const { allowed, waitMs } = await this.canMakeRequest();
        if (!allowed) {
          this.emit({ type: 'rate:limited', waitMs });
          await sleep(waitMs);
          continue;
        }

        // Get next request
        const request = this.queue.dequeue();
        if (!request) {
          break;
        }

        // Process request (don't await - run concurrently)
        this.executeRequest(request);
      }
    } finally {
      this.processing = false;
    }
  }

  /**
   * Execute a single request with retries
   */
  private async executeRequest<T>(request: QueuedRequest<T>): Promise<void> {
    const queueTime = Date.now() - request.enqueuedAt;
    this.totalQueueTimeMs += queueTime;
    this.activeRequests++;

    this.emit({
      type: 'request:started',
      metadata: request.metadata,
    });

    const startTime = Date.now();
    let retries = 0;
    let lastError: Error | null = null;

    try {
      await this.recordRequest();

      const maxRetries = this.config.retry?.maxRetries ?? 3;

      while (retries <= maxRetries) {
        try {
          if (request.signal?.aborted) {
            throw new Error('Request cancelled');
          }

          const result = await request.fn();
          const executionTime = Date.now() - startTime;
          this.totalExecutionTimeMs += executionTime;
          this.totalProcessed++;

          this.emit({
            type: 'request:completed',
            durationMs: executionTime,
            metadata: request.metadata,
          });

          request.resolve({
            result,
            queueTime,
            executionTime,
            retries,
          } as ScheduleResult<T>);

          return;
        } catch (error) {
          lastError = error as Error;

          if (!isRetryableError(lastError, this.config.retry ?? {})) {
            throw lastError;
          }

          if (retries >= maxRetries) {
            throw lastError;
          }

          retries++;
          const delay = calculateBackoffDelay(retries, this.config.retry ?? {});

          this.emit({
            type: 'request:requeued',
            reason: lastError.message,
            metadata: request.metadata,
          });

          await sleep(delay, request.signal);
        }
      }

      throw lastError;
    } catch (error) {
      this.emit({
        type: 'request:failed',
        error: error as Error,
        retries,
        metadata: request.metadata,
      });

      request.reject(error as Error);
      this.totalRejected++;
    } finally {
      this.activeRequests--;

      // Trigger queue processing
      setImmediate(() => this.processQueue());
    }
  }

  /**
   * Schedule a function for rate-limited execution
   *
   * @param fn - Async function to execute
   * @param options - Schedule options
   * @returns Promise resolving to the schedule result
   *
   * @example
   * const result = await limiter.schedule(async () => {
   *   return fetch('https://api.example.com/data');
   * }, { priority: 1 });
   */
  schedule<T>(
    fn: () => Promise<T>,
    options: ScheduleOptions = {}
  ): Promise<ScheduleResult<T>> {
    if (this.destroyed) {
      return Promise.reject(new Error('RateLimiter has been destroyed'));
    }

    const { priority = 0, metadata, deadline, signal } = options;
    const maxQueueSize = this.config.maxQueueSize ?? Infinity;

    if (this.queue.size >= maxQueueSize) {
      this.totalRejected++;
      return Promise.reject(new Error('Queue is full'));
    }

    return new Promise<ScheduleResult<T>>((resolve, reject) => {
      const request: QueuedRequest<T> = {
        id: generateRequestId(),
        fn,
        priority,
        enqueuedAt: Date.now(),
        deadline,
        metadata,
        resolve,
        reject,
        signal,
      };

      this.queue.enqueue(request as QueuedRequest<unknown>);

      this.emit({
        type: 'request:queued',
        priority,
        queueSize: this.queue.size,
      });

      // Trigger queue processing
      setImmediate(() => this.processQueue());
    });
  }

  /**
   * Get current statistics
   */
  getStats(): RateLimiterStats {
    const processed = this.totalProcessed || 1; // Avoid division by zero
    return {
      queueSize: this.queue.size,
      activeRequests: this.activeRequests,
      totalProcessed: this.totalProcessed,
      totalRejected: this.totalRejected,
      avgQueueTimeMs: this.totalQueueTimeMs / processed,
      avgExecutionTimeMs: this.totalExecutionTimeMs / processed,
    };
  }

  /**
   * Add an event listener
   *
   * @param listener - Event listener function
   * @returns Function to remove the listener
   */
  on(listener: RateLimiterEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Remove an event listener
   */
  off(listener: RateLimiterEventListener): void {
    this.listeners.delete(listener);
  }

  /**
   * Destroy the rate limiter and clean up resources
   */
  async destroy(): Promise<void> {
    this.destroyed = true;

    // Reject all pending requests
    const pending = this.queue.clear();
    for (const request of pending) {
      request.reject(new Error('RateLimiter destroyed'));
    }

    // Close the store
    await this.store.close();

    // Clear listeners
    this.listeners.clear();
  }
}

/**
 * Create a new rate limiter instance
 */
export function createRateLimiter(
  config: RateLimiterConfig,
  store?: RateLimitStore
): RateLimiter {
  return new RateLimiter(config, store);
}

export default {
  RateLimiter,
  createRateLimiter,
};
