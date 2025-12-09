/**
 * Provider Connection Health Check Routes Plugin
 *
 * Exposes provider connection health check endpoints.
 * Uses provider_api_getters for API token resolution and health checking.
 */

import fastifyPlugin from 'fastify-plugin';
import {
  ProviderHealthChecker,
  PROVIDER_REGISTRY,
} from '@internal/provider-api-getters';

/**
 * Provider Connection Routes Plugin
 */
async function providerConnectionRoutesPlugin(fastify, options) {
  const prefix = options.prefix || '/healthz/providers/connection';

  // Get static config from decorator (set in main.mjs)
  const getStaticConfig = () => fastify.staticConfig;

  /**
   * GET /healthz/providers/connection
   * Returns list of available providers
   */
  fastify.get(prefix, async (request, reply) => {
    const providers = Object.keys(PROVIDER_REGISTRY);
    const uniqueProviders = [...new Set(providers)].sort();

    return {
      providers: uniqueProviders,
      count: uniqueProviders.length,
      timestamp: new Date().toISOString(),
    };
  });

  /**
   * GET /healthz/providers/connection/:providerName
   * Check connection to a specific provider
   * Returns config_used with the effective configuration used for the test
   *
   * Query Parameters (proxy overrides):
   *   proxy_env: Override default_environment (e.g., 'prod', 'dev')
   *   proxy_url: Override proxy URL for the current environment
   *   cert_verify: Override SSL certificate verification (true/false)
   *   ca_bundle: Override CA bundle path
   *   http_proxy: Override HTTP agent proxy
   *   https_proxy: Override HTTPS agent proxy
   *
   * Query Parameters (client overrides):
   *   timeout_seconds: Override request timeout in seconds
   *   timeout_ms: Override request timeout in milliseconds
   *
   * Examples:
   *   /healthz/providers/connection/gemini?proxy_env=prod&proxy_url=http://proxy:8080
   *   /healthz/providers/connection/jira?cert_verify=false&timeout_seconds=120
   *   /healthz/providers/connection/github?http_proxy=http://squid:3128
   */
  fastify.get(`${prefix}/:providerName`, async (request, reply) => {
    const { providerName } = request.params;
    const staticConfig = getStaticConfig();

    // Extract query params for proxy/client overrides
    const {
      proxy_env,
      proxy_url,
      cert_verify,
      ca_bundle,
      http_proxy,
      https_proxy,
      timeout_seconds,
      timeout_ms,
    } = request.query;

    // Build runtime override from query params
    const runtimeOverride = {};

    // Proxy overrides
    const proxyOverride = {};
    if (proxy_env !== undefined) {
      proxyOverride.default_environment = proxy_env;
    }
    if (proxy_url !== undefined) {
      const envKey = proxy_env || 'default';
      proxyOverride.proxy_urls = { [envKey]: proxy_url };
    }
    if (cert_verify !== undefined) {
      proxyOverride.cert_verify = cert_verify === 'true' || cert_verify === true;
    }
    if (ca_bundle !== undefined) {
      proxyOverride.ca_bundle = ca_bundle;
    }
    if (http_proxy !== undefined || https_proxy !== undefined) {
      proxyOverride.agent_proxy = {};
      if (http_proxy !== undefined) {
        proxyOverride.agent_proxy.http_proxy = http_proxy || null;
      }
      if (https_proxy !== undefined) {
        proxyOverride.agent_proxy.https_proxy = https_proxy || null;
      }
    }

    if (Object.keys(proxyOverride).length > 0) {
      runtimeOverride.proxy = proxyOverride;
    }

    // Client overrides
    const clientOverride = {};
    if (timeout_seconds !== undefined) {
      clientOverride.timeout_seconds = parseFloat(timeout_seconds);
    }
    if (timeout_ms !== undefined) {
      clientOverride.timeout_ms = parseInt(timeout_ms, 10);
    }

    if (Object.keys(clientOverride).length > 0) {
      runtimeOverride.client = clientOverride;
    }

    // Create checker with optional runtime override
    const hasOverride = Object.keys(runtimeOverride).length > 0;
    const checker = new ProviderHealthChecker(
      staticConfig,
      hasOverride ? runtimeOverride : null
    );
    const result = await checker.check(providerName);

    return {
      provider: result.provider,
      status: result.status,
      latency_ms: result.latency_ms,
      message: result.message,
      error: result.error,
      timestamp: result.timestamp,
      config_used: result.config_used,
    };
  });

  /**
   * POST /healthz/providers/connection/:providerName
   * Check connection with runtime proxy/client override
   *
   * Useful for testing VPN/proxy configurations without modifying YAML.
   * The override is deep-merged with the static config (global + overwrite_root_config).
   *
   * Request body:
   * {
   *   "proxy": {
   *     "default_environment": "prod",
   *     "proxy_urls": {"prod": "http://proxy.internal:8080"},
   *     "cert_verify": false
   *   },
   *   "client": {
   *     "timeout_seconds": 120.0
   *   },
   *   "headers": {
   *     "X-Custom-Header": "value"
   *   }
   * }
   */
  fastify.post(`${prefix}/:providerName`, async (request, reply) => {
    const { providerName } = request.params;
    const staticConfig = getStaticConfig();
    const runtimeOverride = request.body || {};

    const checker = new ProviderHealthChecker(staticConfig, runtimeOverride);
    const result = await checker.check(providerName);

    return {
      provider: result.provider,
      status: result.status,
      latency_ms: result.latency_ms,
      message: result.message,
      error: result.error,
      timestamp: result.timestamp,
      config_used: result.config_used,
    };
  });

  fastify.log.info(`Provider connection routes registered at ${prefix}`);
}

export default fastifyPlugin(providerConnectionRoutesPlugin, {
  name: 'provider-connection-routes',
  fastify: '5.x',
});
