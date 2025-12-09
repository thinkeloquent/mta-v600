/**
 * @internal/fetch-client
 *
 * Enterprise-grade, latency-optimized HTTP client with streaming support.
 *
 * @example
 * ```typescript
 * import { createClient, warmupDns } from '@internal/fetch-client';
 * import { ProxyDispatcherFactory } from '@internal/fetch-proxy-dispatcher';
 *
 * // Get dispatcher
 * const factory = new ProxyDispatcherFactory({ ... });
 * const dispatcher = factory.getDispatcherForEnvironment('QA');
 *
 * // Warmup DNS (optional)
 * await warmupDns('api.example.com');
 *
 * // Create client
 * const client = createClient({
 *   baseUrl: 'https://api.example.com',
 *   dispatcher,
 *   auth: {
 *     type: 'bearer',
 *     apiKey: process.env.API_KEY,
 *   },
 * });
 *
 * // Make requests
 * const response = await client.get('/users/123');
 *
 * // Stream SSE
 * for await (const event of client.stream('/v1/chat', { method: 'POST', json: {...} })) {
 *   console.log(event.data);
 * }
 * ```
 */

// Types
export type {
  AuthType,
  StreamFormat,
  ProtocolType,
  HttpMethod,
  RequestContext,
  AuthConfig,
  TimeoutConfig,
  ClientConfig,
  RequestOptions,
  FetchResponse,
  SSEEvent,
  StreamOptions,
  FetchClient,
  DiagnosticsEvent,
  Serializer,
} from './types.mjs';

// Config
export {
  DEFAULT_TIMEOUTS,
  DEFAULT_CONTENT_TYPE,
  defaultSerializer,
  normalizeTimeout,
  validateConfig,
  validateAuthConfig,
  getAuthHeaderName,
  formatAuthHeaderValue,
  resolveConfig,
  type ResolvedConfig,
} from './config.mjs';

// DNS Warmup
export {
  warmupDns,
  warmupDnsMany,
  warmupDnsForUrl,
  extractHostname,
  type DnsWarmupResult,
} from './dns-warmup.mjs';

// Factory
export {
  createClient,
  createClientWithDispatcher,
  createClients,
  closeClients,
  BaseClient,
  RestAdapter,
  type ClientConfigWithProxy,
} from './factory.mjs';

// Auth
export {
  createAuthHandler,
  BearerAuthHandler,
  XApiKeyAuthHandler,
  CustomAuthHandler,
  type AuthHandler,
} from './auth/auth-handler.mjs';

// Streaming
export {
  parseSSEStream,
  parseSSEEvent,
  parseSSEData,
} from './streaming/sse-reader.mjs';

export {
  parseNdjsonStream,
  parseNdjsonStreamSimple,
  encodeNdjson,
} from './streaming/ndjson-reader.mjs';

// Diagnostics
export {
  CHANNELS,
  emitRequestStart,
  emitRequestEnd,
  emitRequestError,
  onRequestStart,
  onRequestEnd,
  onRequestError,
  onAllEvents,
} from './diagnostics.mjs';

// Core (for advanced usage)
export {
  buildUrl,
  buildHeaders,
  buildBody,
  buildUndiciOptions,
  createRequestContext,
  resolveAuthHeader,
} from './core/request-builder.mjs';
