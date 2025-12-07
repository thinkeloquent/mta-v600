/**
 * Factory pattern for proxy dispatcher creation
 * Provides explicit configuration injection for advanced use cases
 */

import type { Dispatcher } from 'undici';
import type { AppEnv } from './config.mjs';
import { getAppEnv, Environment } from './config.mjs';
import { defaultAgents, createProxyAgent, type AgentType } from './agents.mjs';

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
    const env = options.environment ?? this.config.defaultEnvironment ?? getAppEnv();

    // Check agent proxy override
    const agentProxy =
      this.config.agentProxy?.httpsProxy || this.config.agentProxy?.httpProxy;

    if (agentProxy) {
      return createProxyAgent(agentProxy, options.disableTls);
    }

    // Check env-specific proxy
    const envProxy = this.config.proxyUrls?.[env];
    if (envProxy) {
      return createProxyAgent(envProxy, options.disableTls);
    }

    // Return appropriate agent
    const agentType = options.agentType ?? (env === Environment.DEV ? 'DEV' : 'stayAlive');
    return defaultAgents[agentType]();
  }

  /**
   * Get a dispatcher for a specific environment
   */
  getDispatcherForEnvironment(env: AppEnv): Dispatcher {
    return this.getProxyDispatcher({ environment: env });
  }

  /**
   * Update proxy URL configuration
   */
  setProxyUrls(proxyUrls: ProxyUrlConfig): void {
    this.config.proxyUrls = { ...this.config.proxyUrls, ...proxyUrls };
  }

  /**
   * Update agent proxy configuration
   */
  setAgentProxy(agentProxy: AgentProxyConfig): void {
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
  return new ProxyDispatcherFactory(config);
}

export default {
  ProxyDispatcherFactory,
  createProxyDispatcherFactory,
};
