/**
 * Tests for PriorityQueue
 *
 * Coverage includes:
 * - Statement/Branch/Condition coverage
 * - MC/DC for conditional logic
 * - Boundary value analysis
 * - State transition testing
 */

import { describe, it, expect, beforeEach } from '@jest/globals';
import { PriorityQueue } from '../src/queue.mjs';
import type { QueuedRequest } from '../src/types.mjs';

describe('PriorityQueue', () => {
  let queue: PriorityQueue<string>;

  const createRequest = (
    id: string,
    priority: number,
    enqueuedAt: number = Date.now(),
    deadline?: number
  ): QueuedRequest<string> => ({
    id,
    fn: async () => id,
    priority,
    enqueuedAt,
    deadline,
    metadata: { id },
    resolve: () => {},
    reject: () => {},
  });

  beforeEach(() => {
    queue = new PriorityQueue<string>();
  });

  describe('enqueue', () => {
    it('should add a single item to empty queue', () => {
      const request = createRequest('req1', 0);
      queue.enqueue(request);

      expect(queue.size).toBe(1);
      expect(queue.isEmpty()).toBe(false);
    });

    it('should maintain priority order (higher priority first)', () => {
      const low = createRequest('low', 0, 1000);
      const high = createRequest('high', 10, 1000);
      const medium = createRequest('medium', 5, 1000);

      queue.enqueue(low);
      queue.enqueue(high);
      queue.enqueue(medium);

      expect(queue.dequeue()?.id).toBe('high');
      expect(queue.dequeue()?.id).toBe('medium');
      expect(queue.dequeue()?.id).toBe('low');
    });

    it('should maintain FIFO order for same priority', () => {
      const first = createRequest('first', 5, 1000);
      const second = createRequest('second', 5, 2000);
      const third = createRequest('third', 5, 3000);

      queue.enqueue(first);
      queue.enqueue(second);
      queue.enqueue(third);

      expect(queue.dequeue()?.id).toBe('first');
      expect(queue.dequeue()?.id).toBe('second');
      expect(queue.dequeue()?.id).toBe('third');
    });

    it('should handle negative priorities', () => {
      const negative = createRequest('negative', -5, 1000);
      const zero = createRequest('zero', 0, 1000);
      const positive = createRequest('positive', 5, 1000);

      queue.enqueue(negative);
      queue.enqueue(zero);
      queue.enqueue(positive);

      expect(queue.dequeue()?.id).toBe('positive');
      expect(queue.dequeue()?.id).toBe('zero');
      expect(queue.dequeue()?.id).toBe('negative');
    });

    it('should handle large number of items', () => {
      const count = 1000;
      for (let i = 0; i < count; i++) {
        queue.enqueue(createRequest(`req${i}`, Math.random() * 100, i));
      }

      expect(queue.size).toBe(count);

      let lastPriority = Infinity;
      let lastTime = -Infinity;
      while (!queue.isEmpty()) {
        const item = queue.dequeue();
        if (!item) break;

        if (item.priority < lastPriority) {
          lastPriority = item.priority;
          lastTime = item.enqueuedAt;
        } else if (item.priority === lastPriority) {
          expect(item.enqueuedAt).toBeGreaterThanOrEqual(lastTime);
          lastTime = item.enqueuedAt;
        }
      }
    });
  });

  describe('dequeue', () => {
    it('should return undefined for empty queue', () => {
      expect(queue.dequeue()).toBeUndefined();
    });

    it('should remove and return highest priority item', () => {
      queue.enqueue(createRequest('req1', 1));
      queue.enqueue(createRequest('req2', 2));

      const item = queue.dequeue();
      expect(item?.id).toBe('req2');
      expect(queue.size).toBe(1);
    });

    it('should empty queue after dequeuing all items', () => {
      queue.enqueue(createRequest('req1', 0));
      queue.dequeue();

      expect(queue.isEmpty()).toBe(true);
      expect(queue.size).toBe(0);
    });
  });

  describe('peek', () => {
    it('should return undefined for empty queue', () => {
      expect(queue.peek()).toBeUndefined();
    });

    it('should return highest priority item without removing it', () => {
      queue.enqueue(createRequest('req1', 1));
      queue.enqueue(createRequest('req2', 2));

      expect(queue.peek()?.id).toBe('req2');
      expect(queue.size).toBe(2);
      expect(queue.peek()?.id).toBe('req2');
    });
  });

  describe('isEmpty', () => {
    it('should return true for new queue', () => {
      expect(queue.isEmpty()).toBe(true);
    });

    it('should return false after adding item', () => {
      queue.enqueue(createRequest('req1', 0));
      expect(queue.isEmpty()).toBe(false);
    });

    it('should return true after removing all items', () => {
      queue.enqueue(createRequest('req1', 0));
      queue.dequeue();
      expect(queue.isEmpty()).toBe(true);
    });
  });

  describe('size', () => {
    it('should be 0 for new queue', () => {
      expect(queue.size).toBe(0);
    });

    it('should track additions correctly', () => {
      queue.enqueue(createRequest('req1', 0));
      expect(queue.size).toBe(1);
      queue.enqueue(createRequest('req2', 0));
      expect(queue.size).toBe(2);
    });

    it('should track removals correctly', () => {
      queue.enqueue(createRequest('req1', 0));
      queue.enqueue(createRequest('req2', 0));
      queue.dequeue();
      expect(queue.size).toBe(1);
    });
  });

  describe('removeExpired', () => {
    it('should return empty array when no expired items', () => {
      const now = Date.now();
      queue.enqueue(createRequest('req1', 0, now, now + 10000));

      const expired = queue.removeExpired(now);
      expect(expired).toHaveLength(0);
      expect(queue.size).toBe(1);
    });

    it('should remove and return expired items', () => {
      const now = Date.now();
      queue.enqueue(createRequest('expired', 0, now, now - 1000));
      queue.enqueue(createRequest('valid', 0, now, now + 10000));

      const expired = queue.removeExpired(now);
      expect(expired).toHaveLength(1);
      expect(expired[0].id).toBe('expired');
      expect(queue.size).toBe(1);
    });

    it('should not remove items without deadline', () => {
      const now = Date.now();
      queue.enqueue(createRequest('noDeadline', 0, now));
      queue.enqueue(createRequest('expired', 0, now, now - 1000));

      const expired = queue.removeExpired(now);
      expect(expired).toHaveLength(1);
      expect(queue.size).toBe(1);
    });

    it('should handle boundary case: deadline equals now', () => {
      const now = Date.now();
      queue.enqueue(createRequest('boundary', 0, now, now));

      const expired = queue.removeExpired(now);
      expect(expired).toHaveLength(1);
    });

    it('should remove all expired items', () => {
      const now = Date.now();
      queue.enqueue(createRequest('exp1', 0, now, now - 1000));
      queue.enqueue(createRequest('exp2', 0, now, now - 500));
      queue.enqueue(createRequest('valid', 0, now, now + 1000));

      const expired = queue.removeExpired(now);
      expect(expired).toHaveLength(2);
      expect(queue.size).toBe(1);
    });
  });

  describe('removeCancelled', () => {
    it('should return empty array when no cancelled items', () => {
      queue.enqueue(createRequest('req1', 0));

      const cancelled = queue.removeCancelled();
      expect(cancelled).toHaveLength(0);
    });

    it('should remove and return cancelled items', () => {
      const controller = new AbortController();
      const request = createRequest('req1', 0);
      request.signal = controller.signal;

      queue.enqueue(request);
      controller.abort();

      const cancelled = queue.removeCancelled();
      expect(cancelled).toHaveLength(1);
      expect(cancelled[0].id).toBe('req1');
      expect(queue.isEmpty()).toBe(true);
    });

    it('should only remove cancelled items', () => {
      const controller = new AbortController();
      const cancelledReq = createRequest('cancelled', 0);
      cancelledReq.signal = controller.signal;

      queue.enqueue(cancelledReq);
      queue.enqueue(createRequest('active', 0));

      controller.abort();

      const cancelled = queue.removeCancelled();
      expect(cancelled).toHaveLength(1);
      expect(queue.size).toBe(1);
    });
  });

  describe('removeById', () => {
    it('should return undefined for non-existent ID', () => {
      queue.enqueue(createRequest('req1', 0));

      expect(queue.removeById('nonexistent')).toBeUndefined();
      expect(queue.size).toBe(1);
    });

    it('should remove and return item by ID', () => {
      queue.enqueue(createRequest('req1', 0));
      queue.enqueue(createRequest('req2', 0));
      queue.enqueue(createRequest('req3', 0));

      const removed = queue.removeById('req2');
      expect(removed?.id).toBe('req2');
      expect(queue.size).toBe(2);
    });

    it('should return undefined for empty queue', () => {
      expect(queue.removeById('any')).toBeUndefined();
    });
  });

  describe('clear', () => {
    it('should return empty array for empty queue', () => {
      expect(queue.clear()).toEqual([]);
    });

    it('should remove and return all items', () => {
      queue.enqueue(createRequest('req1', 0));
      queue.enqueue(createRequest('req2', 0));
      queue.enqueue(createRequest('req3', 0));

      const cleared = queue.clear();
      expect(cleared).toHaveLength(3);
      expect(queue.isEmpty()).toBe(true);
    });
  });

  describe('getAll', () => {
    it('should return empty array for empty queue', () => {
      expect(queue.getAll()).toEqual([]);
    });

    it('should return all items without modifying queue', () => {
      queue.enqueue(createRequest('req1', 2));
      queue.enqueue(createRequest('req2', 1));
      queue.enqueue(createRequest('req3', 3));

      const all = queue.getAll();
      expect(all).toHaveLength(3);
      expect(queue.size).toBe(3);
    });
  });

  describe('state transitions', () => {
    it('should handle rapid add/remove cycles', () => {
      for (let i = 0; i < 100; i++) {
        queue.enqueue(createRequest(`req${i}`, i % 10));
        if (i % 3 === 0) {
          queue.dequeue();
        }
      }

      expect(queue.size).toBe(100 - 34);
    });

    it('should maintain consistency after mixed operations', () => {
      const now = Date.now();

      queue.enqueue(createRequest('req1', 5, now, now + 10000));
      queue.enqueue(createRequest('req2', 3, now, now - 1000));
      queue.enqueue(createRequest('req3', 7, now));
      queue.removeById('req1');
      queue.removeExpired(now);

      expect(queue.size).toBe(1);
      expect(queue.peek()?.id).toBe('req3');
    });
  });

  describe('boundary value analysis', () => {
    it('should handle priority at Number.MAX_SAFE_INTEGER', () => {
      queue.enqueue(createRequest('max', Number.MAX_SAFE_INTEGER));
      queue.enqueue(createRequest('min', Number.MIN_SAFE_INTEGER));
      queue.enqueue(createRequest('zero', 0));

      expect(queue.dequeue()?.id).toBe('max');
      expect(queue.dequeue()?.id).toBe('zero');
      expect(queue.dequeue()?.id).toBe('min');
    });

    it('should handle enqueuedAt at edge timestamps', () => {
      queue.enqueue(createRequest('epoch', 0, 0));
      queue.enqueue(createRequest('future', 0, Number.MAX_SAFE_INTEGER));

      expect(queue.dequeue()?.id).toBe('epoch');
      expect(queue.dequeue()?.id).toBe('future');
    });
  });
});
