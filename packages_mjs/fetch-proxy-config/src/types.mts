/**
 * Agent proxy configuration (http_proxy/https_proxy env vars)
 */
export interface AgentProxyConfig {
    http_proxy?: string | null;
    https_proxy?: string | null;
}

/**
 * Network configuration including proxy settings.
 * Renamed from ProxyConfig to better reflect its scope.
 */
export interface NetworkConfig {
    default_environment?: string;
    proxy_urls?: Record<string, string | null>;
    ca_bundle?: string | null;
    cert?: string | null;
    cert_verify?: boolean;
    agent_proxy?: AgentProxyConfig | null;
}
