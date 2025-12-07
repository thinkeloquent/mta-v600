/**
 * DNS Cache Resolver - Main implementation
 */

import { promises as dns } from 'node:dns';
import type {
  CachedEntry,
  DnsCacheConfig,
  DnsCacheEvent,
  DnsCacheEventListener,
  DnsCacheStats,
  DnsCacheStore,
  ResolvedEndpoint,
  ResolverFunction,
  ResolutionResult,
} from './types.mjs';
import {
  mergeConfig,
  clampTtl,
  isExpired,
  isWithinGracePeriod,
  selectEndpoint,
  createLoadBalanceState,
  getEndpointKey,
  parseDsn,
  type LoadBalanceState,
} from './config.mjs';
import { MemoryStore } from './stores/memory.mjs';

/**
 * DNS Cache Resolver
 *
 * Provides cached DNS/service discovery resolution with:
 * - Configurable TTL with min/max bounds
 * - Stale-while-revalidate support
 * - Multiple load balancing strategies
 * - Health-aware endpoint selection
 * - Event emission for observability
 *
 * @example
 * const resolver = new DnsCacheResolver({
 *   id: 'api-resolver',
 *   defaultTtlMs: 60000,
 *   loadBalanceStrategy: 'power-of-two'
 * });
 *
 * const result = await resolver.resolve('api.example.com');
 * const endpoint = resolver.selectEndpoint('api.example.com');
 */
export class DnsCacheResolver {
  private readonly config: Required<DnsCacheConfig>;
  private readonly store: DnsCacheStore;
  private readonly listeners: Set<DnsCacheEventListener> = new Set();
  private readonly loadBalanceState: LoadBalanceState;
  private readonly customResolvers: Map<string, ResolverFunction> = new Map();
  private readonly revalidating: Set<string> = new Set();

  // Statistics
  private cacheHits = 0;
  private cacheMisses = 0;
  private staleHits = 0;
  private totalResolutionTimeMs = 0;
  private resolutionCount = 0;

  constructor(config: DnsCacheConfig, store?: DnsCacheStore) {
    this.config = mergeConfig(config);
    this.store = store ?? new MemoryStore(this.config.maxEntries);
    this.loadBalanceState = createLoadBalanceState();
  }

  /**
   * Resolve a DSN to endpoints, using cache when available
   *
   * @param dsn - The DSN/hostname to resolve
   * @param options - Resolution options
   * @returns Resolution result with endpoints
   */
  async resolve(
    dsn: string,
    options?: {
      /** Force a fresh resolution, bypassing cache */
      forceRefresh?: boolean;
      /** Custom TTL for this resolution (ms) */
      ttlMs?: number;
    }
  ): Promise<ResolutionResult> {
    const startTime = Date.now();

    // Check cache first (unless forcing refresh)
    if (!options?.forceRefresh) {
      const cached = await this.store.get(dsn);

      if (cached) {
        const now = Date.now();
        const expired = isExpired(cached.expiresAt, now);

        if (!expired) {
          // Cache hit - valid entry
          this.cacheHits++;
          cached.hitCount++;
          await this.store.set(dsn, cached);

          this.emit({
            type: 'cache:hit',
            dsn,
            ttlRemainingMs: cached.expiresAt - now,
          });

          return {
            endpoints: cached.endpoints,
            fromCache: true,
            ttlRemainingMs: cached.expiresAt - now,
            resolutionTimeMs: Date.now() - startTime,
          };
        }

        // Entry is expired, check if within grace period
        if (
          this.config.staleWhileRevalidate &&
          isWithinGracePeriod(cached.expiresAt, this.config.staleGracePeriodMs, now)
        ) {
          this.staleHits++;

          // Trigger background revalidation
          const isRevalidating = this.revalidating.has(dsn);
          if (!isRevalidating) {
            this.revalidateInBackground(dsn, options?.ttlMs);
          }

          this.emit({
            type: 'cache:stale',
            dsn,
            revalidating: !isRevalidating,
          });

          return {
            endpoints: cached.endpoints,
            fromCache: true,
            ttlRemainingMs: 0,
            resolutionTimeMs: Date.now() - startTime,
          };
        }

        // Entry is fully expired
        this.emit({ type: 'cache:expired', dsn });
      } else {
        this.emit({ type: 'cache:miss', dsn });
      }
    }

    // Cache miss - perform fresh resolution
    this.cacheMisses++;
    return this.freshResolve(dsn, options?.ttlMs);
  }

