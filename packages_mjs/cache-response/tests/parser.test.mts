/**
 * Tests for Cache-Control parser and utilities
 */

import { jest } from '@jest/globals';
import {
  parseCacheControl,
  buildCacheControl,
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
  getHeaderValue,
  parseDateHeader,
} from '../src/parser.mjs';
import type { CacheEntryMetadata } from '../src/types.mjs';

describe('parseCacheControl', () => {
  it('should parse empty or null header', () => {
    expect(parseCacheControl(null)).toEqual({});
    expect(parseCacheControl(undefined)).toEqual({});
    expect(parseCacheControl('')).toEqual({});
  });

  it('should parse no-store directive', () => {
    expect(parseCacheControl('no-store')).toEqual({ noStore: true });
  });

  it('should parse no-cache directive', () => {
    expect(parseCacheControl('no-cache')).toEqual({ noCache: true });
  });

  it('should parse max-age directive', () => {
    expect(parseCacheControl('max-age=3600')).toEqual({ maxAge: 3600 });
  });

  it('should parse s-maxage directive', () => {
    expect(parseCacheControl('s-maxage=7200')).toEqual({ sMaxAge: 7200 });
  });

  it('should parse private directive', () => {
    expect(parseCacheControl('private')).toEqual({ private: true });
  });

  it('should parse public directive', () => {
    expect(parseCacheControl('public')).toEqual({ public: true });
  });

  it('should parse must-revalidate directive', () => {
    expect(parseCacheControl('must-revalidate')).toEqual({ mustRevalidate: true });
  });

  it('should parse stale-while-revalidate directive', () => {
    expect(parseCacheControl('stale-while-revalidate=60')).toEqual({
      staleWhileRevalidate: 60,
    });
  });

  it('should parse stale-if-error directive', () => {
    expect(parseCacheControl('stale-if-error=300')).toEqual({ staleIfError: 300 });
  });

  it('should parse immutable directive', () => {
    expect(parseCacheControl('immutable')).toEqual({ immutable: true });
  });

  it('should parse multiple directives', () => {
    expect(parseCacheControl('public, max-age=3600, must-revalidate')).toEqual({
      public: true,
      maxAge: 3600,
      mustRevalidate: true,
    });
  });

  it('should parse complex Cache-Control header', () => {
    const header = 'public, max-age=86400, s-maxage=3600, stale-while-revalidate=60, immutable';
    expect(parseCacheControl(header)).toEqual({
      public: true,
      maxAge: 86400,
      sMaxAge: 3600,
      staleWhileRevalidate: 60,
      immutable: true,
    });
  });

  it('should handle case insensitivity', () => {
    expect(parseCacheControl('Max-Age=100, No-Store')).toEqual({
      maxAge: 100,
      noStore: true,
    });
  });
});

describe('buildCacheControl', () => {
  it('should build empty header', () => {
    expect(buildCacheControl({})).toBe('');
  });

  it('should build single directive', () => {
    expect(buildCacheControl({ noStore: true })).toBe('no-store');
    expect(buildCacheControl({ maxAge: 3600 })).toBe('max-age=3600');
  });

  it('should build multiple directives', () => {
    const result = buildCacheControl({
      public: true,
      maxAge: 3600,
      mustRevalidate: true,
    });
    expect(result).toContain('public');
    expect(result).toContain('max-age=3600');
    expect(result).toContain('must-revalidate');
  });
});

describe('extractETag', () => {
  it('should extract ETag from headers', () => {
    expect(extractETag({ etag: '"abc123"' })).toBe('"abc123"');
    expect(extractETag({ ETag: '"def456"' })).toBe('"def456"');
  });

  it('should return undefined if no ETag', () => {
    expect(extractETag({})).toBeUndefined();
  });
});

describe('extractLastModified', () => {
  it('should extract Last-Modified from headers', () => {
    const date = 'Wed, 21 Oct 2015 07:28:00 GMT';
    expect(extractLastModified({ 'last-modified': date })).toBe(date);
    expect(extractLastModified({ 'Last-Modified': date })).toBe(date);
  });

  it('should return undefined if no Last-Modified', () => {
    expect(extractLastModified({})).toBeUndefined();
  });
});

