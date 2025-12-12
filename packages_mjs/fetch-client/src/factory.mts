/**
 * Client factory for @internal/fetch-client
 *
 * This module provides factory functions for creating HTTP clients.
 * For automatic proxy/dispatcher configuration, use createClientWithDispatcher.
 */
import type { Dispatcher } from 'undici';
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

/** Proxy config shape from server.*.yaml */
interface YamlProxyConfig {
  default_environment?: string;
  proxy_urls?: Record<string, string>;
  ca_bundle?: string | null;
  cert?: string | null;
  cert_verify?: boolean;
  agent_proxy?: {
    http_proxy?: string | null;
    https_proxy?: string | null;
  };
}

/**
 * Load proxy configuration from ConfigStore (server.*.yaml)
 * Returns the proxy section from the YAML config.
 */
async function getProxyConfigFromYaml(): Promise<YamlProxyConfig | null> {
  try {
    // Dynamic import to avoid TypeScript errors for optional peer dependency
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const configModule = await import('@internal/app-static-config-yaml' as any);
    const config = configModule.config;
    if (config && typeof config.getNested === 'function') {
      return config.getNested('network') || config.getNested('proxy') || null;
    }
    return null;
  } catch {
    return null;
  }
}

/** Options for getProxyDispatcherSafe */
interface ProxyDispatcherOptions {
  /** Override proxy URL (e.g., "http://proxy:8080"). Takes priority over YAML/env config. */
  proxy?: string;
  /** Override SSL verification. undefined uses YAML config. */
  verify?: boolean;
}

/**
 * Get proxy dispatcher from @internal/fetch-proxy-dispatcher
 * Configures based on YAML config from ConfigStore.
 * Runtime overrides take precedence over YAML config.
 * Returns undefined if the package is not available or no dispatcher is needed.
 */
async function getProxyDispatcherSafe(
  options: ProxyDispatcherOptions = {}
): Promise<Dispatcher | undefined> {
  try {
    const { ProxyDispatcherFactory } = await import('@internal/fetch-proxy-dispatcher');

    // Load proxy config from YAML (server.*.yaml)
    const yamlConfig = await getProxyConfigFromYaml();

    // Determine effective cert_verify (runtime override takes precedence)
    const effectiveCertVerify =
      options.verify !== undefined ? options.verify : yamlConfig?.cert_verify;

    // Build agent proxy config - explicit proxy parameter takes priority
    let agentProxyConfig:
      | { httpProxy?: string; httpsProxy?: string }
      | undefined;

    if (options.proxy) {
      // Explicit proxy override takes highest priority
      agentProxyConfig = {
        httpProxy: options.proxy,
        httpsProxy: options.proxy,
      };
    } else if (yamlConfig?.agent_proxy) {
      agentProxyConfig = {
        httpProxy: yamlConfig.agent_proxy.http_proxy || undefined,
        httpsProxy: yamlConfig.agent_proxy.https_proxy || undefined,
      };
    }

    if (yamlConfig || options.proxy !== undefined || options.verify !== undefined) {
      // Create factory with YAML configuration + overrides
      // Note: proxyUrls and defaultEnvironment support arbitrary environment names
      // (e.g., "dev", "Live", "STAGING", "Preview") - cast to bypass strict typing
      const factory = new ProxyDispatcherFactory({
        proxyUrls: yamlConfig?.proxy_urls as Record<string, string> | undefined,
        agentProxy: agentProxyConfig,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        defaultEnvironment: yamlConfig?.default_environment as any,
      });

      return factory.getProxyDispatcher({
        disableTls: effectiveCertVerify === false,
      });
    }

    // Fallback to simple API if no YAML config and no overrides
    const { getProxyDispatcher } = await import('@internal/fetch-proxy-dispatcher');
    return getProxyDispatcher();
  } catch {
    return undefined;
  }
}

/**
 * Extended client configuration with proxy override options.
 */
export interface ClientConfigWithProxy extends ClientConfig {
  /** Override proxy URL (e.g., "http://proxy:8080"). Takes priority over YAML/env config. */
  proxy?: string;
  /** Alias for proxy. Override proxy URL (e.g., "http://proxy:8080"). */
  proxyUrl?: string;
  /** Override SSL verification. undefined uses YAML config. */
  verify?: boolean;
}

/**
 * Create a fetch client with automatic proxy dispatcher configuration.
 *
 * Uses @internal/fetch-proxy-dispatcher to automatically configure
 * the appropriate dispatcher based on environment (DEV, QA, STAGE, PROD).
 *
 * Proxy configuration is loaded from server.*.yaml (via ConfigStore):
 * ```yaml
 * proxy:
 *   default_environment: "dev"
 *   proxy_urls:
 *     PROD: "http://proxy.company.com:8080"
 *     QA: "http://qa-proxy.company.com:8080"
 *   cert_verify: false
 *   agent_proxy:
 *     http_proxy: null
 *     https_proxy: null
 * ```
 *
 * @param config - Client configuration (dispatcher will be auto-configured if not provided)
 * @returns Promise<FetchClient> instance
 *
 * @example
 * ```typescript
 * // Dispatcher is automatically configured based on YAML config
 * const client = await createClientWithDispatcher({
 *   baseUrl: 'https://api.example.com',
 *   auth: {
 *     type: 'bearer',
 *     apiKey: process.env.API_KEY,
 *   },
 * });
 *
 * const response = await client.get('/users');
 *
 * // With explicit proxy override
 * const client2 = await createClientWithDispatcher({
 *   baseUrl: 'https://api.example.com',
 *   proxyUrl: 'http://proxy.company.com:8080',
 *   verify: false,
 * });
 * ```
 */
export async function createClientWithDispatcher(
  config: ClientConfigWithProxy
): Promise<FetchClient> {
  // Extract proxy options from config
  const { proxy, proxyUrl, verify, ...clientConfig } = config;

  // Only auto-configure dispatcher if not already provided
  if (!clientConfig.dispatcher) {
    // proxyUrl is alias for proxy, proxy takes precedence if both provided (though unlikely)
    const effectiveProxy = proxy || proxyUrl;
    const dispatcher = await getProxyDispatcherSafe({ proxy: effectiveProxy, verify });
    if (dispatcher) {
      clientConfig.dispatcher = dispatcher;
    }
  }

  return createClient(clientConfig);
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