  /**
   * Perform a fresh DNS resolution
   */
  private async freshResolve(dsn: string, customTtlMs?: number): Promise<ResolutionResult> {
    const startTime = Date.now();

    this.emit({ type: 'resolve:start', dsn });

    try {
      // Use custom resolver if registered, otherwise use system DNS
      const resolver = this.customResolvers.get(dsn) ?? this.defaultResolver.bind(this);
      const endpoints = await resolver(dsn);

      const durationMs = Date.now() - startTime;
      this.totalResolutionTimeMs += durationMs;
      this.resolutionCount++;

      // Calculate TTL
      const ttlMs = clampTtl(
        customTtlMs ?? this.config.defaultTtlMs,
        this.config.minTtlMs,
        this.config.maxTtlMs
      );

      const now = Date.now();

      // Cache the result
      const entry: CachedEntry = {
        dsn,
        endpoints,
        resolvedAt: now,
        expiresAt: now + ttlMs,
        ttlMs,
        hitCount: 0,
      };

      await this.store.set(dsn, entry);

      this.emit({
        type: 'resolve:success',
        dsn,
        endpointCount: endpoints.length,
        durationMs,
      });

      return {
        endpoints,
        fromCache: false,
        ttlRemainingMs: ttlMs,
        resolutionTimeMs: durationMs,
      };
    } catch (error) {
      this.emit({
        type: 'resolve:error',
        dsn,
        error: error instanceof Error ? error : new Error(String(error)),
      });

      // Cache negative result if configured
      if (this.config.negativeTtlMs > 0) {
        const now = Date.now();
        const entry: CachedEntry = {
          dsn,
          endpoints: [],
          resolvedAt: now,
          expiresAt: now + this.config.negativeTtlMs,
          ttlMs: this.config.negativeTtlMs,
          hitCount: 0,
        };
        await this.store.set(dsn, entry);
      }

      throw error;
    }
  }

  /**
   * Default DNS resolver using Node.js dns module
   */
  private async defaultResolver(dsn: string): Promise<ResolvedEndpoint[]> {
    const parsed = parseDsn(dsn);
    const host = parsed.host;

    try {
      // Try to resolve as hostname
      const addresses = await dns.resolve4(host);

      return addresses.map((addr) => ({
        host: addr,
        port: parsed.port ?? 80,
        healthy: true,
        lastChecked: Date.now(),
      }));
    } catch {
      // If DNS resolution fails, treat as literal address
      return [
        {
          host,
          port: parsed.port ?? 80,
          healthy: true,
          lastChecked: Date.now(),
        },
      ];
    }
  }

  /**
   * Revalidate a cache entry in the background
   */
  private async revalidateInBackground(dsn: string, customTtlMs?: number): Promise<void> {
    if (this.revalidating.has(dsn)) return;

    this.revalidating.add(dsn);

    try {
      await this.freshResolve(dsn, customTtlMs);
    } catch {
      // Ignore errors in background revalidation
    } finally {
      this.revalidating.delete(dsn);
    }
  }

  /**
   * Select an endpoint for a DSN using the configured load balancing strategy
   *
   * @param dsn - The DSN to select an endpoint for
   * @returns The selected endpoint, or undefined if not cached
   */
  async selectEndpoint(dsn: string): Promise<ResolvedEndpoint | undefined> {
    const cached = await this.store.get(dsn);
    if (!cached || cached.endpoints.length === 0) {
      return undefined;
    }

    return selectEndpoint(cached.endpoints, this.config.loadBalanceStrategy, this.loadBalanceState);
  }

  /**
   * Resolve and select a single endpoint
   */
  async resolveOne(
    dsn: string,
    options?: { forceRefresh?: boolean; ttlMs?: number }
  ): Promise<ResolvedEndpoint | undefined> {
    const result = await this.resolve(dsn, options);
    if (result.endpoints.length === 0) {
      return undefined;
    }

    return selectEndpoint(result.endpoints, this.config.loadBalanceStrategy, this.loadBalanceState);
  }

  /**
   * Register a custom resolver for a specific DSN pattern
   */
  registerResolver(dsn: string, resolver: ResolverFunction): void {
    this.customResolvers.set(dsn, resolver);
  }

  /**
   * Unregister a custom resolver
   */
  unregisterResolver(dsn: string): boolean {
    return this.customResolvers.delete(dsn);
  }

