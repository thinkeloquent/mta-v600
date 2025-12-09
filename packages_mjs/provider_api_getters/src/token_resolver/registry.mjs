/**
 * Token Resolver Registry for dynamic API token resolution.
 *
 * Supports three methods for token resolution:
 * - Option A: setAPIToken(providerName, token) - imperative runtime override
 * - Option B: runtime_import - YAML-configured module path
 * - Option C: registerResolver(providerName, fn) - function registration at startup
 *
 * Resolution priority:
 * 1. Static token via setAPIToken() (Option A)
 * 2. Registered resolver via registerResolver() (Option C)
 * 3. runtime_import module (Option B)
 * 4. Static env var (default - handled in base class)
 */

// Simple console logger for defensive programming
const logger = {
  debug: (msg) => console.debug(`[DEBUG] token_resolver: ${msg}`),
  info: (msg) => console.info(`[INFO] token_resolver: ${msg}`),
  warn: (msg) => console.warn(`[WARN] token_resolver: ${msg}`),
  error: (msg) => console.error(`[ERROR] token_resolver: ${msg}`),
};

/**
 * Token Resolver Registry - singleton for managing token resolvers.
 */
export class TokenResolverRegistry {
  #runtimeTokens = new Map(); // Option A: setAPIToken() overrides
  #resolvers = new Map(); // Option B/C: registered resolvers
  #startupTokens = new Map(); // Cache for startup-resolved tokens

  constructor() {
    logger.debug('TokenResolverRegistry.constructor: Initializing registry');
  }

  // ========== Option A: Static Token Override ==========

  /**
   * Set a static token at runtime (Option A).
   * This takes highest priority - overrides all other methods.
   *
   * @param {string} providerName - Provider name
   * @param {string} token - Static token value
   */
  setAPIToken(providerName, token) {
    logger.info(`setAPIToken: Setting runtime token for '${providerName}'`);

    if (!providerName || typeof providerName !== 'string') {
      logger.error('setAPIToken: providerName must be a non-empty string');
      throw new Error('providerName must be a non-empty string');
    }

    if (!token || typeof token !== 'string') {
      logger.error('setAPIToken: token must be a non-empty string');
      throw new Error('token must be a non-empty string');
    }

    this.#runtimeTokens.set(providerName, token);
    logger.debug(
      `setAPIToken: Token set for '${providerName}' (length=${token.length})`
    );
  }

  /**
   * Clear a runtime token override.
   *
   * @param {string} providerName - Provider name
   */
  clearAPIToken(providerName) {
    logger.info(`clearAPIToken: Clearing runtime token for '${providerName}'`);
    const existed = this.#runtimeTokens.delete(providerName);
    logger.debug(`clearAPIToken: Token existed=${existed} for '${providerName}'`);
  }

  /**
   * Check if provider has a runtime token override.
   *
   * @param {string} providerName - Provider name
   * @returns {boolean}
   */
  hasRuntimeToken(providerName) {
    const result = this.#runtimeTokens.has(providerName);
    logger.debug(`hasRuntimeToken: '${providerName}' = ${result}`);
    return result;
  }

  // ========== Option C: Register Resolver Function (PRIMARY) ==========

  /**
   * Register a resolver function directly (Option C - PRIMARY).
   * This is the recommended approach for most use cases.
   *
   * The resolver function is called with a context object containing:
   * - tenantId: string | null
   * - userId: string | null
   * - request: any | null (Fastify request object)
   * - appState: any | null
   * - extra: object
   *
   * @param {string} providerName - Provider name
   * @param {Function} resolver - Async function: (context) => Promise<string|null>
   */
  registerResolver(providerName, resolver) {
    logger.info(`registerResolver: Registering resolver for '${providerName}'`);

    if (!providerName || typeof providerName !== 'string') {
      logger.error('registerResolver: providerName must be a non-empty string');
      throw new Error('providerName must be a non-empty string');
    }

    if (typeof resolver !== 'function') {
      logger.error('registerResolver: resolver must be a function');
      throw new Error('resolver must be a function');
    }

    this.#resolvers.set(providerName, resolver);
    logger.debug(`registerResolver: Resolver registered for '${providerName}'`);
  }

