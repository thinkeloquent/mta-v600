/**
 * Configuration utilities for @internal/fetch-client
 */
import type {
  ClientConfig,
  AuthConfig,
  TimeoutConfig,
  Serializer,
} from './types.mjs';
import { encodeAuth } from '@internal/fetch-auth-encoding';

// Get current file path for logging
const LOG_PREFIX = `[AUTH:config.mts]`;

/**
 * Default timeout values in milliseconds
 */
export const DEFAULT_TIMEOUTS: Required<TimeoutConfig> = {
  connect: 5000,
  read: 30000,
  write: 10000,
};

/**
 * Default content type
 */
export const DEFAULT_CONTENT_TYPE = 'application/json';

/**
 * Default JSON serializer
 */
export const defaultSerializer: Serializer = {
  serialize: (data: unknown) => JSON.stringify(data),
  deserialize: <T = unknown,>(text: string): T => JSON.parse(text),
};

/**
 * Normalize timeout config to milliseconds
 */
export function normalizeTimeout(timeout?: TimeoutConfig | number): Required<TimeoutConfig> {
  if (typeof timeout === 'number') {
    return {
      connect: timeout,
      read: timeout,
      write: timeout,
    };
  }

  return {
    connect: timeout?.connect ?? DEFAULT_TIMEOUTS.connect,
    read: timeout?.read ?? DEFAULT_TIMEOUTS.read,
    write: timeout?.write ?? DEFAULT_TIMEOUTS.write,
  };
}

/**
 * Validate client configuration
 */
export function validateConfig(config: ClientConfig): void {
  if (!config.baseUrl) {
    throw new Error('baseUrl is required');
  }

  try {
    new URL(config.baseUrl);
  } catch {
    throw new Error(`Invalid baseUrl: ${config.baseUrl}`);
  }

  if (config.auth) {
    validateAuthConfig(config.auth);
  }
}

/**
 * Validate auth configuration
 */
export function validateAuthConfig(auth: AuthConfig): void {
  const validTypes = [
    // Basic auth family
    'basic', 'basic_email_token', 'basic_token', 'basic_email',
    // Bearer auth family
    'bearer', 'bearer_oauth', 'bearer_jwt',
    'bearer_username_token', 'bearer_username_password',
    'bearer_email_token', 'bearer_email_password',
    // Custom/API Key
    'x-api-key', 'custom', 'custom_header',
    // HMAC (stub)
    'hmac',
  ];

  if (!validTypes.includes(auth.type)) {
    throw new Error(`Invalid auth type: ${auth.type}. Must be one of: ${validTypes.sort().join(', ')}`);
  }

  // Validation rules per type
  if (auth.type === 'basic') {
    // Auto-compute: need (username OR email) AND (password OR rawApiKey)
    const hasIdentifier = auth.username || auth.email;
    const hasSecret = auth.password || auth.rawApiKey;
    if (!hasIdentifier || !hasSecret) {
      throw new Error('basic auth requires (username OR email) AND (password OR rawApiKey)');
    }
  } else if (auth.type === 'basic_email_token') {
    if (!auth.email) {
      throw new Error('email is required for basic_email_token auth type');
    }
    if (!auth.rawApiKey) {
      throw new Error('rawApiKey is required for basic_email_token auth type');
    }
  } else if (auth.type === 'basic_token') {
    if (!auth.username) {
      throw new Error('username is required for basic_token auth type');
    }
    if (!auth.rawApiKey) {
      throw new Error('rawApiKey is required for basic_token auth type');
    }
  } else if (auth.type === 'basic_email') {
    if (!auth.email) {
      throw new Error('email is required for basic_email auth type');
    }
    if (!auth.password) {
      throw new Error('password is required for basic_email auth type');
    }
  } else if (auth.type === 'bearer') {
    if (!auth.rawApiKey) {
      throw new Error('rawApiKey is required for bearer auth type');
    }
  } else if (auth.type === 'bearer_oauth' || auth.type === 'bearer_jwt') {
    if (!auth.rawApiKey) {
      throw new Error(`rawApiKey is required for ${auth.type} auth type`);
    }
  } else if (auth.type === 'bearer_username_token') {
    if (!auth.username) {
      throw new Error('username is required for bearer_username_token auth type');
    }
    if (!auth.rawApiKey) {
      throw new Error('rawApiKey is required for bearer_username_token auth type');
    }
  } else if (auth.type === 'bearer_username_password') {
    if (!auth.username) {
      throw new Error('username is required for bearer_username_password auth type');
    }
    if (!auth.password) {
      throw new Error('password is required for bearer_username_password auth type');
    }
  } else if (auth.type === 'bearer_email_token') {
    if (!auth.email) {
      throw new Error('email is required for bearer_email_token auth type');
    }
    if (!auth.rawApiKey) {
      throw new Error('rawApiKey is required for bearer_email_token auth type');
    }
  } else if (auth.type === 'bearer_email_password') {
    if (!auth.email) {
      throw new Error('email is required for bearer_email_password auth type');
    }
    if (!auth.password) {
      throw new Error('password is required for bearer_email_password auth type');
    }
  } else if (auth.type === 'x-api-key') {
    if (!auth.rawApiKey) {
      throw new Error('rawApiKey is required for x-api-key auth type');
    }
  } else if (auth.type === 'custom' || auth.type === 'custom_header') {
    if (!auth.headerName) {
      throw new Error(`headerName is required for ${auth.type} auth type`);
    }
    if (!auth.rawApiKey) {
      throw new Error(`rawApiKey is required for ${auth.type} auth type`);
    }
  } else if (auth.type === 'hmac') {
    // HMAC validation is a stub - will be expanded with AuthConfigHMAC
    throw new Error('hmac auth type requires AuthConfigHMAC class (not yet implemented)');
  }
}

