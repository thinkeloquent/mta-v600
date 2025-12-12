import type { NetworkConfig } from './types.mjs';

/**
 * Resolve the proxy URL based on configuration and environment variables.
 *
 * Precedence (Waterfall):
 * 1. proxyUrlOverride (e.g. from provider.proxy_url)
 * 2. networkConfig.proxy_urls[default_environment]
 * 3. PROXY_URL environment variable
 * 4. HTTPS_PROXY environment variable
 * 5. HTTP_PROXY environment variable
 *
 * @param networkConfig - Network configuration object
 * @param proxyUrlOverride - Optional override URL (highest priority)
 * @returns Resolved proxy URL string or null if no proxy should be used
 */
export function resolveProxyUrl(
    networkConfig?: NetworkConfig | null,
    proxyUrlOverride?: string | null
): string | null {
    // 1. Check override
    if (proxyUrlOverride) {
        return proxyUrlOverride;
    }

    // 2. Check network config
    if (networkConfig?.proxy_urls && networkConfig.default_environment) {
        const envKey = networkConfig.default_environment;
        const url = networkConfig.proxy_urls[envKey];
        if (url) {
            return url;
        }
    }

    // 3. PROXY_URL
    if (process.env.PROXY_URL) {
        return process.env.PROXY_URL;
    }

    // 4. HTTPS_PROXY
    if (process.env.HTTPS_PROXY) {
        return process.env.HTTPS_PROXY;
    }

    // 5. HTTP_PROXY
    if (process.env.HTTP_PROXY) {
        return process.env.HTTP_PROXY;
    }

    return null;
}
