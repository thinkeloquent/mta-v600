/**
 * Agent configurations for fetch-proxy-dispatcher
 * Provides pre-configured Agent and ProxyAgent instances
 */

import { Agent, ProxyAgent } from 'undici';
import { isDev } from './config.mjs';

/**
 * TLS options for development (disabled certificate validation)
 */
const devTlsOptions = {
  rejectUnauthorized: false,
};

/**
 * Create a DEV agent with TLS validation disabled
 * Use only in development environments
 */
export function createDevAgent(): Agent {
  return new Agent({
    connect: devTlsOptions,
    keepAliveTimeout: 60_000,
    keepAliveMaxTimeout: 60_000,
    connections: 1,
  });
}

/**
 * Create a "stay alive" agent with keep-alive enabled
 * Good for persistent connections and high-throughput scenarios
 */
export function createStayAliveAgent(): Agent {
  return new Agent({
    keepAliveTimeout: 30_000,
    keepAliveMaxTimeout: 60_000,
  });
}

/**
 * Create a "do not stay alive" agent
 * Connections close immediately after use
 * Good for one-off requests or debugging
 */
export function createDoNotStayAliveAgent(): Agent {
  return new Agent({
    keepAliveTimeout: 0,
    keepAliveMaxTimeout: 0,
    pipelining: 0,
  });
}

/**
 * Create a proxy agent with optional TLS options
 * @param proxyUrl - The proxy server URL
 * @param disableTls - Whether to disable TLS validation (default: based on isDev())
 */
export function createProxyAgent(proxyUrl: string, disableTls?: boolean): ProxyAgent {
  const shouldDisableTls = disableTls ?? isDev();

  return new ProxyAgent({
    uri: proxyUrl,
    ...(shouldDisableTls && {
      requestTls: devTlsOptions,
      proxyTls: devTlsOptions,
    }),
  });
}

/**
 * Default agents registry
 * Maps agent type names to factory functions
 */
export const defaultAgents = {
  DEV: createDevAgent,
  doNotStayAlive: createDoNotStayAliveAgent,
  stayAlive: createStayAliveAgent,
};

/**
 * Agent type names
 */
export type AgentType = keyof typeof defaultAgents;

export default {
  createDevAgent,
  createStayAliveAgent,
  createDoNotStayAliveAgent,
  createProxyAgent,
  defaultAgents,
};