describe('calculateExpiration', () => {
  const now = Date.now();

  beforeEach(() => {
    jest.spyOn(Date, 'now').mockReturnValue(now);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should return now for no-store', () => {
    const result = calculateExpiration({}, { noStore: true });
    expect(result).toBe(now);
  });

  it('should use s-maxage over max-age', () => {
    const result = calculateExpiration({}, { sMaxAge: 7200, maxAge: 3600 });
    expect(result).toBe(now + 7200 * 1000);
  });

  it('should use max-age', () => {
    const result = calculateExpiration({}, { maxAge: 3600 });
    expect(result).toBe(now + 3600 * 1000);
  });

  it('should use Expires header as fallback', () => {
    const expires = new Date(now + 1800 * 1000).toUTCString();
    const result = calculateExpiration({ expires }, {});
    // toUTCString() only has second precision, so we need to allow for up to 1000ms difference
    expect(Math.abs(result - (now + 1800 * 1000))).toBeLessThanOrEqual(1000);
  });

  it('should use default TTL as last resort', () => {
    const result = calculateExpiration({}, {}, 300000);
    expect(result).toBe(now + 300000);
  });

  it('should respect max TTL', () => {
    const result = calculateExpiration({}, { maxAge: 999999 }, 0, 3600000);
    expect(result).toBe(now + 3600000);
  });
});

describe('determineFreshness', () => {
  const now = Date.now();

  beforeEach(() => {
    jest.spyOn(Date, 'now').mockReturnValue(now);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should return fresh for unexpired response', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 1000,
      expiresAt: now + 1000,
    };
    expect(determineFreshness(metadata, now)).toBe('fresh');
  });

  it('should return stale within stale-while-revalidate window', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 10000,
      expiresAt: now - 1000,
      directives: { staleWhileRevalidate: 60 },
    };
    expect(determineFreshness(metadata, now)).toBe('stale');
  });

  it('should return expired when outside stale window', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 100000,
      expiresAt: now - 90000,
      directives: { staleWhileRevalidate: 60 },
    };
    expect(determineFreshness(metadata, now)).toBe('expired');
  });

  it('should return fresh for immutable responses within TTL', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 1000,
      expiresAt: now + 1000,
      directives: { immutable: true },
    };
    expect(determineFreshness(metadata, now)).toBe('fresh');
  });
});

describe('isCacheableStatus', () => {
  it('should return true for cacheable statuses', () => {
    expect(isCacheableStatus(200)).toBe(true);
    expect(isCacheableStatus(301)).toBe(true);
    expect(isCacheableStatus(404)).toBe(true);
  });

  it('should return false for non-cacheable statuses', () => {
    expect(isCacheableStatus(201)).toBe(false);
    expect(isCacheableStatus(500)).toBe(false);
    expect(isCacheableStatus(302)).toBe(false);
  });

  it('should respect custom cacheable statuses', () => {
    expect(isCacheableStatus(201, [200, 201])).toBe(true);
  });
});

describe('isCacheableMethod', () => {
  it('should return true for GET and HEAD', () => {
    expect(isCacheableMethod('GET')).toBe(true);
    expect(isCacheableMethod('HEAD')).toBe(true);
    expect(isCacheableMethod('get')).toBe(true);
  });

  it('should return false for other methods', () => {
    expect(isCacheableMethod('POST')).toBe(false);
    expect(isCacheableMethod('PUT')).toBe(false);
    expect(isCacheableMethod('DELETE')).toBe(false);
  });
});

describe('shouldCache', () => {
  it('should return false for no-store', () => {
    expect(shouldCache({ noStore: true })).toBe(false);
  });

  it('should return false for private', () => {
    expect(shouldCache({ private: true })).toBe(false);
  });

  it('should return true for public', () => {
    expect(shouldCache({ public: true })).toBe(true);
  });

  it('should return true for max-age without restrictions', () => {
    expect(shouldCache({ maxAge: 3600 })).toBe(true);
  });

  it('should respect config options', () => {
    expect(shouldCache({ noStore: true }, { respectNoStore: false })).toBe(true);
    expect(shouldCache({ private: true }, { respectPrivate: false })).toBe(true);
  });
});

