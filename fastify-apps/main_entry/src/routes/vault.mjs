/**
 * Vault Admin Routes Plugin
 *
 * Exposes vault status and loaded secrets information via admin endpoints.
 * Uses the vault singleton from @internal/vault-file.
 */

import fastifyPlugin from "fastify-plugin";
import { basename } from "node:path";

/**
 * Redact sensitive values - show first 5 chars only
 */
function redactValue(value) {
  if (!value || typeof value !== "string") return "**(redacted)";
  if (value.length <= 5) return value.slice(0, value.length) + "**(redacted)";
  return value.slice(0, 5) + "**(redacted)";
}

/**
 * Vault Routes Plugin
 */
async function vaultRoutesPlugin(fastify, options) {
  const prefix = options.prefix || "/healthz/admin/vault";

  // Get vault from decorator (set in main.mjs)
  const getVault = () => fastify.vault;

  /**
   * GET /healthz/admin/vault
   * Returns vault status and summary
   */
  fastify.get(prefix, async (request, reply) => {
    const vault = getVault();
    const isInitialized = vault?.isInitialized?.() ?? false;
    const loadResult = vault?.getLoadResult?.() ?? { loaded: [], errors: [] };
    const allVars = vault?.getAll?.() ?? {};

    return {
      status: isInitialized ? "loaded" : "not_configured",
      initialized: isInitialized,
      summary: {
        filesLoaded: loadResult.loaded?.length ?? 0,
        keysLoaded: Object.keys(allVars).length,
        errorsCount: loadResult.errors?.length ?? 0,
      },
      files: loadResult.loaded ?? [],
      errors: loadResult.errors ?? [],
      timestamp: new Date().toISOString(),
    };
  });

  /**
   * GET /healthz/admin/vault/keys
   * Returns all loaded keys with redacted values
   */
  fastify.get(`${prefix}/keys`, async (request, reply) => {
    const vault = getVault();
    const isInitialized = vault?.isInitialized?.() ?? false;

    if (!isInitialized) {
      return reply.status(404).send({
        error: "Vault not initialized",
        message: "No VAULT_SECRET_FILE configured or failed to load",
      });
    }

    const allVars = vault.getAll();
    const redactedVars = {};

    for (const [key, value] of Object.entries(allVars)) {
      redactedVars[key] = redactValue(value);
    }

    return {
      status: "loaded",
      keysCount: Object.keys(redactedVars).length,
      keys: redactedVars,
      timestamp: new Date().toISOString(),
    };
  });

  /**
   * GET /healthz/admin/vault/:fileName
   * Returns status for a specific loaded file
   */
  fastify.get(`${prefix}/:fileName`, async (request, reply) => {
    const { fileName } = request.params;
    const vault = getVault();
    const isInitialized = vault?.isInitialized?.() ?? false;
    const loadResult = vault?.getLoadResult?.() ?? { loaded: [], errors: [] };

    if (!isInitialized) {
      return reply.status(404).send({
        error: "Vault not initialized",
        message: "No VAULT_SECRET_FILE configured or failed to load",
      });
    }

    // Find file in loaded files
    const loadedFiles = loadResult.loaded ?? [];
    const matchedFile = loadedFiles.find(
      (filePath) => basename(filePath) === fileName || filePath === fileName
    );

    if (matchedFile) {
      return {
        status: "loaded",
        fileName: fileName,
        filePath: matchedFile,
        timestamp: new Date().toISOString(),
      };
    }

    // Check if file had an error
    const errors = loadResult.errors ?? [];
    const matchedError = errors.find(
      (err) => basename(err.file) === fileName || err.file === fileName
    );

    if (matchedError) {
      return reply.status(500).send({
        status: "error",
        fileName: fileName,
        filePath: matchedError.file,
        error: matchedError.error,
        timestamp: new Date().toISOString(),
      });
    }

    return reply.status(404).send({
      status: "not_found",
      fileName: fileName,
      message: `File "${fileName}" was not loaded by vault`,
      availableFiles: loadedFiles.map((f) => basename(f)),
      timestamp: new Date().toISOString(),
    });
  });

  fastify.log.info(`Vault admin routes registered at ${prefix}`);
}

export default fastifyPlugin(vaultRoutesPlugin, {
  name: "vault-routes",
  fastify: "5.x",
});
