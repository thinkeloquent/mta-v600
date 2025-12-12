/**
 * Factory pattern for proxy dispatcher creation
 * Provides explicit configuration injection for advanced use cases
 */

import process from 'node:process';
import type { Dispatcher } from 'undici';
import type { AppEnv } from './config.mjs';
import { getAppEnv, Environment } from './config.mjs';
import { defaultAgents, createProxyAgent, type AgentType } from './agents.mjs';
import { resolveProxyUrl } from '@internal/fetch-proxy-config';

/**
 * Simple logger for factory module
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
      console.log(`[fetch-proxy-dispatcher.factory] ${message}`);
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
 * Proxy URL configuration per environment
 */
export interface ProxyUrlConfig {
  DEV?: string;
  STAGE?: string;
  QA?: string;
  PROD?: string;
}

/**
 * Agent proxy configuration
 */
export interface AgentProxyConfig {
  httpProxy?: string;
  httpsProxy?: string;
}

/**
 * Factory configuration
 */
export interface FactoryConfig {
  /** Proxy URLs per environment */
  proxyUrls?: ProxyUrlConfig;
  /** Direct proxy URL override */
  proxyUrl?: string;
  /** Agent proxy overrides */
  agentProxy?: AgentProxyConfig;
  /** Default environment when not detected */
  defaultEnvironment?: AppEnv;
}

/**
 * Options for getProxyDispatcher method
 */
export interface FactoryOptions {
  /** Target environment (default: auto-detect from APP_ENV) */
  environment?: AppEnv;
  /** Force disable TLS validation */
  disableTls?: boolean;
  /** Agent type to use when no proxy (default: DEV for DEV env, stayAlive otherwise) */
  agentType?: AgentType;
}

/**
 * Factory class for creating proxy dispatchers with explicit configuration
 *
 * @example
 * const factory = new ProxyDispatcherFactory({
 *   proxyUrls: {
 *     PROD: 'http://proxy.company.com:8080',
 *     QA: 'http://qa-proxy.company.com:8080',
 *   },
 * });
 *
 * await fetch(url, { dispatcher: factory.getProxyDispatcher() });
 */
export class ProxyDispatcherFactory {
  private config: FactoryConfig;

  constructor(config: FactoryConfig = {}) {
    this.config = config;

    // Log factory initialization
    const proxyUrlsStr = config.proxyUrls
      ? Object.entries(config.proxyUrls)
        .map(([k, v]) => `${k}=${maskProxyUrl(v)}`)
        .join(', ')
      : 'none';
    const proxyUrlStr = config.proxyUrl ? maskProxyUrl(config.proxyUrl) : 'none';
    const agentProxyStr = config.agentProxy
      ? `http=${maskProxyUrl(config.agentProxy.httpProxy)}, https=${maskProxyUrl(config.agentProxy.httpsProxy)}`
      : 'none';

    log.debug(
      `ProxyDispatcherFactory.__init__: proxyUrls=[${proxyUrlsStr}], proxyUrl=${proxyUrlStr}, ` +
      `agentProxy=[${agentProxyStr}], defaultEnvironment=${config.defaultEnvironment ?? 'auto'}`
    );
  }

  /**
   * Get a dispatcher based on options and factory configuration
   *
   * Priority:
   * 1. Agent proxy (httpsProxy > httpProxy)
   * 2. Environment-specific proxy from config
   * 3. Appropriate agent based on environment
   */
  getProxyDispatcher(options: FactoryOptions = {}): Dispatcher {
    log.debug(
      `getProxyDispatcher: environment=${options.environment ?? 'auto'}, ` +
      `disableTls=${options.disableTls}, agentType=${options.agentType ?? 'auto'}`
    );

    const env = options.environment ?? this.config.defaultEnvironment ?? getAppEnv();
    log.debug(`getProxyDispatcher: Resolved environment=${env}`);

    // Priority 1: Agent proxy override
    const agentProxy =
      this.config.agentProxy?.httpsProxy || this.config.agentProxy?.httpProxy;

    if (agentProxy) {
      log.debug(`getProxyDispatcher: Using agent proxy=${maskProxyUrl(agentProxy)}`);
      const dispatcher = createProxyAgent(agentProxy, options.disableTls);
      log.debug('getProxyDispatcher: ProxyAgent created from agent proxy');
      return dispatcher;
    }

    // Use shared resolution logic
    // Convert config to NetworkConfig format
    const networkConfig = {
      default_environment: this.config.defaultEnvironment,
      // Convert mapping back to what resolver expects if keys match
      proxy_urls: this.config.proxyUrls as Record<string, string>,
      agent_proxy: {
        http_proxy: this.config.agentProxy?.httpProxy,
        https_proxy: this.config.agentProxy?.httpsProxy
      }
    };

    // Pass direct override from factory config if present
    const resolvedUrl = resolveProxyUrl(networkConfig, this.config.proxyUrl);

    if (resolvedUrl) {
      log.debug(`getProxyDispatcher: Resolved proxy URL=${maskProxyUrl(resolvedUrl)}`);
      const dispatcher = createProxyAgent(resolvedUrl, options.disableTls);
      return dispatcher;
    }

    // Return appropriate agent
    const agentType = options.agentType ?? (env === Environment.DEV ? 'DEV' : 'stayAlive');
    log.debug(`getProxyDispatcher: No proxy configured, using agent type=${agentType}`);
    const dispatcher = defaultAgents[agentType]();
    log.debug(`getProxyDispatcher: Agent created of type=${agentType}`);
    return dispatcher;
  }

  /**
   * Get a dispatcher for a specific environment
   */
  getDispatcherForEnvironment(env: AppEnv): Dispatcher {
    log.debug(`getDispatcherForEnvironment: env=${env}`);
    return this.getProxyDispatcher({ environment: env });
  }

  /**
   * Update proxy URL configuration
   */
  setProxyUrls(proxyUrls: ProxyUrlConfig): void {
    log.debug(`setProxyUrls: Updating proxy URLs`);
    this.config.proxyUrls = { ...this.config.proxyUrls, ...proxyUrls };
  }

  /**
   * Update agent proxy configuration
   */
  setAgentProxy(agentProxy: AgentProxyConfig): void {
    log.debug(
      `setAgentProxy: httpProxy=${maskProxyUrl(agentProxy.httpProxy)}, ` +
      `httpsProxy=${maskProxyUrl(agentProxy.httpsProxy)}`
    );
    this.config.agentProxy = { ...this.config.agentProxy, ...agentProxy };
  }

  /**
   * Get the current configuration
   */
  getConfig(): FactoryConfig {
    return { ...this.config };
  }
}

/**
 * Create a factory instance with configuration
 *
 * @example
 * const factory = createProxyDispatcherFactory({
 *   proxyUrls: { PROD: 'http://proxy:8080' },
 * });
 */
export function createProxyDispatcherFactory(config?: FactoryConfig): ProxyDispatcherFactory {
  log.debug('createProxyDispatcherFactory: Creating new factory instance');
  return new ProxyDispatcherFactory(config);
}

export default {
  ProxyDispatcherFactory,
  createProxyDispatcherFactory,
};