  /**
   * Mark an endpoint as unhealthy
   */
  async markUnhealthy(dsn: string, endpoint: ResolvedEndpoint): Promise<void> {
    const cached = await this.store.get(dsn);
    if (!cached) return;

    const key = getEndpointKey(endpoint);
    const target = cached.endpoints.find((e) => getEndpointKey(e) === key);

    if (target && target.healthy) {
      target.healthy = false;
      target.lastChecked = Date.now();
      await this.store.set(dsn, cached);

      this.emit({
        type: 'health:changed',
        endpoint: target,
        previousHealthy: true,
      });
    }
  }

  /**
   * Mark an endpoint as healthy
   */
  async markHealthy(dsn: string, endpoint: ResolvedEndpoint): Promise<void> {
    const cached = await this.store.get(dsn);
    if (!cached) return;

    const key = getEndpointKey(endpoint);
    const target = cached.endpoints.find((e) => getEndpointKey(e) === key);

    if (target && !target.healthy) {
      target.healthy = true;
      target.lastChecked = Date.now();
      await this.store.set(dsn, cached);

      this.emit({
        type: 'health:changed',
        endpoint: target,
        previousHealthy: false,
      });
    }
  }

  /**
   * Increment active connections for an endpoint (for least-connections/P2C)
   */
  incrementConnections(endpoint: ResolvedEndpoint): void {
    const key = getEndpointKey(endpoint);
    const current = this.loadBalanceState.activeConnections.get(key) ?? 0;
    this.loadBalanceState.activeConnections.set(key, current + 1);
  }

  /**
   * Decrement active connections for an endpoint
   */
  decrementConnections(endpoint: ResolvedEndpoint): void {
    const key = getEndpointKey(endpoint);
    const current = this.loadBalanceState.activeConnections.get(key) ?? 0;
    this.loadBalanceState.activeConnections.set(key, Math.max(0, current - 1));
  }

  /**
   * Invalidate a cached entry
   */
  async invalidate(dsn: string): Promise<boolean> {
    const deleted = await this.store.delete(dsn);
    if (deleted) {
      this.emit({ type: 'cache:evicted', dsn, reason: 'manual' });
    }
    return deleted;
  }

  /**
   * Clear all cached entries
   */
  async clear(): Promise<void> {
    const keys = await this.store.keys();
    await this.store.clear();
    for (const dsn of keys) {
      this.emit({ type: 'cache:evicted', dsn, reason: 'manual' });
    }
  }

  /**
   * Get cache statistics
   */
  async getStats(): Promise<DnsCacheStats> {
    const entries = await this.store.size();
    const keys = await this.store.keys();

    let healthyEndpoints = 0;
    let unhealthyEndpoints = 0;

    for (const key of keys) {
      const entry = await this.store.get(key);
      if (entry) {
        for (const endpoint of entry.endpoints) {
          if (endpoint.healthy) {
            healthyEndpoints++;
          } else {
            unhealthyEndpoints++;
          }
        }
      }
    }

    const totalRequests = this.cacheHits + this.cacheMisses;

    return {
      totalEntries: entries,
      cacheHits: this.cacheHits,
      cacheMisses: this.cacheMisses,
      hitRatio: totalRequests > 0 ? this.cacheHits / totalRequests : 0,
      staleHits: this.staleHits,
      avgResolutionTimeMs:
        this.resolutionCount > 0 ? this.totalResolutionTimeMs / this.resolutionCount : 0,
      healthyEndpoints,
      unhealthyEndpoints,
    };
  }

  /**
   * Subscribe to events
   */
  on(listener: DnsCacheEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Unsubscribe from events
   */
  off(listener: DnsCacheEventListener): void {
    this.listeners.delete(listener);
  }

  /**
   * Emit an event
   */
  private emit(event: DnsCacheEvent): void {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch {
        // Ignore listener errors
      }
    }
  }

  /**
   * Destroy the resolver, releasing resources
   */
  async destroy(): Promise<void> {
    this.listeners.clear();
    this.customResolvers.clear();
    this.revalidating.clear();
    await this.store.close();
  }
}

/**
 * Factory function to create a DNS cache resolver
 */
export function createDnsCacheResolver(
  config: DnsCacheConfig,
  store?: DnsCacheStore
): DnsCacheResolver {
  return new DnsCacheResolver(config, store);
}

export default DnsCacheResolver;
