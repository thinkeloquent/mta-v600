/**
 * Auth handler utilities for @internal/fetch-client
 */
import type { AuthConfig, RequestContext } from '../types.mjs';
import { getComputedApiKey } from '../config.mjs';

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
 *
 * Uses getComputedApiKey() to get the formatted auth header value based on auth type.
 * For example, basic_email_token returns "Basic <base64(email:token)>".
 */
export function createAuthHandler(config: AuthConfig): AuthHandler {
  // Get the computed/formatted auth value based on the auth type
  const computedApiKey = getComputedApiKey(config);

  switch (config.type) {
    case 'bearer':
    case 'bearer_oauth':
    case 'bearer_jwt':
    case 'bearer_username_token':
    case 'bearer_username_password':
    case 'bearer_email_token':
    case 'bearer_email_password':
      // Bearer types - computedApiKey already includes "Bearer " prefix
      // Use raw key since BearerAuthHandler adds "Bearer " prefix
      return new BearerAuthHandler(config.rawApiKey, config.getApiKeyForRequest);

    case 'x-api-key':
      return new XApiKeyAuthHandler(config.rawApiKey, config.getApiKeyForRequest);

    case 'basic':
    case 'basic_email_token':
    case 'basic_token':
    case 'basic_email':
      // Basic auth - return full computed value ("Basic <base64>")
      // Use CustomAuthHandler with Authorization header to pass the pre-computed value
      return new CustomAuthHandler(
        'Authorization',
        computedApiKey,
        config.getApiKeyForRequest
      );

    case 'custom':
    case 'custom_header':
      return new CustomAuthHandler(
        config.headerName || 'Authorization',
        config.rawApiKey,
        config.getApiKeyForRequest
      );

    default:
      // Default to bearer with rawApiKey
      return new BearerAuthHandler(config.rawApiKey, config.getApiKeyForRequest);
  }
}
