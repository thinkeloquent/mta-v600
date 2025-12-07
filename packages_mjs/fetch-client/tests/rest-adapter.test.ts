/**
 * Tests for rest-adapter.mts
 * Logic testing: Path coverage for delegation pattern
 */
import { RestAdapter } from '../src/adapters/rest-adapter.mjs';
import type { FetchClient, FetchResponse, SSEEvent, StreamOptions } from '../src/types.mjs';

describe('rest-adapter', () => {
  const createMockClient = (): jest.Mocked<FetchClient> => ({
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    request: jest.fn(),
    stream: jest.fn(),
    streamNdjson: jest.fn(),
    close: jest.fn(),
  });

  const mockResponse: FetchResponse<unknown> = {
    status: 200,
    statusText: 'OK',
    headers: {},
    data: { success: true },
    ok: true,
  };

  describe('constructor', () => {
    // Path: wraps client
    it('should wrap the provided client', () => {
      const mockClient = createMockClient();
      const adapter = new RestAdapter(mockClient);
      expect(adapter).toBeDefined();
    });
  });

  describe('get', () => {
    // Path: delegates to client.get
    it('should delegate to client.get', async () => {
      const mockClient = createMockClient();
      mockClient.get.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);

      const result = await adapter.get('/users');

      expect(mockClient.get).toHaveBeenCalledWith('/users', {});
      expect(result).toBe(mockResponse);
    });

    // Path: passes options
    it('should pass options to client.get', async () => {
      const mockClient = createMockClient();
      mockClient.get.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);
      const options = { query: { page: 1 }, headers: { 'X-Custom': 'value' } };

      await adapter.get('/users', options);

      expect(mockClient.get).toHaveBeenCalledWith('/users', options);
    });

    // Path: default empty options
    it('should use empty object as default options', async () => {
      const mockClient = createMockClient();
      mockClient.get.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);

      await adapter.get('/users');

      expect(mockClient.get).toHaveBeenCalledWith('/users', {});
    });
  });

  describe('post', () => {
    // Path: delegates to client.post
    it('should delegate to client.post', async () => {
      const mockClient = createMockClient();
      mockClient.post.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);

      const result = await adapter.post('/users', { json: { name: 'test' } });

      expect(mockClient.post).toHaveBeenCalledWith('/users', { json: { name: 'test' } });
      expect(result).toBe(mockResponse);
    });
  });

  describe('put', () => {
    // Path: delegates to client.put
    it('should delegate to client.put', async () => {
      const mockClient = createMockClient();
      mockClient.put.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);

      const result = await adapter.put('/users/1', { json: { name: 'updated' } });

      expect(mockClient.put).toHaveBeenCalledWith('/users/1', { json: { name: 'updated' } });
      expect(result).toBe(mockResponse);
    });
  });

  describe('patch', () => {
    // Path: delegates to client.patch
    it('should delegate to client.patch', async () => {
      const mockClient = createMockClient();
      mockClient.patch.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);

      const result = await adapter.patch('/users/1', { json: { name: 'patched' } });

      expect(mockClient.patch).toHaveBeenCalledWith('/users/1', { json: { name: 'patched' } });
      expect(result).toBe(mockResponse);
    });
  });

  describe('delete', () => {
    // Path: delegates to client.delete
    it('should delegate to client.delete', async () => {
      const mockClient = createMockClient();
      mockClient.delete.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);

      const result = await adapter.delete('/users/1');

      expect(mockClient.delete).toHaveBeenCalledWith('/users/1', {});
      expect(result).toBe(mockResponse);
    });
  });

  describe('request', () => {
    // Path: delegates to client.request
    it('should delegate to client.request', async () => {
      const mockClient = createMockClient();
      mockClient.request.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);

      const result = await adapter.request({ path: '/users', method: 'GET' });

      expect(mockClient.request).toHaveBeenCalledWith({ path: '/users', method: 'GET' });
      expect(result).toBe(mockResponse);
    });

    // Path: with all options
    it('should pass all options to client.request', async () => {
      const mockClient = createMockClient();
      mockClient.request.mockResolvedValue(mockResponse);
      const adapter = new RestAdapter(mockClient);
      const options = {
        path: '/users',
        method: 'POST' as const,
        json: { data: 'test' },
        query: { active: true },
        headers: { 'Content-Type': 'application/json' },
        timeout: 5000,
      };

      await adapter.request(options);

      expect(mockClient.request).toHaveBeenCalledWith(options);
    });
  });

  describe('stream', () => {
    // Path: delegates to client.stream
    it('should delegate to client.stream', () => {
      const mockClient = createMockClient();
      const mockGenerator = (async function* () {
        yield { data: 'test' };
      })();
      mockClient.stream.mockReturnValue(mockGenerator);
      const adapter = new RestAdapter(mockClient);

      const result = adapter.stream('/events');

      expect(mockClient.stream).toHaveBeenCalledWith('/events', undefined);
      expect(result).toBe(mockGenerator);
    });

    // Path: with options
    it('should pass options to client.stream', () => {
      const mockClient = createMockClient();
      const mockGenerator = (async function* () {})();
      mockClient.stream.mockReturnValue(mockGenerator);
      const adapter = new RestAdapter(mockClient);
      const options: StreamOptions = { method: 'POST', json: { prompt: 'test' } };

      adapter.stream('/events', options);

      expect(mockClient.stream).toHaveBeenCalledWith('/events', options);
    });
  });

  describe('streamNdjson', () => {
    // Path: delegates to client.streamNdjson
    it('should delegate to client.streamNdjson', () => {
      const mockClient = createMockClient();
      const mockGenerator = (async function* () {
        yield { id: 1 };
      })();
      mockClient.streamNdjson.mockReturnValue(mockGenerator);
      const adapter = new RestAdapter(mockClient);

      const result = adapter.streamNdjson('/data');

      expect(mockClient.streamNdjson).toHaveBeenCalledWith('/data', undefined);
      expect(result).toBe(mockGenerator);
    });

    // Path: with options
    it('should pass options to client.streamNdjson', () => {
      const mockClient = createMockClient();
      const mockGenerator = (async function* () {})();
      mockClient.streamNdjson.mockReturnValue(mockGenerator);
      const adapter = new RestAdapter(mockClient);
      const options: StreamOptions = { query: { limit: 100 } };

      adapter.streamNdjson('/data', options);

      expect(mockClient.streamNdjson).toHaveBeenCalledWith('/data', options);
    });
  });

  describe('close', () => {
    // Path: delegates to client.close
    it('should delegate to client.close', async () => {
      const mockClient = createMockClient();
      mockClient.close.mockResolvedValue(undefined);
      const adapter = new RestAdapter(mockClient);

      await adapter.close();

      expect(mockClient.close).toHaveBeenCalled();
    });

    // Path: returns promise from client.close
    it('should return promise from client.close', async () => {
      const mockClient = createMockClient();
      mockClient.close.mockResolvedValue(undefined);
      const adapter = new RestAdapter(mockClient);

      const result = adapter.close();

      expect(result).toBeInstanceOf(Promise);
      await expect(result).resolves.toBeUndefined();
    });
  });
});
