/**
 * Tests for Cache-Control parser and utilities
 */

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
    expect(result).toBeCloseTo(now + 1800 * 1000, -2);
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
});
