/**
 * RFC 7234 HTTP Response Cache Manager
 */

import type {
  CacheResponseConfig,
  CacheResponseStore,
  CachedResponse,
  CacheEntryMetadata,
  CacheLookupResult,
  CacheResponseEvent,
  CacheResponseEventType,
  CacheResponseEventListener,
  BackgroundRevalidator,
  CacheFreshness,
} from './types.mjs';
import {
  parseCacheControl,
  extractETag,
  extractLastModified,
  calculateExpiration,
  determineFreshness,
  isCacheableStatus,
  isCacheableMethod,
  shouldCache,
  needsRevalidation,
  parseVary,
  isVaryUncacheable,
  extractVaryHeaders,
  matchVaryHeaders,
  normalizeHeaders,
} from './parser.mjs';
import { MemoryCacheStore } from './stores/memory.mjs';

/**
 * Default cache response configuration
 */
export const DEFAULT_CACHE_RESPONSE_CONFIG: Required<CacheResponseConfig> = {
  methods: ['GET', 'HEAD'],
  cacheableStatuses: [200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501],
  defaultTtlMs: 0,
  maxTtlMs: 86400000, // 24 hours
  respectNoCache: true,
  respectNoStore: true,
  respectPrivate: true,
  staleWhileRevalidate: true,
  staleIfError: true,
  includeQueryInKey: true,
  keyGenerator: defaultKeyGenerator,
  varyHeaders: [],
};

/**
 * Default cache key generator
 */
