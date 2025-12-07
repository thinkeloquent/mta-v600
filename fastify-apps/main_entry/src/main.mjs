#!/usr/bin/env node
/**
 * Main Entry Fastify Server
 *
 * Production-ready server that serves the shared frontend from
 * frontend-apps/main_entry with SSR config injection.
 *
 * Usage:
 *   node src/main.mjs
 *   node src/main.mjs --port=3001
 *   node src/main.mjs --host=127.0.0.1 --log-level=debug
 */

import Fastify from "fastify";
import cors from "@fastify/cors";
import "dotenv/config";

import mainEntryPlugin from "./index.mjs";

// Build parameters (set by CI/CD or Makefile)
const BUILD_ID = process.env.BUILD_ID || "local";
const BUILD_VERSION = process.env.BUILD_VERSION || "0.0.0-dev";
const GIT_COMMIT = process.env.GIT_COMMIT || "unknown";

// Parse command line arguments
const args = process.argv.slice(2).reduce((acc, arg) => {
  const [key, value] = arg.replace("--", "").split("=");
  acc[key] = value || true;
  return acc;
}, {});

// Configuration
const PORT = parseInt(args.port || process.env.PORT || "51000", 10);
const HOST = args.host || process.env.HOST || "0.0.0.0";
const LOG_LEVEL = args["log-level"] || process.env.LOG_LEVEL || "info";

// Create Fastify instance
const fastify = Fastify({
  logger: {
    level: LOG_LEVEL,
    transport: {
      target: "pino-pretty",
      options: {
        colorize: true,
        translateTime: "HH:MM:ss Z",
        ignore: "pid,hostname",
      },
    },
  },
});

// Register CORS
await fastify.register(cors, {
  origin: true,
  credentials: true,
});

// Register main_entry plugin with shared frontend
await fastify.register(mainEntryPlugin, {
  apiPrefix: "/api/fastify",
  frontendApp: "main_entry",
});

// Health check (before 404 handler takes over)
fastify.get("/health", async () => ({
  status: "ok",
  timestamp: new Date().toISOString(),
}));

// Request logging hook
fastify.addHook("onResponse", (request, reply, done) => {
  fastify.log.info({
    method: request.method,
    url: request.url,
    statusCode: reply.statusCode,
    responseTime: reply.elapsedTime,
  });
  done();
});

// Start server
try {
  await fastify.listen({ port: PORT, host: HOST });
  console.log(`
╔════════════════════════════════════════════════════════════╗
║                  Main Entry Fastify Server                 ║
╠════════════════════════════════════════════════════════════╣
║  Server running at: http://${HOST}:${PORT.toString().padEnd(25)}║
║                                                            ║
║  Build Info:                                               ║
║    BUILD_ID:      ${BUILD_ID.padEnd(33)}║
║    BUILD_VERSION: ${BUILD_VERSION.padEnd(33)}║
║    GIT_COMMIT:    ${GIT_COMMIT.padEnd(33)}║
║                                                            ║
║  API Endpoints:                                            ║
║    GET  /health              - Health check                ║
║    GET  /api/fastify         - API info                    ║
║    GET  /api/fastify/hello   - Hello endpoint              ║
║    POST /api/fastify/echo    - Echo endpoint               ║
║                                                            ║
║  Frontend: Served from frontend-apps/main_entry/dist       ║
║    GET  /                    - SPA with SSR config         ║
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

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
