/**
 * Simple dispatcher API
 * Returns the appropriate Agent or ProxyAgent based on environment
 */

import type { Dispatcher } from 'undici';
import { getEffectiveProxyUrl, isDev } from './config.mjs';
import { createDevAgent, createProxyAgent, createStayAliveAgent } from './agents.mjs';

/**
 * Options for getProxyDispatcher
 */
export interface DispatcherOptions {
  /** Force disable TLS validation (default: auto based on APP_ENV) */
  disableTls?: boolean;
  /** Use stay-alive agent when no proxy is needed (default: false) */
  stayAlive?: boolean;
}

/**
 * Get the appropriate dispatcher for the current environment
 *
 * Logic:
 * 1. If proxy configured (corporate HTTP_PROXY/HTTPS_PROXY or env-specific PROXY_*_URL) → ProxyAgent
 * 2. If DEV environment with no proxy → DevAgent (TLS disabled)
 * 3. If stayAlive option is true → StayAliveAgent
 * 4. Otherwise → undefined (use default fetch behavior)
 *
 * @param options - Configuration options
 * @returns Agent, ProxyAgent, or undefined
 *
 * @example
 * // Basic usage - auto-detect environment
 * await fetch(url, { dispatcher: getProxyDispatcher() });
 *
 * @example
 * // Force TLS disabled
 * await fetch(url, { dispatcher: getProxyDispatcher({ disableTls: true }) });
 *
 * @example
 * // Use stay-alive agent in non-DEV without proxy
 * await fetch(url, { dispatcher: getProxyDispatcher({ stayAlive: true }) });
 */
export function getProxyDispatcher(options: DispatcherOptions = {}): Dispatcher | undefined {
  const { disableTls, stayAlive = false } = options;

  const proxyUrl = getEffectiveProxyUrl();

  // If proxy URL exists, use ProxyAgent
  if (proxyUrl) {
    return createProxyAgent(proxyUrl, disableTls);
  }

  // If DEV environment with no proxy, return DEV agent (TLS disabled)
  if (isDev()) {
    return createDevAgent();
  }

  // For non-DEV environments without proxy
  if (stayAlive) {
    return createStayAliveAgent();
  }

  // Return undefined to use default fetch behavior
  return undefined;
}

export default {
  getProxyDispatcher,
};