describe('needsRevalidation', () => {
  it('should return true for no-cache directive', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: Date.now(),
      expiresAt: Date.now() + 10000,
      directives: { noCache: true },
    };
    expect(needsRevalidation(metadata)).toBe(true);
  });

  it('should return false when fresh and no-cache not set', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: Date.now(),
      expiresAt: Date.now() + 10000,
    };
    expect(needsRevalidation(metadata)).toBe(false);
  });
});

describe('parseVary', () => {
  it('should parse single header', () => {
    expect(parseVary('Accept')).toEqual(['accept']);
  });

  it('should parse multiple headers', () => {
    expect(parseVary('Accept, Accept-Encoding, Origin')).toEqual([
      'accept',
      'accept-encoding',
      'origin',
    ]);
  });

  it('should handle star', () => {
    expect(parseVary('*')).toEqual(['*']);
  });

  it('should return empty array for null/undefined', () => {
    expect(parseVary(null)).toEqual([]);
    expect(parseVary(undefined)).toEqual([]);
  });
});

describe('isVaryUncacheable', () => {
  it('should return true for star', () => {
    expect(isVaryUncacheable('*')).toBe(true);
  });

  it('should return false for specific headers', () => {
    expect(isVaryUncacheable('Accept')).toBe(false);
  });
});

describe('extractVaryHeaders', () => {
  it('should extract specified headers', () => {
    const headers = {
      Accept: 'application/json',
      'Accept-Encoding': 'gzip',
      'Content-Type': 'text/html',
    };
    expect(extractVaryHeaders(headers, ['accept', 'accept-encoding'])).toEqual({
      accept: 'application/json',
      'accept-encoding': 'gzip',
    });
  });
});

describe('matchVaryHeaders', () => {
  it('should return true for matching headers', () => {
    const request = { accept: 'application/json' };
    const cached = { accept: 'application/json' };
    expect(matchVaryHeaders(request, cached)).toBe(true);
  });

  it('should return false for non-matching headers', () => {
    const request = { accept: 'text/html' };
    const cached = { accept: 'application/json' };
    expect(matchVaryHeaders(request, cached)).toBe(false);
  });
});

describe('normalizeHeaders', () => {
  it('should lowercase all header keys', () => {
    const headers = {
      'Content-Type': 'application/json',
      Accept: 'text/html',
      'X-Custom-Header': 'value',
    };
    expect(normalizeHeaders(headers)).toEqual({
      'content-type': 'application/json',
      accept: 'text/html',
      'x-custom-header': 'value',
    });
  });

  it('should handle empty headers object', () => {
    expect(normalizeHeaders({})).toEqual({});
  });
});

/**
 * =============================================================================
 * LOGIC TESTING COVERAGE
 * =============================================================================
 * The following tests cover additional logic testing methodologies:
 * - Decision/Branch Coverage
 * - Boundary Value Analysis
 * - Path Coverage
 * - MC/DC (Modified Condition/Decision Coverage)
 * - State Transition Testing
 * =============================================================================
 */

