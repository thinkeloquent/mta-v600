/**
 * Hello Fastify Plugin
 *
 * A simple hello world Fastify plugin demonstrating the monorepo structure.
 */

import fastifyPlugin from 'fastify-plugin';
import { readFileSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';

const APP_NAME = 'hello-fastify';
const API_PREFIX = `/api/${APP_NAME}`;

/**
 * Hello Fastify Plugin
 * @param {import('fastify').FastifyInstance} fastify
 * @param {Object} options
 * @param {string} [options.apiPrefix] - Custom API prefix
 * @param {string} [options.frontendPrefix] - Frontend route prefix (e.g., /apps/hello-fastify)
 * @param {string} [options.frontendDir] - Path to frontend dist directory
 */
async function helloFastifyPlugin(fastify, options) {
  const apiPrefix = options.apiPrefix || API_PREFIX;
  const frontendPrefix = options.frontendPrefix;
  const frontendDir = options.frontendDir;

  // Health check endpoint
  fastify.get(apiPrefix, async (request, reply) => {
    return {
      name: APP_NAME,
      version: '1.0.0',
      status: 'healthy',
      timestamp: new Date().toISOString(),
    };
  });

  // Hello endpoint with optional name parameter
  fastify.get(`${apiPrefix}/hello`, async (request, reply) => {
    const { name = 'World' } = request.query;
    return {
      message: `Hello, ${name}!`,
      timestamp: new Date().toISOString(),
    };
  });

  // Echo endpoint - returns the request body
  fastify.post(`${apiPrefix}/echo`, async (request, reply) => {
    return {
      echo: request.body,
      receivedAt: new Date().toISOString(),
    };
  });

  // Serve frontend if configured
  if (frontendPrefix && frontendDir) {
    const absoluteFrontendDir = resolve(frontendDir);

    if (existsSync(absoluteFrontendDir)) {
      // Serve static files
      fastify.register(import('@fastify/static'), {
        root: absoluteFrontendDir,
        prefix: frontendPrefix,
        decorateReply: false,
      });

      // SPA fallback - serve index.html for all non-API routes under the prefix
      fastify.get(`${frontendPrefix}/*`, async (request, reply) => {
        const indexPath = join(absoluteFrontendDir, 'index.html');
        if (existsSync(indexPath)) {
          const content = readFileSync(indexPath, 'utf-8');
          reply.type('text/html').send(content);
        } else {
          reply.status(404).send({ error: 'Frontend not built' });
        }
      });

      fastify.log.info(`Frontend serving from ${frontendPrefix}`);
    } else {
      fastify.log.warn(`Frontend directory not found: ${absoluteFrontendDir}`);
    }
  }

  fastify.log.info(`Hello Fastify plugin registered at ${apiPrefix}`);
}

export default fastifyPlugin(helloFastifyPlugin, {
  name: APP_NAME,
  fastify: '5.x',
});
