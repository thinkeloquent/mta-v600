/**
 * Simple dispatcher API
 * Returns the appropriate Agent or ProxyAgent based on environment
 */

import process from 'node:process';
import type { Dispatcher } from 'undici';
import { getEffectiveProxyUrl, isDev } from './config.mjs';
import { createDevAgent, createProxyAgent, createStayAliveAgent } from './agents.mjs';

/**
 * Simple logger for dispatcher module
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
      console.log(`[fetch-proxy-dispatcher.dispatcher] ${message}`);
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

  log.debug(`getProxyDispatcher: disableTls=${disableTls}, stayAlive=${stayAlive}`);

  const proxyUrl = getEffectiveProxyUrl();
  log.debug(`getProxyDispatcher: effectiveProxyUrl=${maskProxyUrl(proxyUrl)}`);

  // If proxy URL exists, use ProxyAgent
  if (proxyUrl) {
    log.debug(`getProxyDispatcher: Creating ProxyAgent with proxyUrl=${maskProxyUrl(proxyUrl)}, disableTls=${disableTls}`);
    const agent = createProxyAgent(proxyUrl, disableTls);
    log.debug('getProxyDispatcher: ProxyAgent created successfully');
    return agent;
  }

  // If DEV environment with no proxy, return DEV agent (TLS disabled)
  if (isDev()) {
    log.debug('getProxyDispatcher: DEV environment detected, creating DevAgent (TLS disabled)');
    const agent = createDevAgent();
    log.debug('getProxyDispatcher: DevAgent created successfully');
    return agent;
  }

  // For non-DEV environments without proxy
  if (stayAlive) {
    log.debug('getProxyDispatcher: stayAlive=true, creating StayAliveAgent');
    const agent = createStayAliveAgent();
    log.debug('getProxyDispatcher: StayAliveAgent created successfully');
    return agent;
  }

  // Return undefined to use default fetch behavior
  log.debug('getProxyDispatcher: No proxy/agent needed, returning undefined (default fetch)');
  return undefined;
}

export default {
  getProxyDispatcher,
};
