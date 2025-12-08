/**
 * Main Entry Fastify Plugin
 *
 * Main entry point Fastify plugin demonstrating the monorepo structure.
 * Serves a shared frontend from frontend_apps with SSR config injection.
 */

import fastifyPlugin from "fastify-plugin";
import fastifyStatic from "@fastify/static";
import { readFileSync, existsSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
// Navigate up: src -> main_entry -> fastify_apps -> project root
const PROJECT_ROOT = resolve(__dirname, "..", "..", "..");

const APP_NAME = "main_entry";
const APP_VERSION = "1.0.0";
const API_PREFIX = "/api/fastify";

// Build parameters (set by CI/CD or Makefile)
const BUILD_ID = process.env.BUILD_ID || "local";
const BUILD_VERSION = process.env.BUILD_VERSION || "0.0.0-dev";
const GIT_COMMIT = process.env.GIT_COMMIT || "unknown";

/**
 * Generate the SSR config script to inject into HTML
 */
function generateConfigScript(apiPrefix) {
  const config = {
    apiBase: apiPrefix,
    backendType: "fastify",
    backendVersion: APP_VERSION,
    appName: "Main Entry (Fastify)",
    // Build parameters
    buildId: BUILD_ID,
    buildVersion: BUILD_VERSION,
    gitCommit: GIT_COMMIT,
  };
  return `<script>window.__APP_CONFIG__ = ${JSON.stringify(config)};</script>`;
}

/**
 * Inject config into HTML by replacing the placeholder comment
 */
function injectConfig(html, apiPrefix) {
  const configScript = generateConfigScript(apiPrefix);
  return html.replace(
    "<!-- SSR_CONFIG_PLACEHOLDER - Backend injects window.__APP_CONFIG__ here -->",
    configScript
  );
}

/**
 * Main Entry Fastify Plugin
 */
async function mainEntryPlugin(fastify, options) {
  const apiPrefix = options.apiPrefix || API_PREFIX;
  const frontendApp = options.frontendApp || "main_entry";
  const frontendDir =
    options.frontendDir ||
    resolve(PROJECT_ROOT, "frontend_apps", frontendApp, "dist");

  // Cache injected HTML
  let indexHtml = null;
  const indexPath = join(frontendDir, "index.html");
  if (existsSync(indexPath)) {
    const rawHtml = readFileSync(indexPath, "utf-8");
    indexHtml = injectConfig(rawHtml, apiPrefix);
  }

  // API Routes
  fastify.get(apiPrefix, async () => ({
    name: APP_NAME,
    version: APP_VERSION,
    status: "healthy",
    timestamp: new Date().toISOString(),
  }));

  fastify.get(`${apiPrefix}/hello`, async (request) => {
    const { name = "World" } = request.query;
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
  const assetsDir = join(frontendDir, "assets");
  if (existsSync(assetsDir)) {
    await fastify.register(fastifyStatic, {
      root: assetsDir,
      prefix: "/assets/",
      decorateReply: false,
    });
  }

  // Serve index.html with SSR config (includes build info)
  fastify.get("/", async (request, reply) => {
    if (indexHtml) {
      return reply.type("text/html").send(indexHtml);
    }
    return reply
      .status(404)
      .send({ error: "Frontend not built. Run: pnpm build" });
  });

  // SPA fallback - serve index.html for all non-API routes
  fastify.setNotFoundHandler(async (request, reply) => {
    // API routes should return 404, not the SPA
    if (request.url.startsWith("/api/") || request.url.startsWith("/healthz/")) {
      return reply.status(404).send({ error: "Not found" });
    }
    if (indexHtml) {
      return reply.type("text/html").send(indexHtml);
    }
    return reply
      .status(404)
      .send({ error: "Frontend not built. Run: pnpm build" });
  });

  fastify.log.info(`Frontend serving from ${frontendDir}`);
  fastify.log.info(`Main Entry plugin registered at ${apiPrefix}`);
  fastify.log.info(
    `Build info: BUILD_ID=${BUILD_ID}, BUILD_VERSION=${BUILD_VERSION}, GIT_COMMIT=${GIT_COMMIT}`
  );
}

export default fastifyPlugin(mainEntryPlugin, {
  name: APP_NAME,
  fastify: "5.x",
});
