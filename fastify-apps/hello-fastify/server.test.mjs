#!/usr/bin/env node
/**
 * Standalone development server for Hello Fastify
 *
 * Usage:
 *   node server.test.mjs
 *   node server.test.mjs --port=3001
 *   node server.test.mjs --host=127.0.0.1 --log-level=debug
 */

import Fastify from 'fastify';
import cors from '@fastify/cors';
import 'dotenv/config';

import helloFastifyPlugin from './src/index.mjs';

// Parse command line arguments
const args = process.argv.slice(2).reduce((acc, arg) => {
  const [key, value] = arg.replace('--', '').split('=');
  acc[key] = value || true;
  return acc;
}, {});

// Configuration
const PORT = parseInt(args.port || process.env.PORT || '3000', 10);
const HOST = args.host || process.env.HOST || '0.0.0.0';
const LOG_LEVEL = args['log-level'] || process.env.LOG_LEVEL || 'info';

// Create Fastify instance
const fastify = Fastify({
  logger: {
    level: LOG_LEVEL,
    transport: {
      target: 'pino-pretty',
      options: {
        colorize: true,
        translateTime: 'HH:MM:ss Z',
        ignore: 'pid,hostname',
      },
    },
  },
});

// Register CORS
await fastify.register(cors, {
  origin: true,
  credentials: true,
});

// Register hello-fastify plugin
await fastify.register(helloFastifyPlugin, {
  apiPrefix: '/api/hello-fastify',
  frontendPrefix: '/apps/hello-fastify',
  frontendDir: './frontend/dist',
});

// Root health check
fastify.get('/health', async () => ({
  status: 'ok',
  timestamp: new Date().toISOString(),
}));

// Root endpoint - serve frontend or redirect
fastify.get('/', async (request, reply) => {
  reply.redirect('/apps/hello-fastify');
});

// Request logging hook
fastify.addHook('onResponse', (request, reply, done) => {
  fastify.log.info({
    method: request.method,
    url: request.url,
    statusCode: reply.statusCode,
    responseTime: reply.elapsedTime,
  });
  done();
});

// Error handler
fastify.setErrorHandler((error, request, reply) => {
  fastify.log.error(error);
  reply.status(error.statusCode || 500).send({
    error: error.name || 'InternalServerError',
    message: error.message,
    statusCode: error.statusCode || 500,
  });
});

// Start server
try {
  await fastify.listen({ port: PORT, host: HOST });
  console.log(`
╔════════════════════════════════════════════════════════════╗
║                    Hello Fastify Server                    ║
╠════════════════════════════════════════════════════════════╣
║  Server running at: http://${HOST}:${PORT.toString().padEnd(25)}║
║                                                            ║
║  Endpoints:                                                ║
║    GET  /health                    - Health check          ║
║    GET  /api/hello-fastify         - API info              ║
║    GET  /api/hello-fastify/hello   - Hello endpoint        ║
║    POST /api/hello-fastify/echo    - Echo endpoint         ║
║    GET  /apps/hello-fastify        - Frontend (if built)   ║
╚════════════════════════════════════════════════════════════╝
  `);
} catch (err) {
  fastify.log.error(err);
  process.exit(1);
}

// Graceful shutdown
const shutdown = async (signal) => {
  fastify.log.info(`Received ${signal}, shutting down gracefully...`);
  await fastify.close();
  process.exit(0);
};

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
