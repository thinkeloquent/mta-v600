/**
 * Tests for auth-handler.mts
 * Logic testing: Decision/Branch, Boundary, Path coverage
 */
import {
  BearerAuthHandler,
  XApiKeyAuthHandler,
  CustomAuthHandler,
  createAuthHandler,
} from '../src/auth/auth-handler.mjs';
import type { RequestContext, AuthConfig } from '../src/types.mjs';

describe('auth-handler', () => {
  const createContext = (overrides: Partial<RequestContext> = {}): RequestContext => ({
    method: 'GET',
    path: '/users',
    headers: {},
    ...overrides,
  });

  describe('BearerAuthHandler', () => {
    // Decision: static key
    it('should return Authorization header with static key', () => {
      const handler = new BearerAuthHandler('my-api-key');
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ Authorization: 'Bearer my-api-key' });
    });

    // Decision: callback invoked first
    it('should use callback result when provided', () => {
      const callback = jest.fn().mockReturnValue('dynamic-key');
      const handler = new BearerAuthHandler('static-key', callback);
      const context = createContext();
      const result = handler.getHeader(context);

      expect(callback).toHaveBeenCalledWith(context);
      expect(result).toEqual({ Authorization: 'Bearer dynamic-key' });
    });

    // Decision: callback returns undefined, fallback to static
    it('should fallback to static key when callback returns undefined', () => {
      const callback = jest.fn().mockReturnValue(undefined);
      const handler = new BearerAuthHandler('fallback-key', callback);
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ Authorization: 'Bearer fallback-key' });
    });

    // Boundary: no key available
    it('should return null when no key available', () => {
      const handler = new BearerAuthHandler();
      const result = handler.getHeader(createContext());

      expect(result).toBeNull();
    });

    // Boundary: callback returns empty string (falsy)
    it('should fallback when callback returns empty string', () => {
      const callback = jest.fn().mockReturnValue('');
      const handler = new BearerAuthHandler('static-key', callback);
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ Authorization: 'Bearer static-key' });
    });

    // Path: no static key, callback only
    it('should work with callback only', () => {
      const callback = jest.fn().mockReturnValue('callback-only-key');
      const handler = new BearerAuthHandler(undefined, callback);
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ Authorization: 'Bearer callback-only-key' });
    });
  });

  describe('XApiKeyAuthHandler', () => {
    // Decision: static key
    it('should return x-api-key header with static key', () => {
      const handler = new XApiKeyAuthHandler('my-api-key');
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ 'x-api-key': 'my-api-key' });
    });

    // Decision: callback invoked first
    it('should use callback result when provided', () => {
      const callback = jest.fn().mockReturnValue('dynamic-key');
      const handler = new XApiKeyAuthHandler('static-key', callback);
      const context = createContext();
      const result = handler.getHeader(context);

      expect(callback).toHaveBeenCalledWith(context);
      expect(result).toEqual({ 'x-api-key': 'dynamic-key' });
    });

    // Decision: callback returns undefined, fallback to static
    it('should fallback to static key when callback returns undefined', () => {
      const callback = jest.fn().mockReturnValue(undefined);
      const handler = new XApiKeyAuthHandler('fallback-key', callback);
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ 'x-api-key': 'fallback-key' });
    });

    // Boundary: no key available
    it('should return null when no key available', () => {
      const handler = new XApiKeyAuthHandler();
      const result = handler.getHeader(createContext());

      expect(result).toBeNull();
    });
  });

  describe('CustomAuthHandler', () => {
    // Decision: custom header name
    it('should use custom header name', () => {
      const handler = new CustomAuthHandler('X-My-Auth', 'secret');
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ 'X-My-Auth': 'secret' });
    });

    // Decision: callback invoked first
    it('should use callback result when provided', () => {
      const callback = jest.fn().mockReturnValue('dynamic-secret');
      const handler = new CustomAuthHandler('X-Token', 'static-secret', callback);
      const context = createContext();
      const result = handler.getHeader(context);

      expect(callback).toHaveBeenCalledWith(context);
      expect(result).toEqual({ 'X-Token': 'dynamic-secret' });
    });

    // Decision: callback returns undefined, fallback to static
    it('should fallback to static key when callback returns undefined', () => {
      const callback = jest.fn().mockReturnValue(undefined);
      const handler = new CustomAuthHandler('X-Auth', 'fallback', callback);
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ 'X-Auth': 'fallback' });
    });

    // Boundary: no key available
    it('should return null when no key available', () => {
      const handler = new CustomAuthHandler('X-Auth');
      const result = handler.getHeader(createContext());

      expect(result).toBeNull();
    });

    // Path: header name with different cases
    it('should preserve header name case', () => {
      const handler = new CustomAuthHandler('X-Custom-Header-Name', 'value');
      const result = handler.getHeader(createContext());

      expect(result).toEqual({ 'X-Custom-Header-Name': 'value' });
    });
  });

  describe('createAuthHandler', () => {
    // Decision: bearer type
    it('should create BearerAuthHandler for bearer type', () => {
      const config: AuthConfig = { type: 'bearer', rawApiKey: 'key' };
      const handler = createAuthHandler(config);

      expect(handler).toBeInstanceOf(BearerAuthHandler);
      expect(handler.getHeader(createContext())).toEqual({ Authorization: 'Bearer key' });
    });

    // Decision: x-api-key type
    it('should create XApiKeyAuthHandler for x-api-key type', () => {
      const config: AuthConfig = { type: 'x-api-key', rawApiKey: 'key' };
      const handler = createAuthHandler(config);

      expect(handler).toBeInstanceOf(XApiKeyAuthHandler);
      expect(handler.getHeader(createContext())).toEqual({ 'x-api-key': 'key' });
    });

    // Decision: custom type
    it('should create CustomAuthHandler for custom type', () => {
      const config: AuthConfig = { type: 'custom', headerName: 'X-Auth', rawApiKey: 'key' };
      const handler = createAuthHandler(config);

      expect(handler).toBeInstanceOf(CustomAuthHandler);
      expect(handler.getHeader(createContext())).toEqual({ 'X-Auth': 'key' });
    });

    // Decision: custom type without headerName uses Authorization
    it('should use Authorization for custom type without headerName', () => {
      const config: AuthConfig = { type: 'custom', rawApiKey: 'key' };
      const handler = createAuthHandler(config);

      expect(handler.getHeader(createContext())).toEqual({ Authorization: 'key' });
    });

    // Decision: default case (unknown type)
    it('should create BearerAuthHandler for unknown type (default)', () => {
      const config = { type: 'unknown' as any, rawApiKey: 'key' };
      const handler = createAuthHandler(config);

      expect(handler).toBeInstanceOf(BearerAuthHandler);
    });

    // Path: with getApiKeyForRequest callback
    it('should pass callback to handler', () => {
      const callback = jest.fn().mockReturnValue('dynamic');
      const config: AuthConfig = { type: 'bearer', rawApiKey: 'static', getApiKeyForRequest: callback };
      const handler = createAuthHandler(config);

      handler.getHeader(createContext());
      expect(callback).toHaveBeenCalled();
    });
  });
});
