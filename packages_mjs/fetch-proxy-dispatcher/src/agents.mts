/**
 * Agent configurations for fetch-proxy-dispatcher
 * Provides pre-configured Agent and ProxyAgent instances
 */

import process from 'node:process';
import { Agent, ProxyAgent } from 'undici';
import { isDev, isSslVerifyDisabledByEnv } from './config.mjs';

/**
 * Simple logger for agents module
 * Logging is ENABLED by default. Disable with DEBUG=false or DEBUG=0
 */
const isDebugEnabled = (): boolean => {
  const debug = process.env['DEBUG']?.toLowerCase() || '';
  // Disable only if explicitly set to false/0
  if (debug === 'false' || debug === '0') {
    return false;
  }
  return true; // Enabled by default
};

const log = {
  debug: (message: string) => {
    if (isDebugEnabled()) {
      console.log(`[fetch-proxy-dispatcher.agents] ${message}`);
    }
  },
};

/**
 * Mask proxy URL for safe logging
 */
function maskProxyUrl(url: string | undefined): string {
  if (!url) return 'undefined';
  if (url.includes('@')) {
    const protocolEnd = url.indexOf('://');
    if (protocolEnd !== -1) {
      const atPos = url.indexOf('@');
      return `${url.slice(0, protocolEnd + 3)}***@${url.slice(atPos + 1)}`;
    }
  }
  return url;
}

/**
 * TLS options for development (disabled certificate validation)
 */
const devTlsOptions = {
  rejectUnauthorized: false,
};

/**
 * Create a DEV agent with TLS validation disabled
 * Use only in development environments
 *
 * Note: TLS is always disabled for dev agent (rejectUnauthorized=false)
 * This is also triggered when NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0 is set
 */
export function createDevAgent(): Agent {
  // Check if SSL is disabled via env vars for logging purposes
  const envSslDisabled = isSslVerifyDisabledByEnv();

  const options = {
    connect: devTlsOptions,
    keepAliveTimeout: 60_000,
    keepAliveMaxTimeout: 60_000,
    connections: 1,
  };
  log.debug(
    `createDevAgent: Creating Agent with connect.rejectUnauthorized=false (envSslDisabled=${envSslDisabled}), ` +
      `keepAliveTimeout=${options.keepAliveTimeout}, keepAliveMaxTimeout=${options.keepAliveMaxTimeout}, ` +
      `connections=${options.connections}`
  );
  const agent = new Agent(options);
  log.debug('createDevAgent: Agent created successfully');
  return agent;
}

/**
 * Create a "stay alive" agent with keep-alive enabled
 * Good for persistent connections and high-throughput scenarios
 *
 * Note: TLS is disabled when NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0 is set
 */
export function createStayAliveAgent(): Agent {
  const envSslDisabled = isSslVerifyDisabledByEnv();

  const options = {
    keepAliveTimeout: 30_000,
    keepAliveMaxTimeout: 60_000,
    ...(envSslDisabled && { connect: devTlsOptions }),
  };
  log.debug(
    `createStayAliveAgent: Creating Agent with keepAliveTimeout=${options.keepAliveTimeout}, ` +
      `keepAliveMaxTimeout=${options.keepAliveMaxTimeout}, envSslDisabled=${envSslDisabled}`
  );
  const agent = new Agent(options);
  log.debug('createStayAliveAgent: Agent created successfully');
  return agent;
}

/**
 * Create a "do not stay alive" agent
 * Connections close immediately after use
 * Good for one-off requests or debugging
 *
 * Note: TLS is disabled when NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0 is set
 */
export function createDoNotStayAliveAgent(): Agent {
  const envSslDisabled = isSslVerifyDisabledByEnv();

  const options = {
    keepAliveTimeout: 0,
    keepAliveMaxTimeout: 0,
    pipelining: 0,
    ...(envSslDisabled && { connect: devTlsOptions }),
  };
  log.debug(
    `createDoNotStayAliveAgent: Creating Agent with keepAliveTimeout=0, keepAliveMaxTimeout=0, pipelining=0, envSslDisabled=${envSslDisabled}`
  );
  const agent = new Agent(options);
  log.debug('createDoNotStayAliveAgent: Agent created successfully');
  return agent;
}

/**
 * Create a proxy agent with optional TLS options
 * @param proxyUrl - The proxy server URL
 * @param disableTls - Whether to disable TLS validation (default: based on env vars or isDev())
 *
 * Priority for disabling TLS:
 * 1. Explicit disableTls parameter
 * 2. Environment variables (NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0)
 * 3. isDev() fallback
 */
export function createProxyAgent(proxyUrl: string, disableTls?: boolean): ProxyAgent {
  // Priority: explicit param > env vars > isDev()
  let shouldDisableTls: boolean;
  if (disableTls !== undefined) {
    shouldDisableTls = disableTls;
  } else if (isSslVerifyDisabledByEnv()) {
    shouldDisableTls = true;
  } else {
    shouldDisableTls = isDev();
  }

  log.debug(
    `createProxyAgent: proxyUrl=${maskProxyUrl(proxyUrl)}, disableTls=${disableTls}, ` +
      `envSslDisabled=${isSslVerifyDisabledByEnv()}, shouldDisableTls=${shouldDisableTls}`
  );

  const options: ConstructorParameters<typeof ProxyAgent>[0] = {
    uri: proxyUrl,
    ...(shouldDisableTls && {
      requestTls: devTlsOptions,
      proxyTls: devTlsOptions,
    }),
  };

  log.debug(
    `createProxyAgent: ProxyAgent options - uri=${maskProxyUrl(proxyUrl)}, ` +
      `requestTls.rejectUnauthorized=${shouldDisableTls ? false : 'default'}, ` +
      `proxyTls.rejectUnauthorized=${shouldDisableTls ? false : 'default'}`
  );

  const agent = new ProxyAgent(options);
  log.debug('createProxyAgent: ProxyAgent created successfully');
  return agent;
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
