/**
 * Request builder utilities for @internal/fetch-client
 */
import type { Dispatcher } from 'undici';
import type {
  HttpMethod,
  RequestOptions,
  RequestContext,
  AuthConfig,
} from '../types.mjs';
import type { ResolvedConfig } from '../config.mjs';
import {
  getAuthHeaderName,
  formatAuthHeaderValue,
} from '../config.mjs';

/**
 * Build full URL from base and path
 */
export function buildUrl(
  baseUrl: URL,
  path: string,
  query?: Record<string, string | number | boolean>
): string {
  const url = new URL(path, baseUrl);

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      url.searchParams.set(key, String(value));
    }
  }

  return url.toString();
}

/**
 * Build request headers
 */
export function buildHeaders(
  config: ResolvedConfig,
  options: RequestOptions,
  context: RequestContext
): Record<string, string> {
  const headers: Record<string, string> = {
    ...config.headers,
    ...options.headers,
  };

  // Set content-type for requests with body
  if (options.json !== undefined || options.body !== undefined) {
    headers['content-type'] = headers['content-type'] || config.contentType;
  }

  // Set accept header if not specified
  if (!headers['accept']) {
    headers['accept'] = 'application/json';
  }

  // Apply auth header
  if (config.auth) {
    const authHeader = resolveAuthHeader(config.auth, context);
    if (authHeader) {
      Object.assign(headers, authHeader);
    }
  }

  return headers;
}

/**
 * Resolve auth header from config and context
 */
export function resolveAuthHeader(
  auth: AuthConfig,
  context: RequestContext
): Record<string, string> | null {
  let apiKey: string | undefined;

  // Try dynamic callback first
  if (auth.getApiKeyForRequest) {
    apiKey = auth.getApiKeyForRequest(context);
  }

  // Fall back to static key
  if (!apiKey) {
    apiKey = auth.apiKey;
  }

  if (!apiKey) {
    return null;
  }

  const headerName = getAuthHeaderName(auth);
  const headerValue = formatAuthHeaderValue(auth, apiKey);

  return { [headerName]: headerValue };
}

/**
 * Build request body
 */
export function buildBody(
  options: RequestOptions,
  serializer: { serialize: (data: unknown) => string }
): string | Buffer | undefined {
  if (options.body !== undefined) {
    if (typeof options.body === 'string' || Buffer.isBuffer(options.body)) {
      return options.body;
    }
    // ReadableStream is not directly supported - skip
    return undefined;
  }

  if (options.json !== undefined) {
    return serializer.serialize(options.json);
  }

  return undefined;
}

/**
 * Undici request options
 */
export interface UndiciRequestOptions {
  method: Dispatcher.HttpMethod;
  headers: Record<string, string>;
  body?: string | Buffer | undefined;
  signal?: AbortSignal;
  bodyTimeout?: number;
  headersTimeout?: number;
}

/**
 * Build undici request options
 */
export function buildUndiciOptions(
  config: ResolvedConfig,
  options: RequestOptions & { path: string },
  context: RequestContext
): UndiciRequestOptions {
  const method = options.method || 'GET';
  const headers = buildHeaders(config, options, context);
  const body = buildBody(options, config.serializer);

  const undiciOptions: UndiciRequestOptions = {
    method,
    headers,
    body,
    bodyTimeout: options.timeout || config.timeout.read,
    headersTimeout: config.timeout.connect,
  };

  return undiciOptions;
}

/**
 * Create request context from options
 */
export function createRequestContext(
  method: HttpMethod,
  path: string,
  options: RequestOptions
): RequestContext {
  return {
    method,
    path,
    headers: options.headers,
    json: options.json,
  };
}
