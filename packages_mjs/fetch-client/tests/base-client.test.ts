/**
 * Tests for base-client.mts
 * Logic testing: Decision/Branch, State Transition, Path coverage
 */
import { BaseClient } from '../src/core/base-client.mjs';
import type { ClientConfig, FetchResponse, SSEEvent } from '../src/types.mjs';
import { request } from 'undici';

// Mock undici request
jest.mock('undici', () => ({
  request: jest.fn(),
}));

// Mock streaming parsers
jest.mock('../src/streaming/sse-reader.mjs', () => ({
  parseSSEStream: jest.fn(),
}));

jest.mock('../src/streaming/ndjson-reader.mjs', () => ({
  parseNdjsonStream: jest.fn(),
}));

import { parseSSEStream } from '../src/streaming/sse-reader.mjs';
import { parseNdjsonStream } from '../src/streaming/ndjson-reader.mjs';

const mockedRequest = request as jest.MockedFunction<typeof request>;
const mockedParseSSEStream = parseSSEStream as jest.MockedFunction<typeof parseSSEStream>;
const mockedParseNdjsonStream = parseNdjsonStream as jest.MockedFunction<typeof parseNdjsonStream>;

describe('base-client', () => {
  const baseConfig: ClientConfig = {
    baseUrl: 'https://api.example.com',
  };

  const createMockResponse = (
    statusCode: number,
    body: string | object,
    headers: Record<string, string> = {}
  ) => ({
    statusCode,
    headers,
    body: {
      text: jest.fn().mockResolvedValue(typeof body === 'string' ? body : JSON.stringify(body)),
    },
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('constructor', () => {
    // Path: config resolution
    it('should resolve config on construction', () => {
      const client = new BaseClient(baseConfig);
      expect(client).toBeDefined();
    });

    // Path: with dispatcher
    it('should accept custom dispatcher', () => {
      const dispatcher = {} as any;
      const client = new BaseClient({ ...baseConfig, dispatcher });
      expect(client).toBeDefined();
    });

    // Error Path: invalid config
    it('should throw for invalid config', () => {
      expect(() => new BaseClient({ baseUrl: '' })).toThrow('baseUrl is required');
    });
  });

  describe('request', () => {
    // Happy Path: GET success
    it('should make GET request and return FetchResponse', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, { name: 'test' });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/users', method: 'GET' });

      expect(result.status).toBe(200);
      expect(result.ok).toBe(true);
      expect(result.data).toEqual({ name: 'test' });
    });

    // Path: POST with json body
    it('should serialize json body for POST', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(201, { id: 1 });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({
        path: '/users',
        method: 'POST',
        json: { name: 'test' },
      });

      expect(result.status).toBe(201);
      expect(mockedRequest).toHaveBeenCalledWith(
        expect.stringContaining('/users'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'test' }),
        })
      );
    });

    // Path: PUT method
    it('should handle PUT method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, { updated: true });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({
        path: '/users/1',
        method: 'PUT',
        json: { name: 'updated' },
      });

      expect(result.ok).toBe(true);
      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'PUT' })
      );
    });

    // Path: PATCH method
    it('should handle PATCH method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, { patched: true });
      mockedRequest.mockResolvedValue(mockResponse as any);

      await client.request({
        path: '/users/1',
        method: 'PATCH',
        json: { name: 'patched' },
      });

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'PATCH' })
      );
    });

    // Path: DELETE method
    it('should handle DELETE method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(204, '');
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({
        path: '/users/1',
        method: 'DELETE',
      });

      expect(result.status).toBe(204);
      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    // State: request on closed client
    it('should throw when client is closed', async () => {
      const client = new BaseClient(baseConfig);
      await client.close();

      await expect(client.request({ path: '/users' })).rejects.toThrow(
        'Client has been closed'
      );
    });

    // Decision: 404 response
    it('should handle 404 response with ok=false', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(404, { error: 'Not found' });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/users/999' });

      expect(result.status).toBe(404);
      expect(result.ok).toBe(false);
    });

    // Decision: 500 response
    it('should handle 500 response with ok=false', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(500, { error: 'Server error' });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/users' });

      expect(result.status).toBe(500);
      expect(result.ok).toBe(false);
    });

    // Boundary: 200 is ok
    it('should return ok=true for 200', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/users' });
      expect(result.ok).toBe(true);
    });

    // Boundary: 299 is ok
    it('should return ok=true for 299', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(299, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/users' });
      expect(result.ok).toBe(true);
    });

    // Boundary: 300 is not ok
    it('should return ok=false for 300', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(300, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/users' });
      expect(result.ok).toBe(false);
    });

    // Path: JSON parse success
    it('should deserialize JSON response', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, { nested: { value: 123 } });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/data' });

      expect(result.data).toEqual({ nested: { value: 123 } });
    });

    // Error Path: JSON parse failure falls back to text
    it('should fallback to text when JSON parse fails', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 200,
        headers: {},
        body: {
          text: jest.fn().mockResolvedValue('plain text response'),
        },
      };
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/text' });

      expect(result.data).toBe('plain text response');
    });

    // Path: header normalization - string
    it('should handle string headers', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {}, {
        'content-type': 'application/json',
      });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/users' });

      expect(result.headers['content-type']).toBe('application/json');
    });

    // Path: header normalization - array to string
    it('should join array headers with comma', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 200,
        headers: {
          'set-cookie': ['cookie1=value1', 'cookie2=value2'],
        },
        body: {
          text: jest.fn().mockResolvedValue('{}'),
        },
      };
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.request({ path: '/users' });

      expect(result.headers['set-cookie']).toBe('cookie1=value1, cookie2=value2');
    });

    // Path: custom timeout override
    it('should apply custom timeout', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      await client.request({ path: '/users', timeout: 60000 });

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ bodyTimeout: 60000 })
      );
    });

    // Path: query params
    it('should add query params to URL', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      await client.request({ path: '/users', query: { page: 1, limit: 10 } });

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.stringContaining('page=1'),
        expect.any(Object)
      );
    });

    // Path: default method is GET
    it('should default to GET method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      await client.request({ path: '/users' });

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'GET' })
      );
    });
  });

  describe('get', () => {
    // Path: delegation to request
    it('should delegate to request with GET method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, { users: [] });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.get('/users');

      expect(result.data).toEqual({ users: [] });
      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'GET' })
      );
    });

    // Path: with options
    it('should pass options to request', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      await client.get('/users', { query: { active: true } });

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.stringContaining('active=true'),
        expect.any(Object)
      );
    });
  });

  describe('post', () => {
    // Path: delegation to request
    it('should delegate to request with POST method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(201, { id: 1 });
      mockedRequest.mockResolvedValue(mockResponse as any);

      const result = await client.post('/users', { json: { name: 'test' } });

      expect(result.status).toBe(201);
      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  describe('put', () => {
    // Path: delegation to request
    it('should delegate to request with PUT method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      await client.put('/users/1', { json: { name: 'updated' } });

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'PUT' })
      );
    });
  });

  describe('patch', () => {
    // Path: delegation to request
    it('should delegate to request with PATCH method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      await client.patch('/users/1', { json: { name: 'patched' } });

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'PATCH' })
      );
    });
  });

  describe('delete', () => {
    // Path: delegation to request
    it('should delegate to request with DELETE method', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(204, '');
      mockedRequest.mockResolvedValue(mockResponse as any);

      await client.delete('/users/1');

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('stream', () => {
    // Happy Path: yields SSE events
    it('should yield SSE events from stream', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 200,
        body: {},
      };
      mockedRequest.mockResolvedValue(mockResponse as any);

      const mockEvents: SSEEvent[] = [
        { data: 'event1' },
        { data: 'event2' },
      ];
      mockedParseSSEStream.mockImplementation(async function* () {
        for (const event of mockEvents) {
          yield event;
        }
      });

      const events: SSEEvent[] = [];
      for await (const event of client.stream('/events')) {
        events.push(event);
      }

      expect(events).toEqual(mockEvents);
    });

    // State: stream on closed client
    it('should throw when client is closed', async () => {
      const client = new BaseClient(baseConfig);
      await client.close();

      const generator = client.stream('/events');
      await expect(generator.next()).rejects.toThrow('Client has been closed');
    });

    // Error Path: non-2xx response
    it('should throw for non-2xx response', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 500,
        body: {
          text: jest.fn().mockResolvedValue('Internal Server Error'),
        },
      };
      mockedRequest.mockResolvedValue(mockResponse as any);

      const generator = client.stream('/events');
      await expect(generator.next()).rejects.toThrow('HTTP 500: Internal Server Error');
    });

    // Path: sets accept header
    it('should set accept header to text/event-stream', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 200,
        body: {},
      };
      mockedRequest.mockResolvedValue(mockResponse as any);
      mockedParseSSEStream.mockImplementation(async function* () {});

      const generator = client.stream('/events');
      await generator.next();

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            accept: 'text/event-stream',
          }),
        })
      );
    });

    // Path: default method is POST
    it('should default to POST method for stream', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 200,
        body: {},
      };
      mockedRequest.mockResolvedValue(mockResponse as any);
      mockedParseSSEStream.mockImplementation(async function* () {});

      const generator = client.stream('/events');
      await generator.next();

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  describe('streamNdjson', () => {
    // Happy Path: yields parsed objects
    it('should yield parsed NDJSON objects', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 200,
        body: {},
      };
      mockedRequest.mockResolvedValue(mockResponse as any);

      const mockObjects = [{ id: 1 }, { id: 2 }, { id: 3 }];
      mockedParseNdjsonStream.mockImplementation(async function* () {
        for (const obj of mockObjects) {
          yield obj;
        }
      });

      const objects: unknown[] = [];
      for await (const obj of client.streamNdjson('/data')) {
        objects.push(obj);
      }

      expect(objects).toEqual(mockObjects);
    });

    // State: streamNdjson on closed client
    it('should throw when client is closed', async () => {
      const client = new BaseClient(baseConfig);
      await client.close();

      const generator = client.streamNdjson('/data');
      await expect(generator.next()).rejects.toThrow('Client has been closed');
    });

    // Error Path: non-2xx response
    it('should throw for non-2xx response', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 404,
        body: {
          text: jest.fn().mockResolvedValue('Not Found'),
        },
      };
      mockedRequest.mockResolvedValue(mockResponse as any);

      const generator = client.streamNdjson('/data');
      await expect(generator.next()).rejects.toThrow('HTTP 404: Not Found');
    });

    // Path: sets accept header
    it('should set accept header to application/x-ndjson', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 200,
        body: {},
      };
      mockedRequest.mockResolvedValue(mockResponse as any);
      mockedParseNdjsonStream.mockImplementation(async function* () {});

      const generator = client.streamNdjson('/data');
      await generator.next();

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            accept: 'application/x-ndjson',
          }),
        })
      );
    });

    // Path: default method is GET
    it('should default to GET method for streamNdjson', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = {
        statusCode: 200,
        body: {},
      };
      mockedRequest.mockResolvedValue(mockResponse as any);
      mockedParseNdjsonStream.mockImplementation(async function* () {});

      const generator = client.streamNdjson('/data');
      await generator.next();

      expect(mockedRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'GET' })
      );
    });
  });

  describe('close', () => {
    // State: sets closed flag
    it('should set closed flag', async () => {
      const client = new BaseClient(baseConfig);
      await client.close();

      await expect(client.request({ path: '/users' })).rejects.toThrow(
        'Client has been closed'
      );
    });

    // State: prevents further requests
    it('should prevent further requests after close', async () => {
      const client = new BaseClient(baseConfig);
      const mockResponse = createMockResponse(200, {});
      mockedRequest.mockResolvedValue(mockResponse as any);

      // First request should work
      await client.request({ path: '/users' });

      // Close the client
      await client.close();

      // Second request should fail
      await expect(client.request({ path: '/users' })).rejects.toThrow(
        'Client has been closed'
      );
    });

    // Path: close is idempotent
    it('should be idempotent', async () => {
      const client = new BaseClient(baseConfig);

      await client.close();
      await client.close();

      await expect(client.request({ path: '/users' })).rejects.toThrow(
        'Client has been closed'
      );
    });
  });
});
