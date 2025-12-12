/**
 * Auth handler utilities for @internal/fetch-client
 */
import type { AuthConfig, RequestContext } from '../types.mjs';
import { getComputedApiKey } from '../config.mjs';

// Get current file path for logging
const LOG_PREFIX = `[AUTH:auth-handler.mts]`;

/**
 * Mask sensitive value for logging, showing first 10 chars.
 */
function maskValue(val: string | undefined): string {
  if (!val) return '<empty>';
  if (val.length <= 10) return '*'.repeat(val.length);
  return val.substring(0, 10) + '*'.repeat(val.length - 10);
}

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
  ) { }

  getHeader(context: RequestContext): Record<string, string> | null {
    const key = this.getApiKeyForRequest?.(context) || this.apiKey;
    if (!key) return null;
    const header = { Authorization: `Bearer ${key}` };
    console.log(
      `${LOG_PREFIX} BearerAuthHandler.getHeader: apiKey=${maskValue(key)} -> Authorization=${maskValue(header.Authorization)}`
    );
    return header;
  }
}

/**
 * X-API-Key auth handler
 */
export class XApiKeyAuthHandler implements AuthHandler {
  constructor(
    private apiKey?: string,
    private getApiKeyForRequest?: (context: RequestContext) => string | undefined
  ) { }

  getHeader(context: RequestContext): Record<string, string> | null {
    const key = this.getApiKeyForRequest?.(context) || this.apiKey;
    if (!key) return null;
    console.log(`${LOG_PREFIX} XApiKeyAuthHandler.getHeader: apiKey=${maskValue(key)}`);
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
  ) { }

  getHeader(context: RequestContext): Record<string, string> | null {
    const key = this.getApiKeyForRequest?.(context) || this.apiKey;
    if (!key) return null;
    console.log(
      `${LOG_PREFIX} CustomAuthHandler.getHeader: headerName=${this.headerName}, apiKey=${maskValue(key)}`
    );
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

  console.log(
    `${LOG_PREFIX} createAuthHandler: type=${config.type}, rawApiKey=${maskValue(config.rawApiKey)}, ` +
    `computedApiKey=${maskValue(computedApiKey)}, email=${maskValue(config.email)}, username=${maskValue(config.username)}`
  );

  switch (config.type) {
    case 'bearer':
    case 'bearer_oauth':
    case 'bearer_jwt':
      {
        // Simple Bearer types (token only)
        // If it's a generic 'bearer' with credentials (username/email), treat as complex
        const isComplex = config.type === 'bearer' && (config.username || config.email);

        if (isComplex) {
          console.log(
            `${LOG_PREFIX} createAuthHandler: Bearer with credentials detected, using computedApiKey=${maskValue(computedApiKey)}`
          );
          // Use CustomAuthHandler to pass the full "Bearer <base64>" header
          return new CustomAuthHandler(
            'Authorization',
            computedApiKey,
            config.getApiKeyForRequest
          );
        }

        // Simple token case
        console.log(
          `${LOG_PREFIX} createAuthHandler: Bearer token type detected, using rawApiKey=${maskValue(config.rawApiKey)} (NOT computedApiKey)`
        );
        return new BearerAuthHandler(config.rawApiKey, config.getApiKeyForRequest);
      }

    case 'bearer_username_token':
    case 'bearer_username_password':
    case 'bearer_email_token':
    case 'bearer_email_password':
      // Complex Bearer types - return full computed value ("Bearer <base64>")
      console.log(
        `${LOG_PREFIX} createAuthHandler: Complex Bearer type detected, using computedApiKey=${maskValue(computedApiKey)}`
      );
      return new CustomAuthHandler(
        'Authorization',
        computedApiKey,
        config.getApiKeyForRequest
      );

    case 'x-api-key':
      console.log(`${LOG_PREFIX} createAuthHandler: x-api-key type, using rawApiKey`);
      return new XApiKeyAuthHandler(config.rawApiKey, config.getApiKeyForRequest);

    case 'basic':
    case 'basic_email_token':
    case 'basic_token':
    case 'basic_email':
      // Basic auth - return full computed value ("Basic <base64>")
      // Use CustomAuthHandler with Authorization header to pass the pre-computed value
      console.log(
        `${LOG_PREFIX} createAuthHandler: Basic type detected, using computedApiKey=${maskValue(computedApiKey)}`
      );
      return new CustomAuthHandler(
        'Authorization',
        computedApiKey,
        config.getApiKeyForRequest
      );

    case 'custom':
    case 'custom_header':
      console.log(
        `${LOG_PREFIX} createAuthHandler: Custom type, headerName=${config.headerName}, using rawApiKey`
      );
      return new CustomAuthHandler(
        config.headerName || 'Authorization',
        config.rawApiKey,
        config.getApiKeyForRequest
      );

    default:
      // Default to bearer with rawApiKey
      console.log(
        `${LOG_PREFIX} createAuthHandler: Unknown type '${config.type}', defaulting to bearer with rawApiKey`
      );
      return new BearerAuthHandler(config.rawApiKey, config.getApiKeyForRequest);
  }
}
