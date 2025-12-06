/**
 * Application configuration injected by the backend via SSR.
 *
 * The backend serves index.html and injects a script tag with:
 * window.__APP_CONFIG__ = { apiBase: '/api/...', backendType: 'fastify', ... }
 *
 * This allows the same frontend to work with different backends.
 */

export interface AppConfig {
  /** Base URL for API calls (e.g., '/api/fastify' or '/api/fastapi') */
  apiBase: string;
  /** Backend type identifier */
  backendType: 'fastify' | 'fastapi' | 'unknown';
  /** Backend version */
  backendVersion: string;
  /** Application name */
  appName: string;
  /** Additional custom config from backend */
  [key: string]: unknown;
}

// Declare the global window property
declare global {
  interface Window {
    __APP_CONFIG__?: AppConfig;
  }
}

/**
 * Default config for local development (when not served by a backend)
 */
const defaultConfig: AppConfig = {
  apiBase: '/api/fastify',
  backendType: 'unknown',
  backendVersion: 'dev',
  appName: 'Main Entry (Dev Mode)',
};

/**
 * Get the application configuration.
 * Returns injected config from backend, or defaults for local dev.
 */
export function getConfig(): AppConfig {
  if (typeof window !== 'undefined' && window.__APP_CONFIG__) {
    return window.__APP_CONFIG__;
  }
  return defaultConfig;
}

/**
 * Get the API base URL for making requests
 */
export function getApiBase(): string {
  return getConfig().apiBase;
}