describe('parseCacheControl - Decision/Branch Coverage', () => {
  it('should parse proxy-revalidate directive', () => {
    expect(parseCacheControl('proxy-revalidate')).toEqual({ proxyRevalidate: true });
  });

  it('should parse no-transform directive', () => {
    expect(parseCacheControl('no-transform')).toEqual({ noTransform: true });
  });

  it('should handle invalid max-age values', () => {
    const result = parseCacheControl('max-age=invalid');
    expect(result.maxAge).toBeNaN();
  });

  it('should handle whitespace in directives', () => {
    expect(parseCacheControl('  max-age=300  ,  no-cache  ')).toEqual({
      maxAge: 300,
      noCache: true,
    });
  });

  it('should handle unknown directives gracefully', () => {
    const result = parseCacheControl('max-age=300, unknown-directive=value');
    expect(result.maxAge).toBe(300);
  });

  it('should parse all directives in complex header', () => {
    const header = 'public, private, no-cache, no-store, max-age=100, s-maxage=200, ' +
      'must-revalidate, proxy-revalidate, no-transform, stale-while-revalidate=30, ' +
      'stale-if-error=60, immutable';
    const result = parseCacheControl(header);
    expect(result.public).toBe(true);
    expect(result.private).toBe(true);
    expect(result.noCache).toBe(true);
    expect(result.noStore).toBe(true);
    expect(result.maxAge).toBe(100);
    expect(result.sMaxAge).toBe(200);
    expect(result.mustRevalidate).toBe(true);
    expect(result.proxyRevalidate).toBe(true);
    expect(result.noTransform).toBe(true);
    expect(result.staleWhileRevalidate).toBe(30);
    expect(result.staleIfError).toBe(60);
    expect(result.immutable).toBe(true);
  });
});

describe('buildCacheControl - Path Coverage', () => {
  it('should build header with all possible directives', () => {
    const result = buildCacheControl({
      noStore: true,
      noCache: true,
      private: true,
      public: true,
      mustRevalidate: true,
      proxyRevalidate: true,
      noTransform: true,
      immutable: true,
      maxAge: 300,
      sMaxAge: 600,
      staleWhileRevalidate: 30,
      staleIfError: 60,
    });
    expect(result).toContain('no-store');
    expect(result).toContain('no-cache');
    expect(result).toContain('private');
    expect(result).toContain('public');
    expect(result).toContain('must-revalidate');
    expect(result).toContain('proxy-revalidate');
    expect(result).toContain('no-transform');
    expect(result).toContain('immutable');
    expect(result).toContain('max-age=300');
    expect(result).toContain('s-maxage=600');
    expect(result).toContain('stale-while-revalidate=30');
    expect(result).toContain('stale-if-error=60');
  });

  it('should handle zero values correctly', () => {
    const result = buildCacheControl({ maxAge: 0, staleWhileRevalidate: 0 });
    expect(result).toContain('max-age=0');
    expect(result).toContain('stale-while-revalidate=0');
  });
});

describe('calculateExpiration - Boundary Value Analysis', () => {
  const now = Date.now();

  beforeEach(() => {
    jest.spyOn(Date, 'now').mockReturnValue(now);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should handle zero max-age', () => {
    const result = calculateExpiration({}, { maxAge: 0 });
    expect(result).toBe(now);
  });

  it('should handle zero s-maxage', () => {
    const result = calculateExpiration({}, { sMaxAge: 0, maxAge: 100 });
    expect(result).toBe(now);
  });

  it('should handle max-age equal to maxTtl', () => {
    const result = calculateExpiration({}, { maxAge: 3600 }, 0, 3600000);
    expect(result).toBe(now + 3600000);
  });

  it('should handle max-age greater than maxTtl', () => {
    const result = calculateExpiration({}, { maxAge: 99999 }, 0, 3600000);
    expect(result).toBe(now + 3600000);
  });

  it('should handle default TTL equal to max TTL', () => {
    const result = calculateExpiration({}, {}, 3600, 3600);
    expect(result).toBe(now + 3600);
  });

  it('should handle expired Expires header', () => {
    const pastDate = new Date(now - 1000).toUTCString();
    const result = calculateExpiration({ expires: pastDate }, {});
    expect(result).toBe(now);
  });

  it('should handle invalid Expires header format', () => {
    const result = calculateExpiration({ Expires: 'invalid-date' }, {});
    expect(result).toBe(now);
  });

  it('should prioritize s-maxage over Expires header', () => {
    const futureDate = new Date(now + 10000).toUTCString();
    const result = calculateExpiration({ expires: futureDate }, { sMaxAge: 100 });
    expect(result).toBe(now + 100 * 1000);
  });
});

