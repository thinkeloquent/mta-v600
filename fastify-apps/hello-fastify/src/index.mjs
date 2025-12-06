/**
 * Hello Fastify Plugin
 *
 * A simple hello world Fastify plugin demonstrating the monorepo structure.
 * Serves a shared frontend from frontend-apps with SSR config injection.
 */

import fastifyPlugin from 'fastify-plugin';
import fastifyStatic from '@fastify/static';
import { readFileSync, existsSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
// Navigate up: src -> hello-fastify -> fastify-apps -> project root
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..');

const APP_NAME = 'hello-fastify';
const APP_VERSION = '1.0.0';
const API_PREFIX = `/api/${APP_NAME}`;

/**
 * Generate the SSR config script to inject into HTML
 */
function generateConfigScript(apiPrefix) {
  const config = {
    apiBase: apiPrefix,
    backendType: 'fastify',
    backendVersion: APP_VERSION,
    appName: 'Hello App (Fastify)',
  };
  return `<script>window.__APP_CONFIG__ = ${JSON.stringify(config)};</script>`;
}

/**
 * Inject config into HTML by replacing the placeholder comment
 */
function injectConfig(html, apiPrefix) {
  const configScript = generateConfigScript(apiPrefix);
  return html.replace('<!-- SSR_CONFIG_PLACEHOLDER - Backend injects window.__APP_CONFIG__ here -->', configScript);
}

/**
 * Hello Fastify Plugin
 */
async function helloFastifyPlugin(fastify, options) {
  const apiPrefix = options.apiPrefix || API_PREFIX;
  const frontendApp = options.frontendApp || 'hello-app';
  const frontendDir = options.frontendDir || resolve(PROJECT_ROOT, 'frontend-apps', frontendApp, 'dist');

  // Cache injected HTML
  let indexHtml = null;
  const indexPath = join(frontendDir, 'index.html');
  if (existsSync(indexPath)) {
    const rawHtml = readFileSync(indexPath, 'utf-8');
    indexHtml = injectConfig(rawHtml, apiPrefix);
  }

  // API Routes
  fastify.get(apiPrefix, async () => ({
    name: APP_NAME,
    version: APP_VERSION,
    status: 'healthy',
    timestamp: new Date().toISOString(),
  }));

  fastify.get(`${apiPrefix}/hello`, async (request) => {
    const { name = 'World' } = request.query;
    return {
      message: `Hello, ${name}!`,
      timestamp: new Date().toISOString(),
    };
  });

  fastify.post(`${apiPrefix}/echo`, async (request) => ({
    echo: request.body,
    receivedAt: new Date().toISOString(),
  }));

  // Serve static assets from /assets
  const assetsDir = join(frontendDir, 'assets');
  if (existsSync(assetsDir)) {
    await fastify.register(fastifyStatic, {
      root: assetsDir,
      prefix: '/assets/',
      decorateReply: false,
    });
  }

  // Serve index.html with SSR config
  fastify.get('/', async (request, reply) => {
    if (indexHtml) {
      return reply.type('text/html').send(indexHtml);
    }
    return reply.status(404).send({ error: 'Frontend not built. Run: pnpm build' });
  });

  // SPA fallback
  fastify.setNotFoundHandler(async (request, reply) => {
    if (request.url.startsWith('/api/')) {
      return reply.status(404).send({ error: 'Not found' });
    }
    if (indexHtml) {
      return reply.type('text/html').send(indexHtml);
    }
    return reply.status(404).send({ error: 'Frontend not built. Run: pnpm build' });
  });

  fastify.log.info(`Frontend serving from ${frontendDir}`);
  fastify.log.info(`Hello Fastify plugin registered at ${apiPrefix}`);
}

export default fastifyPlugin(helloFastifyPlugin, {
  name: APP_NAME,
  fastify: '5.x',
});