/**
 * Get auth header name based on auth type
 */
export function getAuthHeaderName(auth: AuthConfig): string {
  // Basic auth family - all use Authorization header
  if (['basic', 'basic_email_token', 'basic_token', 'basic_email'].includes(auth.type)) {
    return 'Authorization';
  }

  // Bearer auth family - all use Authorization header
  if ([
    'bearer', 'bearer_oauth', 'bearer_jwt',
    'bearer_username_token', 'bearer_username_password',
    'bearer_email_token', 'bearer_email_password',
  ].includes(auth.type)) {
    return 'Authorization';
  }

  // X-API-Key header
  if (auth.type === 'x-api-key') {
    return 'X-API-Key';
  }

  // Custom header
  if (auth.type === 'custom' || auth.type === 'custom_header') {
    return auth.headerName || 'Authorization';
  }

  // HMAC - varies by type, default to Authorization
  if (auth.type === 'hmac') {
    return 'Authorization';
  }

  return 'Authorization';
}

/**
 * Get the computed/formatted API key value based on auth type.
 *
 * This function returns the formatted auth header value (e.g., "Basic <base64>" or "Bearer <token>")
 * based on the auth configuration. Use this when you need the final value to send in headers.
 *
 * @param auth - The auth configuration with rawApiKey
 * @returns The computed auth header value, or undefined if rawApiKey is not set
 */
export function getComputedApiKey(auth: AuthConfig): string | undefined {
  if (auth.rawApiKey === undefined) {
    return undefined;
  }
  return formatAuthHeaderValue(auth, auth.rawApiKey);
}

/**
 * Mask sensitive value for logging, showing first 10 chars.
 */
function maskValue(val: string): string {
  if (!val) return '<empty>';
  if (val.length <= 10) return '*'.repeat(val.length);
  return val.substring(0, 10) + '*'.repeat(val.length - 10);
}