  /**
   * Unregister a resolver function.
   *
   * @param {string} providerName - Provider name
   */
  unregisterResolver(providerName) {
    logger.info(`unregisterResolver: Unregistering resolver for '${providerName}'`);
    const existed = this.#resolvers.delete(providerName);
    logger.debug(`unregisterResolver: Resolver existed=${existed} for '${providerName}'`);
  }

  /**
   * Check if provider has a registered resolver.
   *
   * @param {string} providerName - Provider name
   * @returns {boolean}
   */
  hasResolver(providerName) {
    const result =
      this.#runtimeTokens.has(providerName) || this.#resolvers.has(providerName);
    logger.debug(`hasResolver: '${providerName}' = ${result}`);
    return result;
  }

  // ========== Option B: runtime_import Loading (ADVANCED) ==========

  /**
   * Load resolvers from YAML runtime_import paths (Option B - Advanced).
   * Called during server initialization.
   *
   * Supports two formats:
   * - Object: { fastify: "path.mjs", fastapi: "module.path" }
   * - String: "path.mjs" (single platform)
   *
   * @param {Object} configStore - ConfigStore instance
   */
  async loadResolversFromConfig(configStore) {
    logger.info('loadResolversFromConfig: Loading resolvers from config');

    if (!configStore) {
      logger.warn('loadResolversFromConfig: No configStore provided');
      return;
    }

    let providers;
    try {
      providers = configStore.getNested('providers') || {};
    } catch (error) {
      logger.error(
        `loadResolversFromConfig: Failed to get providers from config: ${error.message}`
      );
      return;
    }

    const providerNames = Object.keys(providers);
    logger.debug(
      `loadResolversFromConfig: Found ${providerNames.length} providers to check`
    );

    for (const [providerName, config] of Object.entries(providers)) {
      const runtimeImport = config?.runtime_import;
      if (!runtimeImport) continue;

      // Skip if already registered via registerResolver (Option C takes priority)
      if (this.#resolvers.has(providerName)) {
        logger.debug(
          `loadResolversFromConfig: Skipping '${providerName}' - resolver already registered`
        );
        continue;
      }

      // Extract platform-specific import path
      let importPath;
      if (typeof runtimeImport === 'object' && runtimeImport.fastify) {
        importPath = runtimeImport.fastify;
        logger.debug(
          `loadResolversFromConfig: Found fastify-specific import for '${providerName}'`
        );
      } else if (typeof runtimeImport === 'string') {
        importPath = runtimeImport;
        logger.debug(
          `loadResolversFromConfig: Found string import for '${providerName}'`
        );
      }

      if (!importPath) {
        logger.debug(
          `loadResolversFromConfig: No importPath resolved for '${providerName}'`
        );
        continue;
      }

      try {
        logger.info(
          `loadResolversFromConfig: Loading resolver for '${providerName}' from ${importPath}`
        );
        const module = await import(importPath);
        const resolver = module.default || module.resolveToken;

        if (typeof resolver === 'function') {
          this.#resolvers.set(providerName, resolver);
          logger.info(
            `loadResolversFromConfig: Successfully loaded resolver for '${providerName}'`
          );
        } else {
          logger.error(
            `loadResolversFromConfig: Module for '${providerName}' does not export a resolver function`
          );
        }
      } catch (error) {
        logger.error(
          `loadResolversFromConfig: Failed to load resolver for '${providerName}': ${error.message}`
        );
      }
    }
  }

  /**
   * Resolve startup tokens for providers with token_resolver: "startup".
   * Should be called after loadResolversFromConfig or registerResolver.
   *
   * @param {Object} configStore - ConfigStore instance
   */
  async resolveStartupTokens(configStore) {
    logger.info('resolveStartupTokens: Resolving startup tokens');

    if (!configStore) {
      logger.warn('resolveStartupTokens: No configStore provided');
      return;
    }

    let providers;
    try {
      providers = configStore.getNested('providers') || {};
    } catch (error) {
      logger.error(
        `resolveStartupTokens: Failed to get providers from config: ${error.message}`
      );
      return;
    }

    for (const [providerName, config] of Object.entries(providers)) {
      if (config?.token_resolver !== 'startup') continue;

      if (!this.#resolvers.has(providerName)) {
        logger.debug(
          `resolveStartupTokens: No resolver for startup provider '${providerName}'`
        );
        continue;
      }

      try {
        logger.info(
          `resolveStartupTokens: Resolving startup token for '${providerName}'`
        );
        const resolver = this.#resolvers.get(providerName);
        const token = await resolver(null); // No context at startup

        if (token && typeof token === 'string') {
          this.#startupTokens.set(providerName, token);
          logger.info(
            `resolveStartupTokens: Startup token resolved for '${providerName}' (length=${token.length})`
          );
        } else {
          logger.warn(
            `resolveStartupTokens: Resolver for '${providerName}' returned invalid token`
          );
        }
      } catch (error) {
        logger.error(
          `resolveStartupTokens: Failed to resolve startup token for '${providerName}': ${error.message}`
        );
      }
    }
  }

