/**
 * Type definitions for @internal/fetch-client
 */
import type { Dispatcher } from 'undici';

/**
 * Authentication type options - Comprehensive authentication type system
 *
 * Basic auth family (Authorization: Basic <base64>):
 * - basic: Auto-compute Basic <base64((username|email):(password|token))>
 * - basic_email_token: Basic <base64(email:token)> - Atlassian APIs
 * - basic_token: Basic <base64(username:token)>
 * - basic_email: Basic <base64(email:password)>
 *
 * Bearer auth family (Authorization: Bearer <value>):
 * - bearer: Auto-compute Bearer <PAT|OAuth|JWT|base64(...)>
 * - bearer_oauth: Bearer <OAuth2.0_token>
 * - bearer_jwt: Bearer <JWT_token>
 * - bearer_username_token: Bearer <base64(username:token)>
 * - bearer_username_password: Bearer <base64(username:password)>
 * - bearer_email_token: Bearer <base64(email:token)>
 * - bearer_email_password: Bearer <base64(email:password)>
 *
 * Custom/API Key auth:
 * - x-api-key: api_key in X-API-Key header
 * - custom: raw string in custom header (specified by headerName)
 * - custom_header: api_key in custom header (specified by headerName)
 *
 * HMAC auth (stub for future implementation):
 * - hmac: AWS Signature, GCP HMAC, HTTP Signatures, Webhooks
 */
export type AuthType =
  // Basic auth family
  | 'basic'
  | 'basic_email_token'
  | 'basic_token'
  | 'basic_email'
  // Bearer auth family
  | 'bearer'
  | 'bearer_oauth'
  | 'bearer_jwt'
  | 'bearer_username_token'
  | 'bearer_username_password'
  | 'bearer_email_token'
  | 'bearer_email_password'
  // Custom/API Key
  | 'x-api-key'
  | 'custom'
  | 'custom_header'
  // HMAC (stub)
  | 'hmac';

/**
 * Streaming format options
 */
export type StreamFormat = 'sse' | 'ndjson' | false;

/**
 * Protocol type options
 */
export type ProtocolType = 'rest' | 'rpc';

/**
 * HTTP methods
 */
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS';

/**
 * Request context passed to auth callback
 */
export interface RequestContext {
  method: HttpMethod;
  path: string;
  headers?: Record<string, string>;
  json?: unknown;
}

/**
 * Auth configuration
 *
 * Note: Use `rawApiKey` to provide the original token/key value.
 * Use `getComputedApiKey(auth)` from config.mts to get the formatted
 * auth header value based on the `type`.
 */
export interface AuthConfig {
  type: AuthType;
  rawApiKey?: string; // Original token/key value (use getComputedApiKey() for formatted value)
  username?: string; // For basic/bearer_username_* types
  email?: string; // For *_email* types
  password?: string; // For *_password types
  headerName?: string; // For custom/custom_header types
  getApiKeyForRequest?: (context: RequestContext) => string | undefined;
}

/**
 * Timeout configuration
 */
export interface TimeoutConfig {
  connect?: number;
  read?: number;
  write?: number;
}

/**
 * Client configuration
 */
export interface ClientConfig {
  baseUrl: string;
  dispatcher?: Dispatcher;
  auth?: AuthConfig;
  timeout?: TimeoutConfig | number;
  headers?: Record<string, string>;
  contentType?: string;
  protocol?: ProtocolType;
  streaming?: StreamFormat;
}

/**
 * Request options for fetch client
 */
export interface RequestOptions {
  method?: HttpMethod;
  path?: string;
  headers?: Record<string, string>;
  json?: unknown;
  body?: string | Buffer | ReadableStream;
  query?: Record<string, string | number | boolean>;
  timeout?: number;
}

/**
 * Response from fetch client
 */
export interface FetchResponse<T = unknown> {
  status: number;
  statusText: string;
  headers: Record<string, string>;
  data: T;
  ok: boolean;
}

/**
 * SSE event structure
 */
export interface SSEEvent {
  id?: string;
  event?: string;
  data: string;
  retry?: number;
}

/**
 * Stream options
 */
export interface StreamOptions extends RequestOptions {
  onEvent?: (event: SSEEvent) => void;
  signal?: AbortSignal;
}

/**
 * Fetch client interface
 */
export interface FetchClient {
  get<T = unknown>(path: string, options?: RequestOptions): Promise<FetchResponse<T>>;
  post<T = unknown>(path: string, options?: RequestOptions): Promise<FetchResponse<T>>;
  put<T = unknown>(path: string, options?: RequestOptions): Promise<FetchResponse<T>>;
  patch<T = unknown>(path: string, options?: RequestOptions): Promise<FetchResponse<T>>;
  delete<T = unknown>(path: string, options?: RequestOptions): Promise<FetchResponse<T>>;
  request<T = unknown>(options: RequestOptions & { path: string }): Promise<FetchResponse<T>>;
  stream(path: string, options?: StreamOptions): AsyncGenerator<SSEEvent, void, unknown>;
  streamNdjson<T = unknown>(path: string, options?: StreamOptions): AsyncGenerator<T, void, unknown>;
  close(): Promise<void>;
}

/**
 * Diagnostics event types
 */
export interface DiagnosticsEvent {
  name: string;
  timestamp: number;
  duration?: number;
  request?: {
    method: HttpMethod;
    url: string;
    headers?: Record<string, string>;
  };
  response?: {
    status: number;
    headers?: Record<string, string>;
  };
  error?: Error;
}

/**
 * Serializer interface for custom JSON handling
 */
export interface Serializer {
  serialize: (data: unknown) => string;
  deserialize: <T = unknown>(text: string) => T;
}