/**
 * Format auth header value based on auth type
 *
 * Auto-compute defaults:
 * - basic: Detects identifier (email OR username) and secret (password OR rawApiKey)
 * - bearer: If has identifier+secret, encodes as base64; otherwise uses rawApiKey as-is
 *
 * Guard against double-encoding:
 * - If apiKey already starts with "Basic " or "Bearer ", return as-is
 * - This prevents malformed headers like "Bearer Basic <base64>" when
 *   pre-encoded values are passed through
 *
 * Logs encoding method with masked input/output for debugging.
 */
export function formatAuthHeaderValue(auth: AuthConfig, apiKey: string): string {
  // Guard: if apiKey already has a scheme prefix, return as-is to prevent double-encoding
  // This handles cases where api_token layer returns pre-encoded values like "Basic <base64>"
  if (apiKey && (apiKey.startsWith('Basic ') || apiKey.startsWith('Bearer '))) {
    console.log(
      `${LOG_PREFIX} formatAuthHeaderValue: Pre-encoded value detected (starts with scheme prefix), ` +
      `returning as-is: ${maskValue(apiKey)}`
    );
    return apiKey;
  }

  // === Basic Auth Family ===
  if (['basic', 'basic_email_token', 'basic_token', 'basic_email'].includes(auth.type)) {
    // Map specific types to generic Basic credentials
    const identifier = auth.email || auth.username || '';
    const secret = auth.password || apiKey;

    // Use fetch-auth-encoding
    const headers = encodeAuth('basic', { username: identifier, password: secret });
    return headers.Authorization;
  }

  // === Bearer Auth Family ===
  if (auth.type === 'bearer') {
    // Strict: use apiKey as-is (PAT, OAuth, JWT)
    const headers = encodeAuth('bearer', { token: apiKey });
    return headers.Authorization;
  }

  if (auth.type === 'bearer_oauth' || auth.type === 'bearer_jwt') {
    const headers = encodeAuth('bearer', { token: apiKey });
    return headers.Authorization;
  }

  if ([
    'bearer_username_token',
    'bearer_username_password',
    'bearer_email_token',
    'bearer_email_password'
  ].includes(auth.type)) {
    const identifier = auth.email || auth.username || '';
    const secret = auth.password || apiKey;
    const headers = encodeAuth('bearer_username_password', { username: identifier, password: secret });
    return headers.Authorization;
  }

  // === Custom/API Key ===
  if (auth.type === 'x-api-key') {
    console.log(
      `${LOG_PREFIX} formatAuthHeaderValue: x-api-key - ` +
      `input=${maskValue(apiKey)} -> output=${maskValue(apiKey)}`
    );
    return apiKey;
  }

  if (auth.type === 'custom' || auth.type === 'custom_header') {
    console.log(
      `${LOG_PREFIX} formatAuthHeaderValue: ${auth.type} - ` +
      `input=${maskValue(apiKey)} -> output=${maskValue(apiKey)}`
    );
    return apiKey;
  }

  // === HMAC (stub) ===
  if (auth.type === 'hmac') {
    // HMAC requires separate handling with AuthConfigHMAC
    throw new Error('hmac auth type requires AuthConfigHMAC class (not yet implemented)');
  }

  console.warn(
    `${LOG_PREFIX} formatAuthHeaderValue: Unknown auth type '${auth.type}', returning apiKey as-is`
  );
  return apiKey;
}

/**
 * Resolved client configuration with defaults applied
 */
export interface ResolvedConfig {
  baseUrl: URL;
  timeout: Required<TimeoutConfig>;
  headers: Record<string, string>;
  contentType: string;
  auth?: AuthConfig;
  serializer: Serializer;
}

/**
 * Resolve client configuration with defaults
 */
export function resolveConfig(config: ClientConfig): ResolvedConfig {
  validateConfig(config);

  return {
    baseUrl: new URL(config.baseUrl),
    timeout: normalizeTimeout(config.timeout),
    headers: { ...config.headers },
    contentType: config.contentType || DEFAULT_CONTENT_TYPE,
    auth: config.auth,
    serializer: defaultSerializer,
  };
}

export type { ClientConfig, AuthConfig, TimeoutConfig };