describe('determineFreshness - State Transition Testing', () => {
  const now = Date.now();

  it('should return fresh for immutable content before expiration', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 1000,
      expiresAt: now + 1000,
      directives: { immutable: true },
    };
    expect(determineFreshness(metadata, now)).toBe('fresh');
  });

  it('should return stale for immutable content after expiration with stale-while-revalidate', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 10000,
      expiresAt: now - 1000,
      directives: { immutable: true, staleWhileRevalidate: 60 },
    };
    expect(determineFreshness(metadata, now)).toBe('stale');
  });

  it('should return stale within stale-if-error window', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 10000,
      expiresAt: now - 1000,
      directives: { staleIfError: 60 },
    };
    expect(determineFreshness(metadata, now)).toBe('stale');
  });

  it('should return expired when outside both stale windows', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 200000,
      expiresAt: now - 100000,
      directives: { staleWhileRevalidate: 60, staleIfError: 30 },
    };
    expect(determineFreshness(metadata, now)).toBe('expired');
  });

  it('should return expired when no stale directives and past expiration', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 10000,
      expiresAt: now - 1000,
    };
    expect(determineFreshness(metadata, now)).toBe('expired');
  });

  it('should handle metadata without directives', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 10000,
      expiresAt: now + 10000,
    };
    expect(determineFreshness(metadata, now)).toBe('fresh');
  });

  it('should handle exactly at expiration boundary', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 10000,
      expiresAt: now,
    };
    // At exactly expiration time, should be expired (not fresh)
    expect(determineFreshness(metadata, now)).toBe('expired');
  });
});

describe('shouldCache - MC/DC Coverage', () => {
  it('should cache when all flags are true but directives are safe', () => {
    expect(shouldCache({ public: true, maxAge: 3600 }, {
      respectNoStore: true,
      respectNoCache: true,
      respectPrivate: true,
    })).toBe(true);
  });

  it('should not cache when no-store is set and respected', () => {
    expect(shouldCache({ noStore: true }, { respectNoStore: true })).toBe(false);
  });

  it('should cache when no-store is set but not respected', () => {
    expect(shouldCache({ noStore: true }, { respectNoStore: false })).toBe(true);
  });

  it('should not cache when private is set and respected', () => {
    expect(shouldCache({ private: true }, { respectPrivate: true })).toBe(false);
  });

  it('should cache when private is set but not respected', () => {
    expect(shouldCache({ private: true }, { respectPrivate: false })).toBe(true);
  });

  it('should cache when no-cache is set (still cacheable, just needs revalidation)', () => {
    expect(shouldCache({ noCache: true })).toBe(true);
  });

  it('should cache with empty directives', () => {
    expect(shouldCache({})).toBe(true);
  });

  it('should not cache with both no-store and private when both respected', () => {
    expect(shouldCache({ noStore: true, private: true }, {
      respectNoStore: true,
      respectPrivate: true,
    })).toBe(false);
  });
});

describe('needsRevalidation - Branch Coverage', () => {
  const now = Date.now();

  it('should return true for must-revalidate with stale content', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now - 10000,
      expiresAt: now - 1000,
      directives: { mustRevalidate: true },
    };
    expect(needsRevalidation(metadata)).toBe(true);
  });

  it('should return false for must-revalidate with fresh content', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now,
      expiresAt: now + 10000,
      directives: { mustRevalidate: true },
    };
    expect(needsRevalidation(metadata)).toBe(false);
  });

  it('should return false when no-cache is not respected', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now,
      expiresAt: now + 10000,
      directives: { noCache: true },
    };
    expect(needsRevalidation(metadata, false)).toBe(false);
  });

  it('should handle metadata with no directives', () => {
    const metadata: CacheEntryMetadata = {
      url: 'https://example.com',
      method: 'GET',
      statusCode: 200,
      headers: {},
      cachedAt: now,
      expiresAt: now + 10000,
    };
    expect(needsRevalidation(metadata)).toBe(false);
  });
});

