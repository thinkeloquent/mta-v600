/**
 * REST adapter for @internal/fetch-client
 *
 * Provides REST-style HTTP methods on top of the base client.
 */
import type {
  FetchClient,
  RequestOptions,
  FetchResponse,
  SSEEvent,
  StreamOptions,
} from '../types.mjs';

/**
 * REST adapter wrapping a fetch client
 *
 * This is the main adapter for REST-style API calls.
 * For RPC-style calls, use rpc-adapter.mts
 */
export class RestAdapter implements FetchClient {
  constructor(private client: FetchClient) {}

  /**
   * GET request
   */
  async get<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.client.get<T>(path, options);
  }

  /**
   * POST request
   */
  async post<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.client.post<T>(path, options);
  }

  /**
   * PUT request
   */
  async put<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.client.put<T>(path, options);
  }

  /**
   * PATCH request
   */
  async patch<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.client.patch<T>(path, options);
  }

  /**
   * DELETE request
   */
  async delete<T = unknown>(
    path: string,
    options: RequestOptions = {}
  ): Promise<FetchResponse<T>> {
    return this.client.delete<T>(path, options);
  }

  /**
   * Generic request
   */
  async request<T = unknown>(
    options: RequestOptions & { path: string }
  ): Promise<FetchResponse<T>> {
    return this.client.request<T>(options);
  }

  /**
   * Stream SSE response
   */
  stream(
    path: string,
    options?: StreamOptions
  ): AsyncGenerator<SSEEvent, void, unknown> {
    return this.client.stream(path, options);
  }

  /**
   * Stream NDJSON response
   */
  streamNdjson<T = unknown>(
    path: string,
    options?: StreamOptions
  ): AsyncGenerator<T, void, unknown> {
    return this.client.streamNdjson<T>(path, options);
  }

  /**
   * Close the client
   */
  async close(): Promise<void> {
    return this.client.close();
  }
}