function defaultKeyGenerator(
  method: string,
  url: string,
  headers?: Record<string, string>
): string {
  let key = `${method.toUpperCase()}:${url}`;
  if (headers && Object.keys(headers).length > 0) {
    const sortedHeaders = Object.entries(headers)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`)
      .join('&');
    key += `|${sortedHeaders}`;
  }
  return key;
}

/**
 * Merge user config with defaults
 */
export function mergeCacheResponseConfig(
  config?: CacheResponseConfig
): Required<CacheResponseConfig> {
  if (!config) {
    return { ...DEFAULT_CACHE_RESPONSE_CONFIG };
  }

  return {
    methods: config.methods ?? DEFAULT_CACHE_RESPONSE_CONFIG.methods,
    cacheableStatuses: config.cacheableStatuses ?? DEFAULT_CACHE_RESPONSE_CONFIG.cacheableStatuses,
    defaultTtlMs: config.defaultTtlMs ?? DEFAULT_CACHE_RESPONSE_CONFIG.defaultTtlMs,
    maxTtlMs: config.maxTtlMs ?? DEFAULT_CACHE_RESPONSE_CONFIG.maxTtlMs,
    respectNoCache: config.respectNoCache ?? DEFAULT_CACHE_RESPONSE_CONFIG.respectNoCache,
    respectNoStore: config.respectNoStore ?? DEFAULT_CACHE_RESPONSE_CONFIG.respectNoStore,
    respectPrivate: config.respectPrivate ?? DEFAULT_CACHE_RESPONSE_CONFIG.respectPrivate,
    staleWhileRevalidate: config.staleWhileRevalidate ?? DEFAULT_CACHE_RESPONSE_CONFIG.staleWhileRevalidate,
    staleIfError: config.staleIfError ?? DEFAULT_CACHE_RESPONSE_CONFIG.staleIfError,
    includeQueryInKey: config.includeQueryInKey ?? DEFAULT_CACHE_RESPONSE_CONFIG.includeQueryInKey,
    keyGenerator: config.keyGenerator ?? DEFAULT_CACHE_RESPONSE_CONFIG.keyGenerator,
    varyHeaders: config.varyHeaders ?? DEFAULT_CACHE_RESPONSE_CONFIG.varyHeaders,
  };
}

/**
 * ResponseCache - RFC 7234 compliant HTTP response cache
 *
 * Implements:
 * - Cache-Control directive parsing and compliance
 * - ETag and Last-Modified conditional request support
 * - Vary header handling
 * - Stale-while-revalidate pattern
 * - Stale-if-error pattern
 * - LRU eviction (via store)
 *
 * @example
 * const cache = new ResponseCache();
 *
 * // Check cache before making request
 * const lookup = await cache.lookup('GET', 'https://api.example.com/data');
 * if (lookup.found && lookup.freshness === 'fresh') {
 *   return lookup.response;
 * }
 *
 * // Make request (with conditional headers if available)
 * const headers = {};
 * if (lookup.etag) headers['If-None-Match'] = lookup.etag;
 * if (lookup.lastModified) headers['If-Modified-Since'] = lookup.lastModified;
 *
 * const response = await fetch(url, { headers });
 *
 * // Handle 304 Not Modified
 * if (response.status === 304 && lookup.response) {
 *   await cache.revalidate(key, lookup.response.metadata);
 *   return lookup.response;
 * }
 *
 * // Store new response
 * await cache.store('GET', url, responseHeaders, body);
 */
export class ResponseCache {
  private readonly config: Required<CacheResponseConfig>;
  private readonly store: CacheResponseStore;
  private readonly listeners: Set<CacheResponseEventListener> = new Set();
  private backgroundRevalidator?: BackgroundRevalidator;
  private revalidatingKeys: Set<string> = new Set();

  constructor(config?: CacheResponseConfig, store?: CacheResponseStore) {
    this.config = mergeCacheResponseConfig(config);
    this.store = store ?? new MemoryCacheStore();
  }

  /**
   * Generate cache key for a request
   */
  generateKey(
    method: string,
    url: string,
    requestHeaders?: Record<string, string>,
    varyHeaders?: string[]
  ): string {
    // Strip query string if configured
    let cacheUrl = url;
    if (!this.config.includeQueryInKey) {
      const queryIndex = url.indexOf('?');
      if (queryIndex !== -1) {
        cacheUrl = url.substring(0, queryIndex);
      }
    }

    // Extract headers for Vary-based key
    let varyHeaderValues: Record<string, string> | undefined;
    if (requestHeaders && varyHeaders && varyHeaders.length > 0) {
      varyHeaderValues = extractVaryHeaders(requestHeaders, varyHeaders);
    }

    return this.config.keyGenerator(method, cacheUrl, varyHeaderValues);
  }

  /**
   * Check if a request method is cacheable
   */
  isCacheable(method: string): boolean {
    return isCacheableMethod(method, this.config.methods);
  }

  /**
   * Look up a cached response
   */
  async lookup(
    method: string,
    url: string,
    requestHeaders?: Record<string, string>
  ): Promise<CacheLookupResult> {
    // Check if method is cacheable
    if (!this.isCacheable(method)) {
      return { found: false };
    }

    const key = this.generateKey(method, url, requestHeaders);
    const cached = await this.store.get(key);

    if (!cached) {
      this.emit({
        type: 'cache:miss',
        key,
        url,
        timestamp: Date.now(),
      });
      return { found: false };
    }

    // Check Vary header matching
    if (cached.metadata.vary && requestHeaders) {
      const varyList = parseVary(cached.metadata.vary);
      if (isVaryUncacheable(cached.metadata.vary)) {
        return { found: false };
      }
      if (cached.metadata.varyHeaders) {
        const requestVaryHeaders = extractVaryHeaders(requestHeaders, varyList);
        if (!matchVaryHeaders(requestVaryHeaders, cached.metadata.varyHeaders)) {
          return { found: false };
        }
      }
    }

    const freshness = determineFreshness(cached.metadata);
    const shouldRevalidate =
      freshness !== 'fresh' ||
      needsRevalidation(cached.metadata, this.config.respectNoCache);

    // Emit appropriate event
    if (freshness === 'fresh' && !shouldRevalidate) {
      this.emit({
        type: 'cache:hit',
        key,
        url,
        timestamp: Date.now(),
        metadata: { freshness },
      });
    } else if (freshness === 'stale') {
      this.emit({
        type: 'cache:stale-serve',
        key,
        url,
        timestamp: Date.now(),
        metadata: { freshness },
      });
    }

    // Trigger background revalidation for stale-while-revalidate
    if (
      this.config.staleWhileRevalidate &&
      freshness === 'stale' &&
      this.backgroundRevalidator &&
      !this.revalidatingKeys.has(key)
    ) {
      this.triggerBackgroundRevalidation(key, url, requestHeaders);
    }

    return {
      found: true,
      response: cached,
      freshness,
      shouldRevalidate,
      etag: cached.metadata.etag,
      lastModified: cached.metadata.lastModified,
    };
  }

  /**
   * Store a response in the cache
   */
  async store(
    method: string,
    url: string,
    statusCode: number,
    responseHeaders: Record<string, string>,
    body: Buffer | string | null,
    requestHeaders?: Record<string, string>
  ): Promise<boolean> {
    // Check if method is cacheable
    if (!this.isCacheable(method)) {
      this.emit({
        type: 'cache:bypass',
        key: this.generateKey(method, url, requestHeaders),
        url,
        timestamp: Date.now(),
        metadata: { reason: 'method-not-cacheable' },
      });
      return false;
    }

    // Check if status is cacheable
    if (!isCacheableStatus(statusCode, this.config.cacheableStatuses)) {
      this.emit({
        type: 'cache:bypass',
        key: this.generateKey(method, url, requestHeaders),
        url,
        timestamp: Date.now(),
        metadata: { reason: 'status-not-cacheable', statusCode },
      });
      return false;
    }

    const normalizedHeaders = normalizeHeaders(responseHeaders);
    const cacheControl = normalizedHeaders['cache-control'];
    const directives = parseCacheControl(cacheControl);

    // Check if response should be cached based on directives
    if (!shouldCache(directives, {
      respectNoStore: this.config.respectNoStore,
      respectNoCache: this.config.respectNoCache,
      respectPrivate: this.config.respectPrivate,
    })) {
      this.emit({
        type: 'cache:bypass',
        key: this.generateKey(method, url, requestHeaders),
        url,
        timestamp: Date.now(),
        metadata: { reason: 'cache-control', cacheControl },
      });
      return false;
    }

    // Check Vary header
    const vary = normalizedHeaders['vary'];
    if (isVaryUncacheable(vary)) {
      this.emit({
        type: 'cache:bypass',
        key: this.generateKey(method, url, requestHeaders),
        url,
        timestamp: Date.now(),
        metadata: { reason: 'vary-star' },
      });
      return false;
    }

    // Extract vary headers from request for key generation
    const varyList = parseVary(vary);
    const varyHeaders = requestHeaders ? extractVaryHeaders(requestHeaders, varyList) : undefined;

    // Calculate expiration
    const now = Date.now();
    const expiresAt = calculateExpiration(
      normalizedHeaders,
      directives,
      this.config.defaultTtlMs,
      this.config.maxTtlMs
    );

    // Don't cache if already expired
    if (expiresAt <= now) {
      this.emit({
        type: 'cache:bypass',
        key: this.generateKey(method, url, requestHeaders, varyList),
        url,
        timestamp: now,
        metadata: { reason: 'already-expired' },
      });
      return false;
    }

    // Build cache entry
    const metadata: CacheEntryMetadata = {
      url,
      method: method.toUpperCase(),
      statusCode,
      headers: normalizedHeaders,
      cachedAt: now,
      expiresAt,
      etag: extractETag(normalizedHeaders),
      lastModified: extractLastModified(normalizedHeaders),
      cacheControl,
      directives,
      vary,
      varyHeaders,
    };

    const cachedResponse: CachedResponse = {
      metadata,
      body,
    };

    const key = this.generateKey(method, url, requestHeaders, varyList);
    await this.store.set(key, cachedResponse);

    this.emit({
      type: 'cache:store',
      key,
      url,
      timestamp: now,
      metadata: { expiresAt, statusCode },
    });

    return true;
  }

  /**
   * Revalidate a cached response (update expiration after 304 Not Modified)
   */
  async revalidate(
    method: string,
    url: string,
    responseHeaders?: Record<string, string>,
    requestHeaders?: Record<string, string>
  ): Promise<boolean> {
    const key = this.generateKey(method, url, requestHeaders);
    const cached = await this.store.get(key);

    if (!cached) {
      return false;
    }

    const now = Date.now();
    const normalizedHeaders = responseHeaders ? normalizeHeaders(responseHeaders) : cached.metadata.headers;
    const cacheControl = normalizedHeaders['cache-control'] || cached.metadata.cacheControl;
    const directives = parseCacheControl(cacheControl);

    // Update expiration
    const expiresAt = calculateExpiration(
      normalizedHeaders,
      directives,
      this.config.defaultTtlMs,
      this.config.maxTtlMs
    );

    // Update metadata
    const updatedMetadata: CacheEntryMetadata = {
      ...cached.metadata,
      cachedAt: now,
      expiresAt,
      etag: extractETag(normalizedHeaders) ?? cached.metadata.etag,
      lastModified: extractLastModified(normalizedHeaders) ?? cached.metadata.lastModified,
      cacheControl,
      directives,
    };

    const updatedResponse: CachedResponse = {
      metadata: updatedMetadata,
      body: cached.body,
    };

    await this.store.set(key, updatedResponse);
    this.revalidatingKeys.delete(key);

    this.emit({
      type: 'cache:revalidate',
      key,
      url,
      timestamp: now,
      metadata: { expiresAt },
    });

    return true;
  }

  /**
   * Invalidate a cached response
   */
  async invalidate(method: string, url: string, requestHeaders?: Record<string, string>): Promise<boolean> {
    const key = this.generateKey(method, url, requestHeaders);
    const deleted = await this.store.delete(key);

    if (deleted) {
      this.emit({
        type: 'cache:expire',
        key,
        url,
        timestamp: Date.now(),
      });
    }

    return deleted;
  }

  /**
   * Set background revalidator for stale-while-revalidate
   */
  setBackgroundRevalidator(revalidator: BackgroundRevalidator): void {
    this.backgroundRevalidator = revalidator;
  }

  /**
   * Trigger background revalidation
   */
  private triggerBackgroundRevalidation(
    key: string,
    url: string,
    requestHeaders?: Record<string, string>
  ): void {
    if (!this.backgroundRevalidator) return;

    this.revalidatingKeys.add(key);

    this.backgroundRevalidator(url, requestHeaders)
      .catch(() => {
        // Ignore errors in background revalidation
      })
      .finally(() => {
        this.revalidatingKeys.delete(key);
      });
  }

  /**
   * Get configuration
   */
  getConfig(): Required<CacheResponseConfig> {
    return this.config;
  }

  /**
   * Get store statistics
   */
  async getStats(): Promise<{ size: number }> {
    return { size: await this.store.size() };
  }

  /**
   * Add event listener
   */
  on(listener: CacheResponseEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Remove event listener
   */
  off(listener: CacheResponseEventListener): void {
    this.listeners.delete(listener);
  }

  private emit(event: CacheResponseEvent): void {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch {
        // Ignore listener errors
      }
    }
  }

  /**
   * Clear all cached responses
   */
  async clear(): Promise<void> {
    await this.store.clear();
  }

  /**
   * Close the cache and release resources
   */
  async close(): Promise<void> {
    await this.store.close();
    this.listeners.clear();
    this.revalidatingKeys.clear();
  }
}

/**
 * Create a response cache instance
 */
export function createResponseCache(
  config?: CacheResponseConfig,
  store?: CacheResponseStore
): ResponseCache {
  return new ResponseCache(config, store);
}
