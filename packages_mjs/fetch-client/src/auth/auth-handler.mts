/**
 * Auth handler utilities for @internal/fetch-client
 */
import type { AuthConfig, RequestContext } from '../types.mjs';

/**
 * Auth handler interface
 */
export interface AuthHandler {
  getHeader(context: RequestContext): Record<string, string> | null;
}

/**
 * Bearer token auth handler
 */
export class BearerAuthHandler implements AuthHandler {
  constructor(
    private apiKey?: string,
    private getApiKeyForRequest?: (context: RequestContext) => string | undefined
  ) {}

  getHeader(context: RequestContext): Record<string, string> | null {
    const key = this.getApiKeyForRequest?.(context) || this.apiKey;
    if (!key) return null;
    return { Authorization: `Bearer ${key}` };
  }
}

/**
 * X-API-Key auth handler
 */
export class XApiKeyAuthHandler implements AuthHandler {
  constructor(
    private apiKey?: string,
    private getApiKeyForRequest?: (context: RequestContext) => string | undefined
  ) {}

  getHeader(context: RequestContext): Record<string, string> | null {
    const key = this.getApiKeyForRequest?.(context) || this.apiKey;
    if (!key) return null;
    return { 'x-api-key': key };
  }
}

/**
 * Custom header auth handler
 */
export class CustomAuthHandler implements AuthHandler {
  constructor(
    private headerName: string,
    private apiKey?: string,
    private getApiKeyForRequest?: (context: RequestContext) => string | undefined
  ) {}

  getHeader(context: RequestContext): Record<string, string> | null {
    const key = this.getApiKeyForRequest?.(context) || this.apiKey;
    if (!key) return null;
    return { [this.headerName]: key };
  }
}

/**
 * Create auth handler from config
 */
export function createAuthHandler(config: AuthConfig): AuthHandler {
  switch (config.type) {
    case 'bearer':
      return new BearerAuthHandler(config.apiKey, config.getApiKeyForRequest);
    case 'x-api-key':
      return new XApiKeyAuthHandler(config.apiKey, config.getApiKeyForRequest);
    case 'custom':
      return new CustomAuthHandler(
        config.headerName || 'Authorization',
        config.apiKey,
        config.getApiKeyForRequest
      );
    default:
      return new BearerAuthHandler(config.apiKey, config.getApiKeyForRequest);
  }
}