describe('Vary handling - Path Coverage', () => {
  it('should handle multiple headers with different cases', () => {
    const headers = {
      'accept': 'application/json',
      'ACCEPT-ENCODING': 'gzip, deflate',
      'Accept-Language': 'en-US',
    };
    const result = extractVaryHeaders(headers, ['Accept', 'accept-encoding', 'ACCEPT-LANGUAGE']);
    expect(result).toEqual({
      'accept': 'application/json',
      'accept-encoding': 'gzip, deflate',
      'accept-language': 'en-US',
    });
  });

  it('should ignore star in extractVaryHeaders', () => {
    const headers = { accept: 'application/json' };
    const result = extractVaryHeaders(headers, ['*', 'accept']);
    expect(result).toEqual({ accept: 'application/json' });
  });

  it('should handle missing vary headers in request', () => {
    const headers = { 'content-type': 'text/html' };
    const result = extractVaryHeaders(headers, ['accept', 'accept-encoding']);
    expect(result).toEqual({});
  });

  it('should match when cached has subset of headers', () => {
    const request = { accept: 'application/json', 'accept-encoding': 'gzip' };
    const cached = { accept: 'application/json' };
    expect(matchVaryHeaders(request, cached)).toBe(true);
  });

  it('should not match when header is missing in request', () => {
    const request = {};
    const cached = { accept: 'application/json' };
    expect(matchVaryHeaders(request, cached)).toBe(false);
  });
});

describe('getHeaderValue - Edge Cases', () => {
  it('should return undefined for non-existent header', () => {
    expect(getHeaderValue({ 'content-type': 'text/html' }, 'accept')).toBeUndefined();
  });

  it('should find header with different case', () => {
    expect(getHeaderValue({ 'Content-Type': 'text/html' }, 'CONTENT-TYPE')).toBe('text/html');
  });

  it('should return first matching header', () => {
    const headers = { 'Accept': 'text/html' };
    expect(getHeaderValue(headers, 'accept')).toBe('text/html');
  });
});

describe('isCacheableStatus - Boundary Values', () => {
  it('should return true for all default cacheable statuses', () => {
    const defaultCacheable = [200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501];
    defaultCacheable.forEach(status => {
      expect(isCacheableStatus(status)).toBe(true);
    });
  });

  it('should return false for common non-cacheable statuses', () => {
    const nonCacheable = [201, 202, 302, 303, 304, 307, 308, 400, 401, 403, 500, 502, 503];
    nonCacheable.forEach(status => {
      expect(isCacheableStatus(status)).toBe(false);
    });
  });

  it('should work with empty custom statuses array', () => {
    expect(isCacheableStatus(200, [])).toBe(false);
  });

  it('should work with single status array', () => {
    expect(isCacheableStatus(200, [200])).toBe(true);
    expect(isCacheableStatus(201, [200])).toBe(false);
  });
});

describe('isCacheableMethod - Case Sensitivity', () => {
  it('should handle lowercase methods', () => {
    expect(isCacheableMethod('get')).toBe(true);
    expect(isCacheableMethod('head')).toBe(true);
    expect(isCacheableMethod('post')).toBe(false);
  });

  it('should handle mixed case methods', () => {
    expect(isCacheableMethod('Get')).toBe(true);
    expect(isCacheableMethod('HeAd')).toBe(true);
  });

  it('should work with custom methods array', () => {
    expect(isCacheableMethod('POST', ['GET', 'POST'])).toBe(true);
    expect(isCacheableMethod('PUT', ['GET', 'POST'])).toBe(false);
  });

  it('should work with empty custom methods array', () => {
    expect(isCacheableMethod('GET', [])).toBe(false);
  });
});

describe('parseDateHeader - Edge Cases', () => {
  it('should handle RFC 2822 date format', () => {
    const date = 'Wed, 21 Oct 2015 07:28:00 GMT';
    const result = parseDateHeader(date);
    expect(result).toBeDefined();
    expect(typeof result).toBe('number');
  });

  it('should handle ISO 8601 date format', () => {
    const date = '2015-10-21T07:28:00.000Z';
    const result = parseDateHeader(date);
    expect(result).toBeDefined();
  });

  it('should return undefined for malformed date', () => {
    expect(parseDateHeader('not a date')).toBeUndefined();
  });

  it('should return undefined for empty string', () => {
    expect(parseDateHeader('')).toBeUndefined();
  });
});