  // ========== Token Resolution ==========

  /**
   * Get token for a provider.
   *
   * Resolution priority:
   * 1. Static token via setAPIToken() (Option A)
   * 2. Registered resolver (Option C) or runtime_import (Option B)
   * 3. null (fall back to env var in base class)
   *
   * @param {string} providerName - Provider name
   * @param {Object|null} context - Request context (for per-request resolution)
   * @param {Object|null} config - Provider config (contains token_resolver)
   * @returns {Promise<string|null>} Resolved token or null
   */
  async getToken(providerName, context = null, config = null) {
    logger.debug(`getToken: Resolving token for '${providerName}'`);

    // 1. Check Option A: runtime override (highest priority)
    if (this.#runtimeTokens.has(providerName)) {
      logger.debug(`getToken: Using runtime token override for '${providerName}'`);
      return this.#runtimeTokens.get(providerName);
    }

    // 2. Check resolver type from config
    const resolverType = config?.token_resolver || 'static';
    logger.debug(`getToken: resolverType='${resolverType}' for '${providerName}'`);

    // 3. For startup tokens, return cached value
    if (resolverType === 'startup') {
      const startupToken = this.#startupTokens.get(providerName) || null;
      logger.debug(
        `getToken: Returning startup token for '${providerName}' ` +
          `(found=${startupToken !== null})`
      );
      return startupToken;
    }

    // 4. For request tokens, call resolver with context
    if (resolverType === 'request' && this.#resolvers.has(providerName)) {
      logger.debug(`getToken: Calling request resolver for '${providerName}'`);
      try {
        const resolver = this.#resolvers.get(providerName);
        const token = await resolver(context);
        logger.debug(
          `getToken: Request resolver returned token for '${providerName}' ` +
            `(hasToken=${token !== null && token !== undefined})`
        );
        return token;
      } catch (error) {
        logger.error(
          `getToken: Request resolver failed for '${providerName}': ${error.message}`
        );
        return null;
      }
    }

    // 5. Static - return null to fall back to env var in base class
    logger.debug(
      `getToken: No token override for '${providerName}', ` +
        `will fall back to env var`
    );
    return null;
  }

  // ========== Utility Methods ==========

  /**
   * Get list of all providers with registered resolvers.
   *
   * @returns {string[]} Array of provider names
   */
  getRegisteredProviders() {
    const providers = new Set([
      ...this.#runtimeTokens.keys(),
      ...this.#resolvers.keys(),
    ]);
    return [...providers];
  }

  /**
   * Clear all registered resolvers and tokens.
   * Useful for testing.
   */
  clear() {
    logger.info('clear: Clearing all resolvers and tokens');
    this.#runtimeTokens.clear();
    this.#resolvers.clear();
    this.#startupTokens.clear();
  }

  /**
   * Get debug information about registry state.
   *
   * @returns {Object} Registry state info
   */
  getDebugInfo() {
    return {
      runtimeTokenCount: this.#runtimeTokens.size,
      resolverCount: this.#resolvers.size,
      startupTokenCount: this.#startupTokens.size,
      runtimeTokenProviders: [...this.#runtimeTokens.keys()],
      resolverProviders: [...this.#resolvers.keys()],
      startupTokenProviders: [...this.#startupTokens.keys()],
    };
  }
}

// Singleton instance
export const tokenRegistry = new TokenResolverRegistry();

// Convenience function (Option A API)
export function setAPIToken(providerName, token) {
  tokenRegistry.setAPIToken(providerName, token);
}

// Convenience function (Option A API)
export function clearAPIToken(providerName) {
  tokenRegistry.clearAPIToken(providerName);
}
