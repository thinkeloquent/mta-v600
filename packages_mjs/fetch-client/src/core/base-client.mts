/**
 * Base HTTP client using undici
 */
import { request } from 'undici';
import type { Dispatcher } from 'undici';
import pino from 'pino';
import type {
  ClientConfig,
  RequestOptions,
  FetchResponse,
  HttpMethod,
  SSEEvent,
  StreamOptions,
  FetchClient,
} from '../types.mjs';
import { resolveConfig, type ResolvedConfig } from '../config.mjs';
import {
  buildUrl,
  buildUndiciOptions,
  createRequestContext,
} from './request-builder.mjs';
import { parseSSEStream } from '../streaming/sse-reader.mjs';
import { parseNdjsonStream } from '../streaming/ndjson-reader.mjs';

// Create pino logger with pretty printing
const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true,
    },
  },
});

/**
 * Mask auth header values for safe logging
 */
function maskAuthHeader(headers: Record<string, string>): Record<string, string> {
  const masked = { ...headers };
  for (const key of Object.keys(masked)) {
    if (key.toLowerCase() === 'authorization' || key.toLowerCase() === 'x-api-key') {
      const value = masked[key];
      if (value.length > 10) {
        masked[key] = value.slice(0, 10) + '*'.repeat(value.length - 10);
      } else {
        masked[key] = '*'.repeat(value.length);
      }
    }
  }
  return masked;
}

/**
 * Base HTTP client implementation
 */
export class BaseClient implements FetchClient {
  protected config: ResolvedConfig;
  protected dispatcher?: Dispatcher;
  private closed = false;

  constructor(clientConfig: ClientConfig) {
    this.config = resolveConfig(clientConfig);
    this.dispatcher = clientConfig.dispatcher;
  }

  /**
   * Make a generic HTTP request
   */
  async request<T = unknown>(
    options: RequestOptions & { path: string }
  ): Promise<FetchResponse<T>> {
    if (this.closed) {
      throw new Error('Client has been closed');
    }

    const method = options.method || 'GET';
    const url = buildUrl(this.config.baseUrl, options.path, options.query);
    const context = createRequestContext(method, options.path, options);
    const undiciOptions = buildUndiciOptions(this.config, options, context);

    // Log request
    const maskedHeaders = maskAuthHeader(undiciOptions.headers as Record<string, string>);
    logger.info({
      type: 'request',
      method,
      url,
      headers: maskedHeaders,
      body: options.json,
    }, `Request: ${method} ${url}`);

    const response = await request(url, {
      ...undiciOptions,
      dispatcher: this.dispatcher,
    });

    const responseHeaders: Record<string, string> = {};
    for (const [key, value] of Object.entries(response.headers)) {
      if (typeof value === 'string') {
        responseHeaders[key] = value;
      } else if (Array.isArray(value)) {
        responseHeaders[key] = value.join(', ');
      }
    }

    const text = await response.body.text();
    let data: T;

    try {
      data = this.config.serializer.deserialize<T>(text);
    } catch {
      data = text as unknown as T;
    }

    // Log response
    const isOk = response.statusCode >= 200 && response.statusCode < 300;
    const logLevel = isOk ? 'info' : 'error';
    logger[logLevel]({
      type: 'response',
      status: response.statusCode,
      headers: responseHeaders,
      body: data,
    }, `Response: ${response.statusCode}`);

    return {
      status: response.statusCode,
      statusText: '',
      headers: responseHeaders,
      data,
      ok: isOk,
    };
  }

  /**
   * GET request
   */
  async get<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.request<T>({ ...options, path, method: 'GET' });
  }

  /**
   * POST request
   */
  async post<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.request<T>({ ...options, path, method: 'POST' });
  }

  /**
   * PUT request
   */
  async put<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.request<T>({ ...options, path, method: 'PUT' });
  }

  /**
   * PATCH request
   */
  async patch<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.request<T>({ ...options, path, method: 'PATCH' });
  }

  /**
   * DELETE request
   */
  async delete<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.request<T>({ ...options, path, method: 'DELETE' });
  }

  /**
   * Stream SSE response
   */
  async *stream(
    path: string,
    options: StreamOptions = {}
  ): AsyncGenerator<SSEEvent, void, unknown> {
    if (this.closed) {
      throw new Error('Client has been closed');
    }

    const method = options.method || 'POST';
    const url = buildUrl(this.config.baseUrl, path, options.query);
    const context = createRequestContext(method, path, options);
    const undiciOptions = buildUndiciOptions(this.config, { ...options, path, method }, context);

    // Set accept header for SSE
    undiciOptions.headers['accept'] = 'text/event-stream';

    const response = await request(url, {
      ...undiciOptions,
      dispatcher: this.dispatcher,
    });

    if (response.statusCode < 200 || response.statusCode >= 300) {
      const text = await response.body.text();
      throw new Error(`HTTP ${response.statusCode}: ${text}`);
    }

    yield* parseSSEStream(response.body);
  }

  /**
   * Stream NDJSON response
   */
  async *streamNdjson<T = unknown>(
    path: string,
    options: StreamOptions = {}
  ): AsyncGenerator<T, void, unknown> {
    if (this.closed) {
      throw new Error('Client has been closed');
    }

    const method = options.method || 'GET';
    const url = buildUrl(this.config.baseUrl, path, options.query);
    const context = createRequestContext(method, path, options);
    const undiciOptions = buildUndiciOptions(this.config, { ...options, path }, context);

    // Set accept header for NDJSON
    undiciOptions.headers['accept'] = 'application/x-ndjson';

    const response = await request(url, {
      ...undiciOptions,
      dispatcher: this.dispatcher,
    });

    if (response.statusCode < 200 || response.statusCode >= 300) {
      const text = await response.body.text();
      throw new Error(`HTTP ${response.statusCode}: ${text}`);
    }

    yield* parseNdjsonStream<T>(response.body, this.config.serializer);
  }

  /**
   * Close the client
   */
  async close(): Promise<void> {
    this.closed = true;
    // Dispatcher cleanup is handled by the caller (fetch-proxy-dispatcher)
  }
}
