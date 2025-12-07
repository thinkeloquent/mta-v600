/**
 * Loaded Config Admin Routes Plugin
 *
 * Exposes static configuration status and loaded properties via admin endpoints.
 * Uses the static-config singleton from @internal/static-config-property-management.
 */

import fastifyPlugin from "fastify-plugin";

/**
 * Loaded Config Routes Plugin
 */
async function loadedConfigRoutesPlugin(fastify, options) {
  const prefix = options.prefix || "/healthz/admin/loaded-config";

  // Get static config from decorator (set in main.mjs)
  const getStaticConfig = () => fastify.staticConfig;

  /**
   * GET /healthz/admin/loaded-config
   * Returns config status and summary
   */
  fastify.get(prefix, async (request, reply) => {
    const staticConfig = getStaticConfig();
    const isInitialized = staticConfig?.isInitialized?.() ?? false;
    const loadResult = staticConfig?.getLoadResult?.() ?? {
      filesLoaded: [],
      errors: [],
      configFile: null,
      appEnv: null,
    };

    const hasErrors = (loadResult.errors?.length ?? 0) > 0;
    let status = "not_configured";
    if (isInitialized && !hasErrors) {
      status = "loaded";
    } else if (isInitialized && hasErrors) {
      status = "error";
    }

    return {
      status,
      initialized: isInitialized,
      summary: {
        filesLoaded: loadResult.filesLoaded?.length ?? 0,
        appEnv: loadResult.appEnv ?? null,
        errorsCount: loadResult.errors?.length ?? 0,
      },
      configFile: loadResult.configFile ?? null,
      errors: loadResult.errors ?? [],
      timestamp: new Date().toISOString(),
    };
  });

  /**
   * GET /healthz/admin/loaded-config/data
   * Returns all loaded configuration data
   */
  fastify.get(`${prefix}/data`, async (request, reply) => {
    const staticConfig = getStaticConfig();
    const isInitialized = staticConfig?.isInitialized?.() ?? false;

    if (!isInitialized) {
      return reply.status(404).send({
        error: "Config not initialized",
        message: "Static configuration has not been loaded",
      });
    }

    const loadResult = staticConfig.getLoadResult();
    const appEnv = loadResult?.appEnv ?? null;
    const data = staticConfig.getAll();

    return {
      status: "loaded",
      appEnv,
      data,
      timestamp: new Date().toISOString(),
    };
  });

  /**
   * GET /healthz/admin/loaded-config/providers/:providerName
   * Returns configuration for a specific provider
   */
  fastify.get(`${prefix}/providers/:providerName`, async (request, reply) => {
    const { providerName } = request.params;
    const staticConfig = getStaticConfig();
    const isInitialized = staticConfig?.isInitialized?.() ?? false;

    if (!isInitialized) {
      return reply.status(404).send({
        error: "Config not initialized",
        message: "Static configuration has not been loaded",
      });
    }

    const providers = staticConfig.get("providers", {});
    const availableProviders = Object.keys(providers);

    if (!providers[providerName]) {
      return reply.status(404).send({
        status: "not_found",
        provider: providerName,
        message: `Provider "${providerName}" not found in configuration`,
        availableProviders,
        timestamp: new Date().toISOString(),
      });
    }

    return {
      status: "loaded",
      provider: providerName,
      config: providers[providerName],
      timestamp: new Date().toISOString(),
    };
  });

  fastify.log.info(`Loaded config admin routes registered at ${prefix}`);
}

export default fastifyPlugin(loadedConfigRoutesPlugin, {
  name: "loaded-config-routes",
  fastify: "5.x",
});
