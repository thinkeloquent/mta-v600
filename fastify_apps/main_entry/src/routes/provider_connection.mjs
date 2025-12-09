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
   */
  fastify.get(`${prefix}/:providerName`, async (request, reply) => {
    const { providerName } = request.params;
    const staticConfig = getStaticConfig();

    const checker = new ProviderHealthChecker(staticConfig);
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
