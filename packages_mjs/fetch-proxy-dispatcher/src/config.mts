/**
 * Configuration for fetch-proxy-dispatcher
 * Environment detection and proxy URL mapping
 */

import process from 'node:process';

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
  if (
    raw === Environment.DEV ||
    raw === Environment.STAGE ||
    raw === Environment.QA ||
    raw === Environment.PROD
  ) {
    return raw;
  }
  return Environment.DEV;
}

/**
 * Check if current environment is development
 */
export function isDev(): boolean {
  return getAppEnv() === Environment.DEV;
}

/**
 * Check if current environment is production
 */
export function isProd(): boolean {
  return getAppEnv() === Environment.PROD;
}

/**
 * Get the proxy URL for the current environment
 * Reads PROXY_DEV_URL, PROXY_STAGE_URL, PROXY_QA_URL, or PROXY_PROD_URL
 */
export function getProxyUrl(): string | undefined {
  const env = getAppEnv();
  return process.env[`PROXY_${env}_URL`];
}

/**
 * Get agent proxy URL (HTTP_PROXY or HTTPS_PROXY override)
 * HTTPS_PROXY takes precedence over HTTP_PROXY
 */
export function getAgentProxyUrl(): string | undefined {
  return process.env['HTTPS_PROXY'] || process.env['HTTP_PROXY'];
}

/**
 * Determine the effective proxy URL to use
 * Priority: Agent proxy > Environment-specific proxy
 */
export function getEffectiveProxyUrl(): string | undefined {
  return getAgentProxyUrl() || getProxyUrl();
}

/**
 * Check if any proxy is configured
 */
export function isProxyConfigured(): boolean {
  return getEffectiveProxyUrl() !== undefined;
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
