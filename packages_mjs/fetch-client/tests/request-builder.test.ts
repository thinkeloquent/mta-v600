/**
 * Tests for request-builder.mts
 * Logic testing: Decision/Branch, Boundary Value, Path coverage
 */
import {
  buildUrl,
  buildHeaders,
  resolveAuthHeader,
  buildBody,
  buildUndiciOptions,
  createRequestContext,
} from '../src/core/request-builder.mjs';
import type { ResolvedConfig } from '../src/config.mjs';
import type { RequestOptions, AuthConfig, RequestContext } from '../src/types.mjs';
import { DEFAULT_TIMEOUTS, defaultSerializer } from '../src/config.mjs';

describe('request-builder', () => {
  describe('buildUrl', () => {
    const baseUrl = new URL('https://api.example.com');

    // Decision: absolute path
    it('should handle absolute path', () => {
      const result = buildUrl(baseUrl, '/api/users');
      expect(result).toBe('https://api.example.com/api/users');
    });

    // Decision: relative path
    it('should handle relative path', () => {
      const base = new URL('https://api.example.com/v1/');
      const result = buildUrl(base, 'users');
      expect(result).toBe('https://api.example.com/v1/users');
    });

    // Path: with query params
    it('should add query params', () => {
      const result = buildUrl(baseUrl, '/users', { page: 1, limit: 10 });
      expect(result).toBe('https://api.example.com/users?page=1&limit=10');
    });

    // Path: query params with boolean
    it('should handle boolean query params', () => {
      const result = buildUrl(baseUrl, '/users', { active: true });
      expect(result).toBe('https://api.example.com/users?active=true');
    });

    // Boundary: empty path
    it('should handle empty path', () => {
      const result = buildUrl(baseUrl, '');
      expect(result).toBe('https://api.example.com/');
    });

    // Boundary: path with special characters
    it('should encode special characters in query values', () => {
      const result = buildUrl(baseUrl, '/search', { q: 'hello world' });
      expect(result).toBe('https://api.example.com/search?q=hello+world');
    });

    // Path: no query params
    it('should work without query params', () => {
      const result = buildUrl(baseUrl, '/users');
      expect(result).toBe('https://api.example.com/users');
    });

    // Boundary: empty query object
    it('should handle empty query object', () => {
      const result = buildUrl(baseUrl, '/users', {});
      expect(result).toBe('https://api.example.com/users');
    });
  });

  describe('buildHeaders', () => {
    const createConfig = (overrides: Partial<ResolvedConfig> = {}): ResolvedConfig => ({
      baseUrl: new URL('https://api.example.com'),
      timeout: DEFAULT_TIMEOUTS,
      headers: {},
      contentType: 'application/json',
      serializer: defaultSerializer,
      ...overrides,
    });

    const createContext = (): RequestContext => ({
      method: 'GET',
      path: '/users',
      headers: {},
    });

    // Path: merges config and options headers
    it('should merge config and options headers', () => {
      const config = createConfig({ headers: { 'User-Agent': 'TestClient' } });
      const options: RequestOptions = { headers: { 'X-Custom': 'value' } };
      const result = buildHeaders(config, options, createContext());

      expect(result['User-Agent']).toBe('TestClient');
      expect(result['X-Custom']).toBe('value');
    });

    // Path: options headers override config headers
    it('should allow options headers to override config headers', () => {
      const config = createConfig({ headers: { 'User-Agent': 'ConfigClient' } });
      const options: RequestOptions = { headers: { 'User-Agent': 'OptionsClient' } };
      const result = buildHeaders(config, options, createContext());

      expect(result['User-Agent']).toBe('OptionsClient');
    });

    // Condition: sets content-type when json present
    it('should set content-type when json is present', () => {
      const config = createConfig();
      const options: RequestOptions = { json: { data: 'test' } };
      const result = buildHeaders(config, options, createContext());

      expect(result['content-type']).toBe('application/json');
    });

    // Condition: sets content-type when body present
    it('should set content-type when body is present', () => {
      const config = createConfig();
      const options: RequestOptions = { body: 'test body' };
      const result = buildHeaders(config, options, createContext());

      expect(result['content-type']).toBe('application/json');
    });

    // Condition: does not override existing content-type
    it('should not override existing content-type header', () => {
      const config = createConfig();
      const options: RequestOptions = {
        json: { data: 'test' },
        headers: { 'content-type': 'text/plain' },
      };
      const result = buildHeaders(config, options, createContext());

      expect(result['content-type']).toBe('text/plain');
    });

    // Condition: no content-type without body
    it('should not set content-type without body or json', () => {
      const config = createConfig();
      const result = buildHeaders(config, {}, createContext());

      expect(result['content-type']).toBeUndefined();
    });

    // Decision: sets accept default
    it('should set accept header to application/json by default', () => {
      const config = createConfig();
      const result = buildHeaders(config, {}, createContext());

      expect(result['accept']).toBe('application/json');
    });

    // Decision: does not override existing accept
    it('should not override existing accept header', () => {
      const config = createConfig();
      const options: RequestOptions = { headers: { accept: 'text/html' } };
      const result = buildHeaders(config, options, createContext());

      expect(result['accept']).toBe('text/html');
    });

    // Path: auth header injection
    it('should inject auth header when auth config present', () => {
      const auth: AuthConfig = { type: 'bearer', apiKey: 'test-key' };
      const config = createConfig({ auth });
      const result = buildHeaders(config, {}, createContext());

      expect(result['Authorization']).toBe('Bearer test-key');
    });

    // Boundary: no auth config
    it('should not add auth header when no auth config', () => {
      const config = createConfig();
      const result = buildHeaders(config, {}, createContext());

      expect(result['Authorization']).toBeUndefined();
    });
  });

  describe('resolveAuthHeader', () => {
    const context: RequestContext = {
      method: 'GET',
      path: '/users',
      headers: {},
    };

    // Decision: callback returns key
    it('should use callback when it returns a key', () => {
      const auth: AuthConfig = {
        type: 'bearer',
        apiKey: 'static-key',
        getApiKeyForRequest: () => 'dynamic-key',
      };
      const result = resolveAuthHeader(auth, context);

      expect(result).toEqual({ Authorization: 'Bearer dynamic-key' });
    });

    // Decision: callback returns undefined, fallback to static
    it('should fallback to static key when callback returns undefined', () => {
      const auth: AuthConfig = {
        type: 'bearer',
        apiKey: 'static-key',
        getApiKeyForRequest: () => undefined,
      };
      const result = resolveAuthHeader(auth, context);

      expect(result).toEqual({ Authorization: 'Bearer static-key' });
    });

    // Decision: no callback, uses static key
    it('should use static key when no callback', () => {
      const auth: AuthConfig = {
        type: 'bearer',
        apiKey: 'static-key',
      };
      const result = resolveAuthHeader(auth, context);

      expect(result).toEqual({ Authorization: 'Bearer static-key' });
    });

    // Boundary: no key available
    it('should return null when no key available', () => {
      const auth: AuthConfig = { type: 'bearer' };
      const result = resolveAuthHeader(auth, context);

      expect(result).toBeNull();
    });

    // Path: x-api-key type
    it('should format x-api-key correctly', () => {
      const auth: AuthConfig = { type: 'x-api-key', apiKey: 'api-key-123' };
      const result = resolveAuthHeader(auth, context);

      expect(result).toEqual({ 'x-api-key': 'api-key-123' });
    });

    // Path: custom type
    it('should use custom header name', () => {
      const auth: AuthConfig = {
        type: 'custom',
        headerName: 'X-Auth-Token',
        apiKey: 'token-123',
      };
      const result = resolveAuthHeader(auth, context);

      expect(result).toEqual({ 'X-Auth-Token': 'token-123' });
    });
  });

  describe('buildBody', () => {
    const serializer = { serialize: (data: unknown) => JSON.stringify(data) };

    // Decision: body takes precedence
    it('should return body when provided', () => {
      const options: RequestOptions = { body: 'raw body' };
      const result = buildBody(options, serializer);

      expect(result).toBe('raw body');
    });

    // Decision: serialize json
    it('should serialize json when provided', () => {
      const options: RequestOptions = { json: { key: 'value' } };
      const result = buildBody(options, serializer);

      expect(result).toBe('{"key":"value"}');
    });

    // Decision: body takes precedence over json
    it('should prefer body over json', () => {
      const options: RequestOptions = { body: 'raw', json: { key: 'value' } };
      const result = buildBody(options, serializer);

      expect(result).toBe('raw');
    });

    // Boundary: neither body nor json
    it('should return undefined when neither body nor json', () => {
      const options: RequestOptions = {};
      const result = buildBody(options, serializer);

      expect(result).toBeUndefined();
    });

    // Path: complex json object
    it('should serialize nested objects', () => {
      const options: RequestOptions = {
        json: { user: { name: 'test', tags: ['a', 'b'] } },
      };
      const result = buildBody(options, serializer);

      expect(result).toBe('{"user":{"name":"test","tags":["a","b"]}}');
    });
  });

  describe('buildUndiciOptions', () => {
    const createConfig = (): ResolvedConfig => ({
      baseUrl: new URL('https://api.example.com'),
      timeout: { connect: 5000, read: 30000, write: 10000 },
      headers: {},
      contentType: 'application/json',
      serializer: defaultSerializer,
    });

    // Path: default method is GET
    it('should default to GET method', () => {
      const config = createConfig();
      const options = { path: '/users' };
      const context: RequestContext = { method: 'GET', path: '/users' };
      const result = buildUndiciOptions(config, options, context);

      expect(result.method).toBe('GET');
    });

    // Path: uses provided method
    it('should use provided method', () => {
      const config = createConfig();
      const options = { path: '/users', method: 'POST' as const };
      const context: RequestContext = { method: 'POST', path: '/users' };
      const result = buildUndiciOptions(config, options, context);

      expect(result.method).toBe('POST');
    });

    // Path: timeout mapping - read → bodyTimeout
    it('should map read timeout to bodyTimeout', () => {
      const config = createConfig();
      const options = { path: '/users' };
      const context: RequestContext = { method: 'GET', path: '/users' };
      const result = buildUndiciOptions(config, options, context);

      expect(result.bodyTimeout).toBe(30000);
    });

    // Path: timeout mapping - connect → headersTimeout
    it('should map connect timeout to headersTimeout', () => {
      const config = createConfig();
      const options = { path: '/users' };
      const context: RequestContext = { method: 'GET', path: '/users' };
      const result = buildUndiciOptions(config, options, context);

      expect(result.headersTimeout).toBe(5000);
    });

    // Path: custom timeout override
    it('should use custom timeout when provided', () => {
      const config = createConfig();
      const options = { path: '/users', timeout: 60000 };
      const context: RequestContext = { method: 'GET', path: '/users' };
      const result = buildUndiciOptions(config, options, context);

      expect(result.bodyTimeout).toBe(60000);
    });

    // Path: includes body for POST
    it('should include serialized body for POST', () => {
      const config = createConfig();
      const options = { path: '/users', method: 'POST' as const, json: { name: 'test' } };
      const context: RequestContext = { method: 'POST', path: '/users', json: { name: 'test' } };
      const result = buildUndiciOptions(config, options, context);

      expect(result.body).toBe('{"name":"test"}');
    });
  });

  describe('createRequestContext', () => {
    // Path: creates context with all fields
    it('should create context from options', () => {
      const options: RequestOptions = {
        headers: { 'X-Custom': 'value' },
        json: { data: 'test' },
      };
      const result = createRequestContext('POST', '/users', options);

      expect(result).toEqual({
        method: 'POST',
        path: '/users',
        headers: { 'X-Custom': 'value' },
        json: { data: 'test' },
      });
    });

    // Boundary: empty options
    it('should handle empty options', () => {
      const result = createRequestContext('GET', '/users', {});

      expect(result).toEqual({
        method: 'GET',
        path: '/users',
        headers: undefined,
        json: undefined,
      });
    });

    // Path: only headers
    it('should handle options with only headers', () => {
      const result = createRequestContext('GET', '/users', {
        headers: { Accept: 'text/html' },
      });

      expect(result.headers).toEqual({ Accept: 'text/html' });
      expect(result.json).toBeUndefined();
    });
  });
});
