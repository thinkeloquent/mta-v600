/**
 * Priority queue implementation for rate limiter
 */

import type { QueuedRequest } from './types.mjs';

/**
 * Priority queue that orders requests by priority (higher first) and enqueue time (FIFO for same priority)
 */
export class PriorityQueue<T> {
  private items: QueuedRequest<T>[] = [];

  /**
   * Add a request to the queue
   *
   * @param request - The request to enqueue
   */
  enqueue(request: QueuedRequest<T>): void {
    // Find insertion point using binary search
    let low = 0;
    let high = this.items.length;

    while (low < high) {
      const mid = Math.floor((low + high) / 2);
      const midItem = this.items[mid];

      // Higher priority comes first
      if (midItem.priority > request.priority) {
        low = mid + 1;
      } else if (midItem.priority < request.priority) {
        high = mid;
      } else {
        // Same priority: FIFO - newer items go after older ones
        if (midItem.enqueuedAt <= request.enqueuedAt) {
          low = mid + 1;
        } else {
          high = mid;
        }
      }
    }

    this.items.splice(low, 0, request);
  }

  /**
   * Remove and return the highest priority request
   *
   * @returns The highest priority request, or undefined if empty
   */
  dequeue(): QueuedRequest<T> | undefined {
    return this.items.shift();
  }

  /**
   * Peek at the highest priority request without removing it
   *
   * @returns The highest priority request, or undefined if empty
   */
  peek(): QueuedRequest<T> | undefined {
    return this.items[0];
  }

  /**
   * Check if the queue is empty
   */
  isEmpty(): boolean {
    return this.items.length === 0;
  }

  /**
   * Get the current queue size
   */
  get size(): number {
    return this.items.length;
  }

  /**
   * Remove all expired requests from the queue
   *
   * @param now - Current timestamp
   * @returns Array of expired requests
   */
  removeExpired(now: number): QueuedRequest<T>[] {
    const expired: QueuedRequest<T>[] = [];
    this.items = this.items.filter((item) => {
      if (item.deadline && item.deadline < now) {
        expired.push(item);
        return false;
      }
      return true;
    });
    return expired;
  }

  /**
   * Remove all cancelled requests from the queue
   *
   * @returns Array of cancelled requests
   */
  removeCancelled(): QueuedRequest<T>[] {
    const cancelled: QueuedRequest<T>[] = [];
    this.items = this.items.filter((item) => {
      if (item.signal?.aborted) {
        cancelled.push(item);
        return false;
      }
      return true;
    });
    return cancelled;
  }

  /**
   * Remove a specific request by ID
   *
   * @param id - The request ID to remove
   * @returns The removed request, or undefined if not found
   */
  removeById(id: string): QueuedRequest<T> | undefined {
    const index = this.items.findIndex((item) => item.id === id);
    if (index !== -1) {
      return this.items.splice(index, 1)[0];
    }
    return undefined;
  }

  /**
   * Clear all items from the queue
   *
   * @returns Array of all removed requests
   */
  clear(): QueuedRequest<T>[] {
    const items = this.items;
    this.items = [];
    return items;
  }

  /**
   * Get all items in the queue (for debugging/monitoring)
   */
  getAll(): ReadonlyArray<QueuedRequest<T>> {
    return this.items;
  }
}

export default PriorityQueue;
