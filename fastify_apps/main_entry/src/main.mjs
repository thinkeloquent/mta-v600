#!/usr/bin/env node
/**
 * Main Entry Fastify Server
 *
 * Production-ready server that serves the shared frontend from
 * frontend_apps/main_entry with SSR config injection.
 *
 * Usage:
 *   node src/main.mjs
 *   node src/main.mjs --port=3001
 *   node src/main.mjs --host=127.0.0.1 --log-level=debug
 */

// ============================================================
// IMPORTANT: Load vault secrets BEFORE any other imports
// This ensures environment variables are set before config loads
// ============================================================
import { on_startup as loadVault, env as vaultEnv } from "@internal/vault-file";

const VAULT_SECRET_FILE = process.env.VAULT_SECRET_FILE;
let vaultLoaded = false;
let vaultKeysCount = 0;

if (VAULT_SECRET_FILE) {
  try {
    await loadVault({ location: VAULT_SECRET_FILE, override: false });
    vaultLoaded = vaultEnv.isInitialized();
    vaultKeysCount = Object.keys(vaultEnv.getAll()).length;
  } catch (err) {
    console.error(
      `Failed to load vault from ${VAULT_SECRET_FILE}:`,
      err.message
    );
  }
}

// ============================================================
// Load static config AFTER vault (so APP_ENV can be set from vault)
// ============================================================
import {
  loadYamlConfig,
  config as staticConfigEnv,
} from "@internal/app-static-config-yaml";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const configDir = path.resolve(__dirname, "..", "..", "..", "common", "config");

let staticConfigLoaded = false;
let staticConfigAppEnv = "N/A";

try {
  const result = await loadYamlConfig({ configDir });
  staticConfigLoaded = staticConfigEnv.isInitialized();
  staticConfigAppEnv = result.appEnv || "N/A";
} catch (err) {
  console.error(`Failed to load static config:`, err.message);
}

// ============================================================
// Now import the rest of the application
// ============================================================
import Fastify from "fastify";
import cors from "@fastify/cors";
import "dotenv/config";

import mainEntryPlugin from "./index.mjs";
import vaultRoutesPlugin from "./routes/vault.mjs";
import loadedConfigRoutesPlugin from "./routes/loaded_config.mjs";
import providerConnectionRoutesPlugin from "./routes/provider_connection.mjs";

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

// Expose vault service as a decorator
fastify.decorate("vault", vaultEnv);

// Expose static config as a decorator
fastify.decorate("staticConfig", staticConfigEnv);

// Register vault admin routes
await fastify.register(vaultRoutesPlugin, {
  prefix: "/healthz/admin/vault",
});

// Register loaded-config admin routes
await fastify.register(loadedConfigRoutesPlugin, {
  prefix: "/healthz/admin/loaded-config",
});

// Register provider connection health check routes
await fastify.register(providerConnectionRoutesPlugin, {
  prefix: "/healthz/providers/connection",
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
  const vaultStatus = vaultLoaded ? "LOADED" : "NOT CONFIGURED";
  const staticConfigStatus = staticConfigLoaded ? "LOADED" : "NOT CONFIGURED";
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
║  Vault:                                                    ║
║    Status: ${vaultStatus.padEnd(41)}║
║    Keys loaded: ${vaultKeysCount.toString().padEnd(36)}║
║                                                            ║
║  Static Config:                                            ║
║    Status: ${staticConfigStatus.padEnd(41)}║
║    APP_ENV: ${staticConfigAppEnv.padEnd(40)}║
║                                                            ║
║  API Endpoints:                                            ║
║    GET  /health              - Health check                ║
║    GET  /api/fastify         - API info                    ║
║    GET  /api/fastify/hello   - Hello endpoint              ║
║    POST /api/fastify/echo    - Echo endpoint               ║
║                                                            ║
║  Admin Endpoints:                                          ║
║    GET  /healthz/admin/vault          - Vault status       ║
║    GET  /healthz/admin/vault/keys     - Loaded keys        ║
║    GET  /healthz/admin/loaded-config       - Config status ║
║    GET  /healthz/admin/loaded-config/data  - Full config   ║
║                                                            ║
║  Provider Health Endpoints:                                ║
║    GET  /healthz/providers/connection      - Providers list║
║    GET  /healthz/providers/connection/:p   - Check provider║
║                                                            ║
║  Frontend: Served from frontend_apps/main_entry/dist       ║
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
