/**
 * Fastify plugin for @internal/fetch-client
 *
 * Provides Fastify integration with application-scoped singleton clients.
 */
import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyPluginAsync } from 'fastify';
import type { FetchClient, ClientConfig } from '../types.mjs';
import { createClient } from '../factory.mjs';
import { warmupDns } from '../dns-warmup.mjs';

/**
 * Plugin options
 */
export interface FetchClientPluginOptions {
  /** Unique name for decorating fastify instance (e.g., 'geminiClient') */
  name: string;
  /** Client configuration */
  config: ClientConfig;
  /** DNS warmup on plugin registration (default: true) */
  warmupDns?: boolean;
}

/**
 * Fastify plugin for fetch client
 *
 * Registers a fetch client as an application-scoped singleton on the Fastify instance.
 *
 * @example
 * ```typescript
 * import Fastify from 'fastify';
 * import fetchClientPlugin from '@internal/fetch-client/fastify';
 *
 * const fastify = Fastify();
 *
 * await fastify.register(fetchClientPlugin, {
 *   name: 'geminiClient',
 *   config: {
 *     baseUrl: 'https://generativelanguage.googleapis.com',
 *     dispatcher,
 *     auth: { type: 'x-api-key', apiKey: process.env.GEMINI_API_KEY },
 *   },
 * });
 *
 * // Use in route handler
 * fastify.get('/chat', async (request) => {
 *   const response = await fastify.geminiClient.get('/v1beta/models');
 *   return response.data;
 * });
 * ```
 */
const fetchClientPlugin: FastifyPluginAsync<FetchClientPluginOptions> = async (
  fastify: FastifyInstance,
  options: FetchClientPluginOptions
) => {
  const { name, config, warmupDns: shouldWarmup = true } = options;

  // DNS warmup on startup
  if (shouldWarmup && config.baseUrl) {
    try {
      const url = new URL(config.baseUrl);
      const result = await warmupDns(url.hostname);
      if (result.success) {
        fastify.log.info(
          { hostname: url.hostname, duration: result.duration },
          `DNS warmup complete for ${name}`
        );
      } else {
        fastify.log.warn(
          { hostname: url.hostname, error: result.error?.message },
          `DNS warmup failed for ${name}`
        );
      }
    } catch (error) {
      fastify.log.warn({ error }, `DNS warmup error for ${name}`);
    }
  }

  // Create singleton client
  const client = createClient(config);

  // Decorate fastify instance (application-scoped)
  if (fastify.hasDecorator(name)) {
    throw new Error(`Decorator '${name}' already exists`);
  }

  fastify.decorate(name, client);

  // Cleanup on shutdown
  fastify.addHook('onClose', async () => {
    await client.close();
    fastify.log.info(`${name} client closed`);
  });
};

/**
 * Export wrapped plugin
 */
export default fp(fetchClientPlugin, {
  name: '@internal/fetch-client',
  fastify: '5.x',
});

/**
 * Type augmentation for Fastify
 *
 * Note: Users should augment this themselves for type-safe access:
 *
 * ```typescript
 * declare module 'fastify' {
 *   interface FastifyInstance {
 *     geminiClient: FetchClient;
 *     openaiClient: FetchClient;
 *   }
 * }
 * ```
 */
export type { FetchClient };
