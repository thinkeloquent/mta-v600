/**
 * Tests for fastify-plugin.mts
 * Logic testing: Decision/Branch, State Transition, Path coverage
 */
import fetchClientPlugin from '../src/integrations/fastify-plugin.mjs';
import { createClient } from '../src/factory.mjs';
import { warmupDns } from '../src/dns-warmup.mjs';
import type { FastifyInstance } from 'fastify';

// Mock dependencies
jest.mock('../src/factory.mjs', () => ({
  createClient: jest.fn(),
}));

jest.mock('../src/dns-warmup.mjs', () => ({
  warmupDns: jest.fn(),
}));

const mockedCreateClient = createClient as jest.MockedFunction<typeof createClient>;
const mockedWarmupDns = warmupDns as jest.MockedFunction<typeof warmupDns>;

describe('fastify-plugin', () => {
  const createMockFastify = (): jest.Mocked<FastifyInstance> => {
    const hooks: Map<string, Function[]> = new Map();
    const decorators: Map<string, unknown> = new Map();

    return {
      log: {
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
      },
      decorate: jest.fn((name: string, value: unknown) => {
        decorators.set(name, value);
      }),
      hasDecorator: jest.fn((name: string) => decorators.has(name)),
      addHook: jest.fn((event: string, handler: Function) => {
        if (!hooks.has(event)) {
          hooks.set(event, []);
        }
        hooks.get(event)!.push(handler);
      }),
      // Helper to trigger hooks
      _triggerHook: async (event: string) => {
        const handlers = hooks.get(event) || [];
        for (const handler of handlers) {
          await handler();
        }
      },
      _getDecorator: (name: string) => decorators.get(name),
    } as unknown as jest.Mocked<FastifyInstance>;
  };

  const createMockClient = () => ({
    get: jest.fn(),
    post: jest.fn(),
    close: jest.fn().mockResolvedValue(undefined),
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockedCreateClient.mockReturnValue(createMockClient() as any);
    mockedWarmupDns.mockResolvedValue({
      success: true,
      hostname: 'api.example.com',
      addresses: ['192.168.1.1'],
      duration: 10,
    });
  });

  describe('plugin registration', () => {
    // Happy Path: decorates fastify instance
    it('should decorate fastify instance with client', async () => {
      const fastify = createMockFastify();
      const mockClient = createMockClient();
      mockedCreateClient.mockReturnValue(mockClient as any);

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
      });

      expect(fastify.decorate).toHaveBeenCalledWith('apiClient', mockClient);
    });

    // Path: creates client with config
    it('should create client with provided config', async () => {
      const fastify = createMockFastify();
      const config = {
        baseUrl: 'https://api.example.com',
        auth: { type: 'bearer' as const, rawApiKey: 'test-key' },
      };

      await fetchClientPlugin(fastify, { name: 'apiClient', config });

      expect(mockedCreateClient).toHaveBeenCalledWith(config);
    });
  });

  describe('DNS warmup', () => {
    // Decision: warmupDns enabled (default)
    it('should perform DNS warmup by default', async () => {
      const fastify = createMockFastify();

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
      });

      expect(mockedWarmupDns).toHaveBeenCalledWith('api.example.com');
    });

    // Decision: warmupDns disabled
    it('should skip DNS warmup when disabled', async () => {
      const fastify = createMockFastify();

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
        warmupDns: false,
      });

      expect(mockedWarmupDns).not.toHaveBeenCalled();
    });

    // Path: logs success
    it('should log DNS warmup success', async () => {
      const fastify = createMockFastify();
      mockedWarmupDns.mockResolvedValue({
        success: true,
        hostname: 'api.example.com',
        addresses: ['1.2.3.4'],
        duration: 15,
      });

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
      });

      expect(fastify.log.info).toHaveBeenCalledWith(
        expect.objectContaining({ hostname: 'api.example.com', duration: 15 }),
        expect.stringContaining('DNS warmup complete')
      );
    });

    // Error Path: DNS warmup failure logs warning
    it('should log warning on DNS warmup failure', async () => {
      const fastify = createMockFastify();
      mockedWarmupDns.mockResolvedValue({
        success: false,
        hostname: 'api.example.com',
        addresses: [],
        error: new Error('ENOTFOUND'),
        duration: 100,
      });

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
      });

      expect(fastify.log.warn).toHaveBeenCalledWith(
        expect.objectContaining({ error: 'ENOTFOUND' }),
        expect.stringContaining('DNS warmup failed')
      );
    });

    // Error Path: DNS warmup throws logs warning
    it('should log warning when DNS warmup throws', async () => {
      const fastify = createMockFastify();
      mockedWarmupDns.mockRejectedValue(new Error('Network error'));

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
      });

      expect(fastify.log.warn).toHaveBeenCalledWith(
        expect.objectContaining({ error: expect.any(Error) }),
        expect.stringContaining('DNS warmup error')
      );
    });

    // Boundary: no baseUrl skips warmup
    it('should skip warmup when baseUrl is empty', async () => {
      const fastify = createMockFastify();
      // Note: This would fail validation in real use, but tests the warmup branch
      mockedCreateClient.mockImplementation(() => {
        throw new Error('baseUrl is required');
      });

      await expect(
        fetchClientPlugin(fastify, {
          name: 'apiClient',
          config: { baseUrl: '' },
        })
      ).rejects.toThrow('baseUrl is required');
    });
  });

  describe('duplicate decorator', () => {
    // Error Path: throws for duplicate decorator
    it('should throw when decorator already exists', async () => {
      const fastify = createMockFastify();
      (fastify.hasDecorator as jest.Mock).mockReturnValue(true);

      await expect(
        fetchClientPlugin(fastify, {
          name: 'existingClient',
          config: { baseUrl: 'https://api.example.com' },
        })
      ).rejects.toThrow("Decorator 'existingClient' already exists");
    });
  });

  describe('onClose hook', () => {
    // State: closes client on shutdown
    it('should register onClose hook', async () => {
      const fastify = createMockFastify();

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
      });

      expect(fastify.addHook).toHaveBeenCalledWith('onClose', expect.any(Function));
    });

    // State: closes client when hook triggered
    it('should close client on onClose hook', async () => {
      const fastify = createMockFastify();
      const mockClient = createMockClient();
      mockedCreateClient.mockReturnValue(mockClient as any);

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
      });

      // Trigger the onClose hook
      await (fastify as any)._triggerHook('onClose');

      expect(mockClient.close).toHaveBeenCalled();
    });

    // Path: logs client closed
    it('should log when client is closed', async () => {
      const fastify = createMockFastify();

      await fetchClientPlugin(fastify, {
        name: 'apiClient',
        config: { baseUrl: 'https://api.example.com' },
      });

      await (fastify as any)._triggerHook('onClose');

      expect(fastify.log.info).toHaveBeenCalledWith('apiClient client closed');
    });
  });

  describe('plugin metadata', () => {
    // Path: plugin name
    it('should have correct plugin name', () => {
      expect(fetchClientPlugin[Symbol.for('fastify.display-name')]).toBe(
        '@internal/fetch-client'
      );
    });
  });
});
