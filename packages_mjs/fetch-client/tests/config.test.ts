/**
 * Tests for config.mts
 * Logic testing: Decision/Branch, Boundary Value, Error Path coverage
 */
import {
  normalizeTimeout,
  validateConfig,
  validateAuthConfig,
  getAuthHeaderName,
  formatAuthHeaderValue,
  resolveConfig,
  DEFAULT_TIMEOUTS,
  DEFAULT_CONTENT_TYPE,
  defaultSerializer,
} from '../src/config.mjs';
import type { ClientConfig, AuthConfig, TimeoutConfig } from '../src/types.mjs';

describe('config', () => {
  describe('normalizeTimeout', () => {
    // Decision: typeof timeout === 'number'
    it('should convert number to TimeoutConfig with uniform values', () => {
      const result = normalizeTimeout(5000);
      expect(result).toEqual({
        connect: 5000,
        read: 5000,
        write: 5000,
      });
    });

    // Decision: timeout is object
    it('should merge partial config with defaults', () => {
      const result = normalizeTimeout({ connect: 1000 });
      expect(result).toEqual({
        connect: 1000,
        read: DEFAULT_TIMEOUTS.read,
        write: DEFAULT_TIMEOUTS.write,
      });
    });

    // Boundary: null/undefined input
    it('should return DEFAULT_TIMEOUTS when timeout is undefined', () => {
      const result = normalizeTimeout(undefined);
      expect(result).toEqual(DEFAULT_TIMEOUTS);
    });

    // Boundary: zero value is valid
    it('should accept zero as valid timeout', () => {
      const result = normalizeTimeout(0);
      expect(result).toEqual({
        connect: 0,
        read: 0,
        write: 0,
      });
    });

    // Boundary: partial object with all fields
    it('should return exact values when all fields provided', () => {
      const config: TimeoutConfig = {
        connect: 1000,
        read: 2000,
        write: 3000,
      };
      const result = normalizeTimeout(config);
      expect(result).toEqual(config);
    });

    // Boundary: empty object uses all defaults
    it('should use all defaults for empty object', () => {
      const result = normalizeTimeout({});
      expect(result).toEqual(DEFAULT_TIMEOUTS);
    });
  });

  describe('validateConfig', () => {
    // Error Path: missing baseUrl
    it('should throw when baseUrl is missing', () => {
      expect(() => validateConfig({} as ClientConfig)).toThrow('baseUrl is required');
    });

    // Error Path: empty baseUrl
    it('should throw when baseUrl is empty string', () => {
      expect(() => validateConfig({ baseUrl: '' })).toThrow('baseUrl is required');
    });

    // Error Path: invalid URL
    it('should throw for invalid URL format', () => {
      expect(() => validateConfig({ baseUrl: 'not-a-url' })).toThrow('Invalid baseUrl: not-a-url');
    });

    // Error Path: URL without protocol
    it('should throw for URL without protocol', () => {
      expect(() => validateConfig({ baseUrl: 'api.example.com' })).toThrow('Invalid baseUrl');
    });

    // Happy Path: valid URL
    it('should pass for valid http URL', () => {
      expect(() => validateConfig({ baseUrl: 'http://api.example.com' })).not.toThrow();
    });

    it('should pass for valid https URL', () => {
      expect(() => validateConfig({ baseUrl: 'https://api.example.com' })).not.toThrow();
    });

    // Path: with auth, delegates to validateAuthConfig
    it('should validate auth config when provided', () => {
      const config: ClientConfig = {
        baseUrl: 'https://api.example.com',
        auth: { type: 'invalid' as any },
      };
      expect(() => validateConfig(config)).toThrow('Invalid auth type');
    });

    // Path: without auth, skips auth validation
    it('should pass without auth config', () => {
      expect(() => validateConfig({ baseUrl: 'https://api.example.com' })).not.toThrow();
    });
  });

  describe('validateAuthConfig', () => {
    // Decision: type = 'bearer'
    it('should pass for bearer auth type', () => {
      expect(() => validateAuthConfig({ type: 'bearer' })).not.toThrow();
    });

    // Decision: type = 'x-api-key'
    it('should pass for x-api-key auth type', () => {
      expect(() => validateAuthConfig({ type: 'x-api-key' })).not.toThrow();
    });

    // Decision: type = 'custom' with headerName
    it('should pass for custom auth type with headerName', () => {
      expect(() =>
        validateAuthConfig({ type: 'custom', headerName: 'X-Custom-Auth' })
      ).not.toThrow();
    });

    // Error Path: type = 'custom' without headerName
    it('should throw for custom auth type without headerName', () => {
      expect(() => validateAuthConfig({ type: 'custom' })).toThrow(
        'headerName is required for custom auth type'
      );
    });

    // Error Path: invalid type
    it('should throw for invalid auth type', () => {
      expect(() => validateAuthConfig({ type: 'invalid' as any })).toThrow(
        'Invalid auth type: invalid'
      );
    });

    // Boundary: empty string type
    it('should throw for empty string auth type', () => {
      expect(() => validateAuthConfig({ type: '' as any })).toThrow('Invalid auth type');
    });
  });

  describe('getAuthHeaderName', () => {
    // Decision: bearer -> Authorization
    it('should return Authorization for bearer type', () => {
      expect(getAuthHeaderName({ type: 'bearer' })).toBe('Authorization');
    });

    // Decision: x-api-key -> x-api-key
    it('should return x-api-key for x-api-key type', () => {
      expect(getAuthHeaderName({ type: 'x-api-key' })).toBe('x-api-key');
    });

    // Decision: custom -> custom headerName
    it('should return custom headerName for custom type', () => {
      expect(getAuthHeaderName({ type: 'custom', headerName: 'X-My-Header' })).toBe('X-My-Header');
    });

    // Decision: custom without headerName -> fallback Authorization
    it('should return Authorization as fallback for custom without headerName', () => {
      expect(getAuthHeaderName({ type: 'custom' })).toBe('Authorization');
    });

    // Decision: default case
    it('should return Authorization for unknown type (default case)', () => {
      expect(getAuthHeaderName({ type: 'unknown' as any })).toBe('Authorization');
    });
  });

  describe('formatAuthHeaderValue', () => {
    const apiKey = 'test-api-key-123';

    // Decision: bearer -> Bearer prefix
    it('should format bearer with Bearer prefix', () => {
      expect(formatAuthHeaderValue({ type: 'bearer' }, apiKey)).toBe(`Bearer ${apiKey}`);
    });

    // Decision: x-api-key -> raw key
    it('should return raw key for x-api-key type', () => {
      expect(formatAuthHeaderValue({ type: 'x-api-key' }, apiKey)).toBe(apiKey);
    });

    // Decision: custom -> raw key
    it('should return raw key for custom type', () => {
      expect(formatAuthHeaderValue({ type: 'custom', headerName: 'X-Auth' }, apiKey)).toBe(apiKey);
    });

    // Decision: default case
    it('should return raw key for unknown type (default case)', () => {
      expect(formatAuthHeaderValue({ type: 'unknown' as any }, apiKey)).toBe(apiKey);
    });

    // Boundary: empty apiKey
    it('should handle empty apiKey for bearer', () => {
      expect(formatAuthHeaderValue({ type: 'bearer' }, '')).toBe('Bearer ');
    });
  });

  describe('resolveConfig', () => {
    const validBaseUrl = 'https://api.example.com';

    // Path: full config resolution
    it('should resolve config with all defaults', () => {
      const result = resolveConfig({ baseUrl: validBaseUrl });

      expect(result.baseUrl).toBeInstanceOf(URL);
      expect(result.baseUrl.toString()).toBe(`${validBaseUrl}/`);
      expect(result.timeout).toEqual(DEFAULT_TIMEOUTS);
      expect(result.headers).toEqual({});
      expect(result.contentType).toBe(DEFAULT_CONTENT_TYPE);
      expect(result.auth).toBeUndefined();
      expect(result.serializer).toBe(defaultSerializer);
    });

    // Path: with custom timeout
    it('should resolve config with custom timeout', () => {
      const result = resolveConfig({
        baseUrl: validBaseUrl,
        timeout: 10000,
      });
      expect(result.timeout).toEqual({
        connect: 10000,
        read: 10000,
        write: 10000,
      });
    });

    // Path: with custom headers
    it('should copy custom headers', () => {
      const headers = { 'User-Agent': 'TestClient/1.0' };
      const result = resolveConfig({
        baseUrl: validBaseUrl,
        headers,
      });
      expect(result.headers).toEqual(headers);
      // Should be a copy, not same reference
      expect(result.headers).not.toBe(headers);
    });

    // Path: with custom content type
    it('should use custom content type', () => {
      const result = resolveConfig({
        baseUrl: validBaseUrl,
        contentType: 'application/xml',
      });
      expect(result.contentType).toBe('application/xml');
    });

    // Path: with auth config
    it('should include auth config when provided', () => {
      const auth: AuthConfig = { type: 'bearer', apiKey: 'secret' };
      const result = resolveConfig({
        baseUrl: validBaseUrl,
        auth,
      });
      expect(result.auth).toEqual(auth);
    });

    // Error Path: propagates validation errors
    it('should throw for invalid config', () => {
      expect(() => resolveConfig({ baseUrl: '' })).toThrow('baseUrl is required');
    });
  });

  describe('defaultSerializer', () => {
    // Path: serialize object to JSON
    it('should serialize object to JSON string', () => {
      const obj = { name: 'test', value: 123 };
      expect(defaultSerializer.serialize(obj)).toBe(JSON.stringify(obj));
    });

    // Path: deserialize JSON to object
    it('should deserialize JSON string to object', () => {
      const json = '{"name":"test","value":123}';
      expect(defaultSerializer.deserialize(json)).toEqual({ name: 'test', value: 123 });
    });

    // Path: serialize nested objects
    it('should handle nested objects', () => {
      const nested = { outer: { inner: [1, 2, 3] } };
      const serialized = defaultSerializer.serialize(nested);
      const deserialized = defaultSerializer.deserialize(serialized);
      expect(deserialized).toEqual(nested);
    });

    // Error Path: deserialize invalid JSON
    it('should throw for invalid JSON', () => {
      expect(() => defaultSerializer.deserialize('not json')).toThrow();
    });

    // Boundary: serialize null
    it('should serialize null', () => {
      expect(defaultSerializer.serialize(null)).toBe('null');
    });

    // Boundary: deserialize null
    it('should deserialize null', () => {
      expect(defaultSerializer.deserialize('null')).toBeNull();
    });
  });

  describe('DEFAULT_TIMEOUTS', () => {
    it('should have expected default values', () => {
      expect(DEFAULT_TIMEOUTS).toEqual({
        connect: 5000,
        read: 30000,
        write: 10000,
      });
    });
  });

  describe('DEFAULT_CONTENT_TYPE', () => {
    it('should be application/json', () => {
      expect(DEFAULT_CONTENT_TYPE).toBe('application/json');
    });
  });
});
