/**
 * Configuration for fetch-proxy-dispatcher
 * Environment detection and proxy URL mapping
 */

import process from 'node:process';

/**
 * Simple logger for fetch-proxy-dispatcher
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
      console.log(`[fetch-proxy-dispatcher.config] ${message}`);
    }
  },
};

/**
 * Mask proxy URL for safe logging (hide credentials if present)
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
 * Environment constants
 */
export const Environment = {
  DEV: 'DEV',
  STAGE: 'STAGE',
  QA: 'QA',
  PROD: 'PROD',
} as const;

/**
 * Valid application environments
 */
export type AppEnv = keyof typeof Environment;

/**
 * All valid environment values
 */
export const ENVIRONMENTS: AppEnv[] = [
  Environment.DEV,
  Environment.STAGE,
  Environment.QA,
  Environment.PROD,
];

/**
 * Get the current application environment
 * Reads APP_ENV, normalizes to uppercase, defaults to 'DEV'
 */
export function getAppEnv(): AppEnv {
  const raw = process.env['APP_ENV']?.toUpperCase();
  let result: AppEnv;
  if (
    raw === Environment.DEV ||
    raw === Environment.STAGE ||
    raw === Environment.QA ||
    raw === Environment.PROD
  ) {
    result = raw;
  } else {
    result = Environment.DEV;
  }
  log.debug(`getAppEnv: APP_ENV=${raw ?? 'undefined'}, result=${result}`);
  return result;
}

/**
 * Check if current environment is development
 */
export function isDev(): boolean {
  const env = getAppEnv();
  const result = env === Environment.DEV;
  log.debug(`isDev: env=${env}, result=${result}`);
  return result;
}

/**
 * Check if current environment is production
 */
export function isProd(): boolean {
  const env = getAppEnv();
  const result = env === Environment.PROD;
  log.debug(`isProd: env=${env}, result=${result}`);
  return result;
}

/**
 * Get the proxy URL for the current environment
 * Reads PROXY_DEV_URL, PROXY_STAGE_URL, PROXY_QA_URL, or PROXY_PROD_URL
 */
export function getProxyUrl(): string | undefined {
  const env = getAppEnv();
  const envVar = `PROXY_${env}_URL`;
  const result = process.env[envVar];
  log.debug(`getProxyUrl: env=${env}, envVar=${envVar}, result=${maskProxyUrl(result)}`);
  return result;
}

/**
 * Get agent proxy URL (HTTP_PROXY or HTTPS_PROXY override)
 * HTTPS_PROXY takes precedence over HTTP_PROXY
 */
export function getAgentProxyUrl(): string | undefined {
  const httpsProxy = process.env['HTTPS_PROXY'];
  const httpProxy = process.env['HTTP_PROXY'];
  const result = httpsProxy || httpProxy;
  log.debug(
    `getAgentProxyUrl: HTTPS_PROXY=${maskProxyUrl(httpsProxy)}, HTTP_PROXY=${maskProxyUrl(httpProxy)}, result=${maskProxyUrl(result)}`
  );
  return result;
}

/**
 * Determine the effective proxy URL to use
 * Priority: Agent proxy > Environment-specific proxy
 */
export function getEffectiveProxyUrl(): string | undefined {
  const agentProxy = getAgentProxyUrl();
  const envProxy = getProxyUrl();
  const result = agentProxy || envProxy;
  log.debug(
    `getEffectiveProxyUrl: agentProxy=${maskProxyUrl(agentProxy)}, envProxy=${maskProxyUrl(envProxy)}, result=${maskProxyUrl(result)}`
  );
  return result;
}

/**
 * Check if any proxy is configured
 */
export function isProxyConfigured(): boolean {
  const result = getEffectiveProxyUrl() !== undefined;
  log.debug(`isProxyConfigured: result=${result}`);
  return result;
}

export default {
  Environment,
  ENVIRONMENTS,
  getAppEnv,
  isDev,
  isProd,
  getProxyUrl,
  getAgentProxyUrl,
  getEffectiveProxyUrl,
  isProxyConfigured,
};
