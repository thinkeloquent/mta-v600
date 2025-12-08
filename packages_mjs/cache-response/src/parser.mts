/**
 * Cache-Control header parsing and utilities for RFC 7234 compliance
 */

import type { CacheControlDirectives, CacheEntryMetadata, CacheFreshness } from './types.mjs';

/**
 * Parse Cache-Control header into directives
 */
export function parseCacheControl(header: string | undefined | null): CacheControlDirectives {
  const directives: CacheControlDirectives = {};

  if (!header) {
    return directives;
  }

  const parts = header.toLowerCase().split(',').map((p) => p.trim());

  for (const part of parts) {
    const [key, value] = part.split('=').map((s) => s.trim());

    switch (key) {
      case 'no-store':
        directives.noStore = true;
        break;
      case 'no-cache':
        directives.noCache = true;
        break;
      case 'max-age':
        directives.maxAge = parseInt(value, 10);
        break;
      case 's-maxage':
        directives.sMaxAge = parseInt(value, 10);
        break;
      case 'private':
        directives.private = true;
        break;
      case 'public':
        directives.public = true;
        break;
      case 'must-revalidate':
        directives.mustRevalidate = true;
        break;
      case 'proxy-revalidate':
        directives.proxyRevalidate = true;
        break;
      case 'no-transform':
        directives.noTransform = true;
        break;
      case 'stale-while-revalidate':
        directives.staleWhileRevalidate = parseInt(value, 10);
        break;
      case 'stale-if-error':
        directives.staleIfError = parseInt(value, 10);
        break;
      case 'immutable':
        directives.immutable = true;
        break;
    }
  }

  return directives;
}

/**
 * Build Cache-Control header from directives
 */
export function buildCacheControl(directives: CacheControlDirectives): string {
  const parts: string[] = [];

  if (directives.noStore) parts.push('no-store');
  if (directives.noCache) parts.push('no-cache');
  if (directives.private) parts.push('private');
  if (directives.public) parts.push('public');
  if (directives.mustRevalidate) parts.push('must-revalidate');
  if (directives.proxyRevalidate) parts.push('proxy-revalidate');
  if (directives.noTransform) parts.push('no-transform');
  if (directives.immutable) parts.push('immutable');
  if (directives.maxAge !== undefined) parts.push(`max-age=${directives.maxAge}`);
  if (directives.sMaxAge !== undefined) parts.push(`s-maxage=${directives.sMaxAge}`);
  if (directives.staleWhileRevalidate !== undefined) {
    parts.push(`stale-while-revalidate=${directives.staleWhileRevalidate}`);
  }
  if (directives.staleIfError !== undefined) {
    parts.push(`stale-if-error=${directives.staleIfError}`);
  }

  return parts.join(', ');
}

/**
 * Extract ETag from response headers
 */
export function extractETag(headers: Record<string, string>): string | undefined {
  const etag = headers['etag'] || headers['ETag'];
  return etag?.trim();
}

/**
 * Extract Last-Modified from response headers
 */
export function extractLastModified(headers: Record<string, string>): string | undefined {
  const lastModified = headers['last-modified'] || headers['Last-Modified'];
  return lastModified?.trim();
}

/**
 * Parse Date header to timestamp
 */
export function parseDateHeader(header: string | undefined): number | undefined {
  if (!header) return undefined;
  const date = new Date(header);
  return isNaN(date.getTime()) ? undefined : date.getTime();
}

/**
 * Calculate expiration time based on Cache-Control and other headers
 */
export function calculateExpiration(
  headers: Record<string, string>,
  directives: CacheControlDirectives,
  defaultTtlMs: number = 0,
  maxTtlMs: number = 86400000
): number {
  const now = Date.now();

  // If no-store, don't cache
  if (directives.noStore) {
    return now;
  }

  // Use s-maxage for shared caches (higher priority than max-age)
  if (directives.sMaxAge !== undefined) {
    const ttl = Math.min(directives.sMaxAge * 1000, maxTtlMs);
    return now + ttl;
  }

  // Use max-age
  if (directives.maxAge !== undefined) {
    const ttl = Math.min(directives.maxAge * 1000, maxTtlMs);
    return now + ttl;
  }

  // Try Expires header
  const expires = headers['expires'] || headers['Expires'];
  if (expires) {
    const expiresDate = parseDateHeader(expires);
    if (expiresDate) {
      const ttl = Math.min(expiresDate - now, maxTtlMs);
      return now + Math.max(0, ttl);
    }
  }

  // Use default TTL
  if (defaultTtlMs > 0) {
    return now + Math.min(defaultTtlMs, maxTtlMs);
  }

  // No caching
  return now;
}

