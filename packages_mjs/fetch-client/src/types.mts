/**
 * Type definitions for @internal/fetch-client
 */
import type { Dispatcher } from 'undici';

/**
 * Authentication type options
 */
export type AuthType = 'bearer' | 'x-api-key' | 'custom';

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
 */
export interface AuthConfig {
  type: AuthType;
  apiKey?: string;
  headerName?: string;
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
