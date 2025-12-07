/**
 * Configuration utilities for @internal/fetch-client
 */
import type {
  ClientConfig,
  AuthConfig,
  TimeoutConfig,
  Serializer,
} from './types.mjs';

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
  deserialize: <T = unknown>(text: string): T => JSON.parse(text),
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
  const validTypes = ['bearer', 'x-api-key', 'custom'];

  if (!validTypes.includes(auth.type)) {
    throw new Error(`Invalid auth type: ${auth.type}. Must be one of: ${validTypes.join(', ')}`);
  }

  if (auth.type === 'custom' && !auth.headerName) {
    throw new Error('headerName is required for custom auth type');
  }
}

/**
 * Get auth header name based on auth type
 */
export function getAuthHeaderName(auth: AuthConfig): string {
  switch (auth.type) {
    case 'bearer':
      return 'Authorization';
    case 'x-api-key':
      return 'x-api-key';
    case 'custom':
      return auth.headerName || 'Authorization';
    default:
      return 'Authorization';
  }
}

/**
 * Format auth header value based on auth type
 */
export function formatAuthHeaderValue(auth: AuthConfig, apiKey: string): string {
  switch (auth.type) {
    case 'bearer':
      return `Bearer ${apiKey}`;
    case 'x-api-key':
    case 'custom':
      return apiKey;
    default:
      return apiKey;
  }
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