/**
 * Determine freshness status of a cached response
 */
export function determineFreshness(
  metadata: CacheEntryMetadata,
  now: number = Date.now()
): CacheFreshness {
  const { expiresAt, directives } = metadata;

  // If immutable and not expired, always fresh
  if (directives?.immutable && now < expiresAt) {
    return 'fresh';
  }

  // Check if within freshness lifetime
  if (now < expiresAt) {
    return 'fresh';
  }

  // Check stale-while-revalidate window
  if (directives?.staleWhileRevalidate) {
    const staleWindow = directives.staleWhileRevalidate * 1000;
    if (now < expiresAt + staleWindow) {
      return 'stale';
    }
  }

  // Check stale-if-error window
  if (directives?.staleIfError) {
    const staleWindow = directives.staleIfError * 1000;
    if (now < expiresAt + staleWindow) {
      return 'stale';
    }
  }

  return 'expired';
}

/**
 * Check if response is cacheable based on status code
 */
export function isCacheableStatus(
  statusCode: number,
  cacheableStatuses: number[] = [200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501]
): boolean {
  return cacheableStatuses.includes(statusCode);
}

/**
 * Check if request method is cacheable
 */
export function isCacheableMethod(
  method: string,
  cacheableMethods: string[] = ['GET', 'HEAD']
): boolean {
  return cacheableMethods.includes(method.toUpperCase());
}

/**
 * Check if response should be cached based on directives
 */
export function shouldCache(
  directives: CacheControlDirectives,
  config: {
    respectNoStore?: boolean;
    respectNoCache?: boolean;
    respectPrivate?: boolean;
  } = {}
): boolean {
  const { respectNoStore = true, respectNoCache = true, respectPrivate = true } = config;

  // no-store means never cache
  if (respectNoStore && directives.noStore) {
    return false;
  }

  // private means only store in private cache (browser)
  // For a shared cache (proxy/CDN), we should not cache
  if (respectPrivate && directives.private) {
    return false;
  }

  // no-cache means cache but revalidate
  // We still cache it, but it needs revalidation before use
  // This is handled at lookup time

  return true;
}

/**
 * Check if cached response needs revalidation
 */
export function needsRevalidation(
  metadata: CacheEntryMetadata,
  respectNoCache: boolean = true
): boolean {
  // If no-cache directive, always revalidate
  if (respectNoCache && metadata.directives?.noCache) {
    return true;
  }

  // If must-revalidate and stale
  if (metadata.directives?.mustRevalidate) {
    const freshness = determineFreshness(metadata);
    if (freshness !== 'fresh') {
      return true;
    }
  }

  return false;
}

/**
 * Parse Vary header into list of header names
 */
export function parseVary(header: string | undefined | null): string[] {
  if (!header) return [];
  if (header === '*') return ['*'];
  return header.split(',').map((h) => h.trim().toLowerCase());
}

/**
 * Check if Vary header indicates uncacheable
 */
export function isVaryUncacheable(vary: string | undefined | null): boolean {
  return vary === '*';
}

/**
 * Extract headers needed for Vary matching
 */
export function extractVaryHeaders(
  headers: Record<string, string>,
  vary: string[]
): Record<string, string> {
  const result: Record<string, string> = {};

  for (const key of vary) {
    if (key === '*') continue;
    const lowerKey = key.toLowerCase();
    for (const [k, v] of Object.entries(headers)) {
      if (k.toLowerCase() === lowerKey) {
        result[lowerKey] = v;
        break;
      }
    }
  }

  return result;
}

/**
 * Check if request headers match cached Vary headers
 */
export function matchVaryHeaders(
  requestHeaders: Record<string, string>,
  cachedVaryHeaders: Record<string, string>
): boolean {
  for (const [key, value] of Object.entries(cachedVaryHeaders)) {
    const requestValue = getHeaderValue(requestHeaders, key);
    if (requestValue !== value) {
      return false;
    }
  }
  return true;
}

/**
 * Get header value case-insensitively
 */
export function getHeaderValue(
  headers: Record<string, string>,
  key: string
): string | undefined {
  const lowerKey = key.toLowerCase();
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === lowerKey) {
      return v;
    }
  }
  return undefined;
}

/**
 * Normalize headers to lowercase keys
 */
export function normalizeHeaders(headers: Record<string, string>): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    result[key.toLowerCase()] = value;
  }
  return result;
}
