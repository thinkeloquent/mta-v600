/**
 * Main retry executor implementation
 */

import type {
  RetryConfig,
  RetryOptions,
  RetryResult,
  RetryEvent,
  RetryEventListener,
  RetryExecutorConfig,
} from './types.mjs';
import {
  mergeConfig,
  calculateBackoffDelay,
  isRetryableError,
  sleep,
} from './config.mjs';

/**
 * Retry Executor
 *
 * Provides retry logic with:
 * - Configurable max retries
 * - Exponential backoff with jitter
 * - Error filtering
 * - Abort signal support
 * - Event emission for observability
 */
export class RetryExecutor {
  private readonly config: Required<RetryConfig>;
  private readonly id: string;
  private readonly listeners: Set<RetryEventListener> = new Set();

  /**
   * Create a new RetryExecutor
   *
   * @param config - Retry executor configuration
   */
  constructor(config: RetryExecutorConfig = {}) {
    const { id, ...retryConfig } = config;
    this.config = mergeConfig(retryConfig);
    this.id = id ?? `retry-${Date.now()}`;
  }

  /**
   * Emit an event to all listeners
   */
  private emit(event: RetryEvent): void {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch {
        // Ignore listener errors
      }
    }
  }

  /**
   * Execute a function with retry logic
   *
   * @param fn - Async function to execute
   * @param options - Retry options for this execution
   * @returns Promise resolving to the result with retry metadata
   *
   * @example
   * const executor = new RetryExecutor({ maxRetries: 3 });
   * const result = await executor.execute(async () => {
   *   return fetch('https://api.example.com/data');
   * });
   */
  async execute<T>(
    fn: () => Promise<T>,
    options: RetryOptions = {}
  ): Promise<RetryResult<T>> {
    const { maxRetries = this.config.maxRetries, signal, metadata, shouldRetry } = options;
    const startTime = Date.now();
    let delayTime = 0;
    let attempt = 0;
    let lastError: Error | null = null;

    while (attempt <= maxRetries) {
      // Check for abort
      if (signal?.aborted) {
        this.emit({
          type: 'retry:abort',
          attempt,
          reason: 'Aborted by signal',
          metadata,
        });
        throw new Error('Retry aborted');
      }

      this.emit({
        type: 'attempt:start',
        attempt,
        metadata,
      });

      const attemptStart = Date.now();

      try {
        const result = await fn();
        const durationMs = Date.now() - attemptStart;

        this.emit({
          type: 'attempt:success',
          attempt,
          durationMs,
          metadata,
        });

        return {
          result,
          retries: attempt,
          totalTimeMs: Date.now() - startTime,
          delayTimeMs: delayTime,
        };
      } catch (error) {
        lastError = error as Error;
        const willRetry = this.shouldRetryAttempt(lastError, attempt, maxRetries, shouldRetry);

        this.emit({
          type: 'attempt:fail',
          attempt,
          error: lastError,
          willRetry,
          metadata,
        });

        if (!willRetry) {
          throw lastError;
        }

        // Calculate and apply backoff delay
        const delay = calculateBackoffDelay(attempt, this.config);
        delayTime += delay;

        this.emit({
          type: 'retry:wait',
          attempt,
          delayMs: delay,
          metadata,
        });

        await sleep(delay, signal);
        attempt++;
      }
    }

    // Should not reach here, but just in case
    throw lastError ?? new Error('Retry failed');
  }

  /**
   * Determine if we should retry after a failure
   */
  private shouldRetryAttempt(
    error: Error,
    attempt: number,
    maxRetries: number,
    customShouldRetry?: (error: Error, attempt: number) => boolean | Promise<boolean>
  ): boolean {
    // Check if we've exhausted retries
    if (attempt >= maxRetries) {
      return false;
    }

    // Check custom predicate first
    if (customShouldRetry) {
      const result = customShouldRetry(error, attempt);
      if (typeof result === 'boolean') {
        return result;
      }
      // If it returns a promise, we can't await here - fall through to default
    }

    // Check if error is retryable
    return isRetryableError(error, this.config);
  }

  /**
   * Add an event listener
   *
   * @param listener - Event listener function
   * @returns Function to remove the listener
   */
  on(listener: RetryEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Remove an event listener
   */
  off(listener: RetryEventListener): void {
    this.listeners.delete(listener);
  }

  /**
   * Get the executor ID
   */
  getId(): string {
    return this.id;
  }

  /**
   * Get the current configuration
   */
  getConfig(): Required<RetryConfig> {
    return { ...this.config };
  }
}

/**
 * Create a new retry executor
 */
export function createRetryExecutor(config?: RetryExecutorConfig): RetryExecutor {
  return new RetryExecutor(config);
}

/**
 * Execute a function with retry logic (convenience function)
 *
 * @param fn - Async function to execute
 * @param config - Retry configuration
 * @returns Promise resolving to the result with retry metadata
 *
 * @example
 * const result = await retry(
 *   async () => fetch('https://api.example.com/data'),
 *   { maxRetries: 3 }
 * );
 */
export async function retry<T>(
  fn: () => Promise<T>,
  config?: RetryConfig & RetryOptions
): Promise<RetryResult<T>> {
  const executor = new RetryExecutor(config);
  return executor.execute(fn, config);
}

/**
 * Create a retry wrapper function
 *
 * @param config - Retry configuration
 * @returns Function that wraps operations with retry logic
 *
 * @example
 * const withRetry = createRetryWrapper({ maxRetries: 3 });
 * const result = await withRetry(() => fetch('https://api.example.com/data'));
 */
export function createRetryWrapper(
  config?: RetryConfig
): <T>(fn: () => Promise<T>, options?: RetryOptions) => Promise<RetryResult<T>> {
  const executor = new RetryExecutor(config);
  return (fn, options) => executor.execute(fn, options);
}

export default {
  RetryExecutor,
  createRetryExecutor,
  retry,
  createRetryWrapper,
};
