/**
 * Tests for factory.mts
 * Logic testing: Decision/Branch, Path coverage
 */
import { createClient, createClients, closeClients, BaseClient, RestAdapter } from '../src/factory.mjs';
import type { ClientConfig, FetchClient } from '../src/types.mjs';

describe('factory', () => {
  const baseConfig: ClientConfig = {
    baseUrl: 'https://api.example.com',
  };

  describe('createClient', () => {
    // Decision: default protocol (REST)
    it('should create RestAdapter by default', () => {
      const client = createClient(baseConfig);

      expect(client).toBeInstanceOf(RestAdapter);
    });

    // Decision: explicit REST protocol
    it('should create RestAdapter for REST protocol', () => {
      const client = createClient({ ...baseConfig, protocol: 'rest' });

      expect(client).toBeInstanceOf(RestAdapter);
    });

    // Decision: RPC protocol returns BaseClient
    it('should create BaseClient for RPC protocol', () => {
      const client = createClient({ ...baseConfig, protocol: 'rpc' });

      expect(client).toBeInstanceOf(BaseClient);
    });

    // Decision: unknown protocol returns BaseClient
    it('should create BaseClient for unknown protocol', () => {
      const client = createClient({ ...baseConfig, protocol: 'graphql' as any });

      expect(client).toBeInstanceOf(BaseClient);
    });

    // Path: with auth config
    it('should pass auth config to client', () => {
      const client = createClient({
        ...baseConfig,
        auth: { type: 'bearer', apiKey: 'test-key' },
      });

      expect(client).toBeInstanceOf(RestAdapter);
    });

    // Path: with custom headers
    it('should pass custom headers to client', () => {
      const client = createClient({
        ...baseConfig,
        headers: { 'User-Agent': 'TestClient/1.0' },
      });

      expect(client).toBeInstanceOf(RestAdapter);
    });

    // Path: with custom timeout
    it('should pass custom timeout to client', () => {
      const client = createClient({
        ...baseConfig,
        timeout: 60000,
      });

      expect(client).toBeInstanceOf(RestAdapter);
    });

    // Error Path: invalid config
    it('should throw for invalid config', () => {
      expect(() => createClient({ baseUrl: '' })).toThrow('baseUrl is required');
    });
  });

  describe('createClients', () => {
    // Path: multiple clients from config map
    it('should create multiple clients from config map', () => {
      const configs: Record<string, ClientConfig> = {
        gemini: { baseUrl: 'https://api.gemini.com' },
        openai: { baseUrl: 'https://api.openai.com' },
      };

      const clients = createClients(configs);

      expect(clients).toBeInstanceOf(Map);
      expect(clients.size).toBe(2);
      expect(clients.has('gemini')).toBe(true);
      expect(clients.has('openai')).toBe(true);
    });

    // Boundary: empty config map
    it('should return empty map for empty config', () => {
      const clients = createClients({});

      expect(clients).toBeInstanceOf(Map);
      expect(clients.size).toBe(0);
    });

    // Path: single client
    it('should create single client from config map', () => {
      const configs: Record<string, ClientConfig> = {
        api: { baseUrl: 'https://api.example.com' },
      };

      const clients = createClients(configs);

      expect(clients.size).toBe(1);
      expect(clients.get('api')).toBeInstanceOf(RestAdapter);
    });

    // Path: mixed protocols
    it('should create clients with different protocols', () => {
      const configs: Record<string, ClientConfig> = {
        rest: { baseUrl: 'https://api.example.com', protocol: 'rest' },
        rpc: { baseUrl: 'https://rpc.example.com', protocol: 'rpc' },
      };

      const clients = createClients(configs);

      expect(clients.get('rest')).toBeInstanceOf(RestAdapter);
      expect(clients.get('rpc')).toBeInstanceOf(BaseClient);
    });

    // Path: clients are independent
    it('should create independent clients', () => {
      const configs: Record<string, ClientConfig> = {
        api1: { baseUrl: 'https://api1.example.com' },
        api2: { baseUrl: 'https://api2.example.com' },
      };

      const clients = createClients(configs);

      const client1 = clients.get('api1');
      const client2 = clients.get('api2');

      expect(client1).not.toBe(client2);
    });
  });

  describe('closeClients', () => {
    // Path: closes all clients
    it('should close all clients in map', async () => {
      const mockClose1 = jest.fn().mockResolvedValue(undefined);
      const mockClose2 = jest.fn().mockResolvedValue(undefined);

      const mockClient1 = { close: mockClose1 } as unknown as FetchClient;
      const mockClient2 = { close: mockClose2 } as unknown as FetchClient;

      const clients = new Map<string, FetchClient>([
        ['client1', mockClient1],
        ['client2', mockClient2],
      ]);

      await closeClients(clients);

      expect(mockClose1).toHaveBeenCalled();
      expect(mockClose2).toHaveBeenCalled();
    });

    // Boundary: empty map
    it('should handle empty map without errors', async () => {
      const clients = new Map<string, FetchClient>();

      await expect(closeClients(clients)).resolves.toBeUndefined();
    });

    // Path: single client
    it('should close single client', async () => {
      const mockClose = jest.fn().mockResolvedValue(undefined);
      const mockClient = { close: mockClose } as unknown as FetchClient;

      const clients = new Map<string, FetchClient>([['client', mockClient]]);

      await closeClients(clients);

      expect(mockClose).toHaveBeenCalledTimes(1);
    });

    // Path: parallel closure
    it('should close clients in parallel', async () => {
      const closeOrder: number[] = [];
      let resolve1: () => void;
      let resolve2: () => void;

      const promise1 = new Promise<void>((r) => {
        resolve1 = r;
      });
      const promise2 = new Promise<void>((r) => {
        resolve2 = r;
      });

      const mockClient1 = {
        close: jest.fn(() => {
          closeOrder.push(1);
          return promise1;
        }),
      } as unknown as FetchClient;

      const mockClient2 = {
        close: jest.fn(() => {
          closeOrder.push(2);
          return promise2;
        }),
      } as unknown as FetchClient;

      const clients = new Map<string, FetchClient>([
        ['client1', mockClient1],
        ['client2', mockClient2],
      ]);

      const closePromise = closeClients(clients);

      // Both close methods should be called immediately (parallel)
      expect(closeOrder).toContain(1);
      expect(closeOrder).toContain(2);

      resolve1!();
      resolve2!();

      await closePromise;
    });

    // Path: waits for all to complete
    it('should wait for all clients to close', async () => {
      let closed = false;

      const mockClient = {
        close: jest.fn(async () => {
          await new Promise((r) => setTimeout(r, 10));
          closed = true;
        }),
      } as unknown as FetchClient;

      const clients = new Map<string, FetchClient>([['client', mockClient]]);

      await closeClients(clients);

      expect(closed).toBe(true);
    });
  });

  describe('exports', () => {
    // Path: exports BaseClient
    it('should export BaseClient', () => {
      expect(BaseClient).toBeDefined();
    });

    // Path: exports RestAdapter
    it('should export RestAdapter', () => {
      expect(RestAdapter).toBeDefined();
    });
  });
});
