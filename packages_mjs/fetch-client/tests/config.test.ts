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
    // Decision: type = 'bearer' with rawApiKey
    it('should pass for bearer auth type with rawApiKey', () => {
      expect(() => validateAuthConfig({ type: 'bearer', rawApiKey: 'key' })).not.toThrow();
    });

    // Decision: type = 'x-api-key' with rawApiKey
    it('should pass for x-api-key auth type with rawApiKey', () => {
      expect(() => validateAuthConfig({ type: 'x-api-key', rawApiKey: 'key' })).not.toThrow();
    });

    // Decision: type = 'custom' with headerName and rawApiKey
    it('should pass for custom auth type with headerName and rawApiKey', () => {
      expect(() =>
        validateAuthConfig({ type: 'custom', headerName: 'X-Custom-Auth', rawApiKey: 'key' })
      ).not.toThrow();
    });

    // Error Path: type = 'custom' without headerName
    it('should throw for custom auth type without headerName', () => {
      expect(() => validateAuthConfig({ type: 'custom', rawApiKey: 'key' })).toThrow(
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

    // Decision: x-api-key -> X-API-Key
    it('should return X-API-Key for x-api-key type', () => {
      expect(getAuthHeaderName({ type: 'x-api-key' })).toBe('X-API-Key');
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

    // =========================================================================
    // Helper for expected base64 values
    // =========================================================================
    function encodeBasic(identifier: string, secret: string): string {
      const credentials = `${identifier}:${secret}`;
      const encoded = Buffer.from(credentials).toString('base64');
      return `Basic ${encoded}`;
    }

    function encodeBearerBase64(identifier: string, secret: string): string {
      const credentials = `${identifier}:${secret}`;
      const encoded = Buffer.from(credentials).toString('base64');
      return `Bearer ${encoded}`;
    }

    // =========================================================================
    // Basic Auth Family Tests
    // =========================================================================

    it('should format basic with email and token', () => {
      const auth: AuthConfig = { type: 'basic', email: 'test@email.com', rawApiKey: 'token123' };
      const result = formatAuthHeaderValue(auth, 'token123');
      expect(result).toBe(encodeBasic('test@email.com', 'token123'));
    });

    it('should format basic with username and token', () => {
      const auth: AuthConfig = { type: 'basic', username: 'testuser', rawApiKey: 'token123' };
      const result = formatAuthHeaderValue(auth, 'token123');
      expect(result).toBe(encodeBasic('testuser', 'token123'));
    });

    it('should format basic with email and password', () => {
      const auth: AuthConfig = { type: 'basic', email: 'test@email.com', password: 'pass123' };
      const result = formatAuthHeaderValue(auth, 'pass123');
      expect(result).toBe(encodeBasic('test@email.com', 'pass123'));
    });

    it('should format basic_email_token', () => {
      const auth: AuthConfig = { type: 'basic_email_token', email: 'user@atlassian.com', rawApiKey: 'api_token' };
      const result = formatAuthHeaderValue(auth, 'api_token');
      expect(result).toBe(encodeBasic('user@atlassian.com', 'api_token'));
    });

    it('should format basic_token', () => {
      const auth: AuthConfig = { type: 'basic_token', username: 'admin', rawApiKey: 'token456' };
      const result = formatAuthHeaderValue(auth, 'token456');
      expect(result).toBe(encodeBasic('admin', 'token456'));
    });

    it('should format basic_email', () => {
      const auth: AuthConfig = { type: 'basic_email', email: 'user@example.com', password: 'secret' };
      const result = formatAuthHeaderValue(auth, 'ignored');
      expect(result).toBe(encodeBasic('user@example.com', 'secret'));
    });

    // =========================================================================
    // Bearer Auth Family Tests
    // =========================================================================

    it('should format bearer with plain token', () => {
      expect(formatAuthHeaderValue({ type: 'bearer' }, apiKey)).toBe(`Bearer ${apiKey}`);
    });

    it('should format bearer with username as base64', () => {
      const auth: AuthConfig = { type: 'bearer', username: 'user', rawApiKey: 'token' };
      const result = formatAuthHeaderValue(auth, 'token');
      expect(result).toBe(encodeBearerBase64('user', 'token'));
    });

    it('should format bearer with email as base64', () => {
      const auth: AuthConfig = { type: 'bearer', email: 'user@test.com', rawApiKey: 'token' };
      const result = formatAuthHeaderValue(auth, 'token');
      expect(result).toBe(encodeBearerBase64('user@test.com', 'token'));
    });

    it('should format bearer_oauth', () => {
      const auth: AuthConfig = { type: 'bearer_oauth', rawApiKey: 'ya29.oauth_token' };
      expect(formatAuthHeaderValue(auth, 'ya29.oauth_token')).toBe('Bearer ya29.oauth_token');
    });

    it('should format bearer_jwt', () => {
      const jwt = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U';
      const auth: AuthConfig = { type: 'bearer_jwt', rawApiKey: jwt };
      expect(formatAuthHeaderValue(auth, jwt)).toBe(`Bearer ${jwt}`);
    });

    it('should format bearer_username_token', () => {
      const auth: AuthConfig = { type: 'bearer_username_token', username: 'apiuser', rawApiKey: 'token789' };
      const result = formatAuthHeaderValue(auth, 'token789');
      expect(result).toBe(encodeBearerBase64('apiuser', 'token789'));
    });

    it('should format bearer_username_password', () => {
      const auth: AuthConfig = { type: 'bearer_username_password', username: 'admin', password: 'adminpass' };
      const result = formatAuthHeaderValue(auth, 'ignored');
      expect(result).toBe(encodeBearerBase64('admin', 'adminpass'));
    });

    it('should format bearer_email_token', () => {
      const auth: AuthConfig = { type: 'bearer_email_token', email: 'user@corp.com', rawApiKey: 'email_token' };
      const result = formatAuthHeaderValue(auth, 'email_token');
      expect(result).toBe(encodeBearerBase64('user@corp.com', 'email_token'));
    });

    it('should format bearer_email_password', () => {
      const auth: AuthConfig = { type: 'bearer_email_password', email: 'user@corp.com', password: 'emailpass' };
      const result = formatAuthHeaderValue(auth, 'ignored');
      expect(result).toBe(encodeBearerBase64('user@corp.com', 'emailpass'));
    });

    // =========================================================================
    // Custom/API Key Auth Tests
    // =========================================================================

    it('should return raw key for x-api-key type', () => {
      expect(formatAuthHeaderValue({ type: 'x-api-key' }, apiKey)).toBe(apiKey);
    });

    it('should return raw key for custom type', () => {
      expect(formatAuthHeaderValue({ type: 'custom', headerName: 'X-Auth' }, apiKey)).toBe(apiKey);
    });

    it('should return raw key for custom_header type', () => {
      const auth: AuthConfig = { type: 'custom_header', headerName: 'X-Service-Key', rawApiKey: 'service_key_123' };
      expect(formatAuthHeaderValue(auth, 'service_key_123')).toBe('service_key_123');
    });

    // =========================================================================
    // Double-Encoding Regression Tests (Bug Fix)
    // =========================================================================

    it('should not double-encode pre-encoded Basic value', () => {
      // Simulate api_token returning pre-encoded value
      const preEncoded = 'Basic dGVzdEBlbWFpbC5jb206dG9rZW4xMjM=';  // test@email.com:token123
      const auth: AuthConfig = { type: 'bearer', rawApiKey: preEncoded };
      const result = formatAuthHeaderValue(auth, preEncoded);
      // Should return as-is, NOT "Bearer Basic dGVzdEBlbWFpbC5jb206dG9rZW4xMjM="
      expect(result).toBe(preEncoded);
      expect(result.startsWith('Bearer Basic')).toBe(false);
    });

    it('should not double-encode pre-encoded Bearer value', () => {
      const preEncoded = 'Bearer token123';
      const auth: AuthConfig = { type: 'bearer', rawApiKey: preEncoded };
      const result = formatAuthHeaderValue(auth, preEncoded);
      // Should return as-is, NOT "Bearer Bearer token123"
      expect(result).toBe(preEncoded);
      expect((result.match(/Bearer/g) || []).length).toBe(1);
    });

    it('should not double-encode pre-encoded Basic with basic auth type', () => {
      const preEncoded = 'Basic dXNlcjpwYXNz';  // user:pass
      const auth: AuthConfig = { type: 'basic', email: 'user', rawApiKey: preEncoded };
      const result = formatAuthHeaderValue(auth, preEncoded);
      // Guard should catch the "Basic " prefix and return as-is
      expect(result).toBe(preEncoded);
    });

    it('should prevent Bearer Basic malformation', () => {
      // This was the actual bug: api_token returned "Basic <base64>",
      // then health check passed it to AuthConfig(type="bearer") which
      // would produce "Bearer Basic <base64>"
      const preEncodedBasic = 'Basic ' + Buffer.from('email:token').toString('base64');
      const auth: AuthConfig = { type: 'bearer', rawApiKey: preEncodedBasic };
      const result = formatAuthHeaderValue(auth, preEncodedBasic);
      // Must NOT start with "Bearer Basic"
      expect(result.startsWith('Bearer Basic')).toBe(false);
      // Should return the pre-encoded Basic value as-is
      expect(result).toBe(preEncodedBasic);
    });

    // =========================================================================
    // Edge Cases and Boundary Values
    // =========================================================================

    it('should handle empty apiKey for bearer', () => {
      expect(() => formatAuthHeaderValue({ type: 'bearer' }, '')).toThrow('bearer requires token');
    });

    it('should return raw key for unknown type (default case)', () => {
      expect(formatAuthHeaderValue({ type: 'unknown' as any }, apiKey)).toBe(apiKey);
    });

    it('should handle special characters in credentials', () => {
      const auth: AuthConfig = { type: 'basic', email: 'user+tag@email.com', rawApiKey: 'p@ss:word!' };
      const result = formatAuthHeaderValue(auth, 'p@ss:word!');
      expect(result).toBe(encodeBasic('user+tag@email.com', 'p@ss:word!'));
    });

    it('should handle unicode in credentials', () => {
      const auth: AuthConfig = { type: 'basic', username: '用户', rawApiKey: '密码' };
      const result = formatAuthHeaderValue(auth, '密码');
      expect(result).toBe(encodeBasic('用户', '密码'));
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
      const auth: AuthConfig = { type: 'bearer', rawApiKey: 'secret' };
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
