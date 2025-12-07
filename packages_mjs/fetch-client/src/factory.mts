/**
 * Client factory for @internal/fetch-client
 */
import type { ClientConfig, FetchClient } from './types.mjs';
import { BaseClient } from './core/base-client.mjs';
import { RestAdapter } from './adapters/rest-adapter.mjs';

/**
 * Create a fetch client with the given configuration
 *
 * @param config - Client configuration
 * @returns FetchClient instance
 *
 * @example
 * ```typescript
 * const client = createClient({
 *   baseUrl: 'https://api.example.com',
 *   dispatcher,
 *   auth: {
 *     type: 'bearer',
 *     apiKey: process.env.API_KEY,
 *   },
 * });
 *
 * const response = await client.get('/users');
 * ```
 */
export function createClient(config: ClientConfig): FetchClient {
  const baseClient = new BaseClient(config);

  // Default to REST adapter
  if (!config.protocol || config.protocol === 'rest') {
    return new RestAdapter(baseClient);
  }

  // For RPC or other protocols, return base client directly
  return baseClient;
}

/**
 * Create multiple clients from config map
 *
 * @param configs - Map of service name to config
 * @returns Map of service name to client
 *
 * @example
 * ```typescript
 * const clients = createClients({
 *   gemini: { baseUrl: 'https://api.gemini.com', ... },
 *   openai: { baseUrl: 'https://api.openai.com', ... },
 * });
 *
 * const gemini = clients.get('gemini');
 * ```
 */
export function createClients(
  configs: Record<string, ClientConfig>
): Map<string, FetchClient> {
  const clients = new Map<string, FetchClient>();

  for (const [name, config] of Object.entries(configs)) {
    clients.set(name, createClient(config));
  }

  return clients;
}

/**
 * Close all clients in a map
 */
export async function closeClients(
  clients: Map<string, FetchClient>
): Promise<void> {
  const promises = Array.from(clients.values()).map((client) => client.close());
  await Promise.all(promises);
}

export { BaseClient } from './core/base-client.mjs';
export { RestAdapter } from './adapters/rest-adapter.mjs';
