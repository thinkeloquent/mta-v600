/**
 * Health status endpoint with full internal package integration.
 *
 * Demonstrates integration with:
 * - @internal/app-static-config-yaml for YAML configuration
 * - @internal/provider-api-getters for API token resolution
 * - @internal/fetch-client for HTTP requests
 * - @internal/fetch-proxy-dispatcher for proxy configuration
 */

import { ConfluenceApiToken } from '@internal/provider-api-getters';
import { createClientWithDispatcher } from '@internal/fetch-client';

/**
 * Health status routes plugin.
 *
 * @param {import('fastify').FastifyInstance} fastify - Fastify instance
 * @param {Object} options - Plugin options
 */
export default async function healthStatusRoutes(fastify, options) {
  /**
   * GET /
   * Health status endpoint demonstrating internal package integration.
   */
  fastify.get('/', async (request, reply) => {
    // Get static config from fastify decorator
    const staticConfig = fastify.staticConfig;

    // Initialize provider from static config
    const provider = new ConfluenceApiToken(staticConfig);
    const apiKeyResult = provider.getApiKey();
    const networkConfig = provider.getNetworkConfig();
    const baseUrl = provider.getBaseUrl();

    // Build status response
    const status = {
      status: 'healthy',
      provider: 'confluence',
      config: {
        base_url: baseUrl,
        has_credentials: apiKeyResult.hasCredentials,
        auth_type: apiKeyResult.authType,
        network: {
          proxy_url: networkConfig.proxyUrl,
          cert_verify: networkConfig.certVerify,
        },
      },
    };

    // Make actual API call to verify connectivity
    if (apiKeyResult.hasCredentials && baseUrl) {
      let client = null;
      try {
        client = await createClientWithDispatcher({
          baseUrl: baseUrl,
          auth: {
            type: 'basic_email_token',
            rawApiKey: apiKeyResult.rawApiKey,
            email: apiKeyResult.email,
          },
          headers: { Accept: 'application/json' },
          verify: networkConfig.certVerify,
          proxy: networkConfig.proxyUrl,
        });

        const response = await client.get('/rest/api/user/current');
        status.connectivity = {
          connected: response.ok,
          status_code: response.status,
        };
      } catch (e) {
        status.connectivity = {
          connected: false,
          error: e.message,
        };
      } finally {
        if (client && typeof client.close === 'function') {
          await client.close();
        }
      }
    } else {
      status.connectivity = {
        connected: false,
        error: 'Missing credentials or base_url',
      };
    }

    return status;
  });
}
