/**
 * Fastify Integration Example for Token Resolver
 *
 * This file demonstrates how to integrate the token_resolver registry
 * with a Fastify server for dynamic API token management.
 *
 * Usage Patterns:
 * - Option A: setAPIToken() for runtime token overrides (testing/debugging)
 * - Option C: registerResolver() for programmatic token resolution (PRIMARY)
 * - Option B: loadResolversFromConfig() for YAML-based dynamic imports (ADVANCED)
 */

import Fastify from 'fastify';
import {
  tokenRegistry,
  setAPIToken,
  clearAPIToken,
  RequestContext,
} from '@internal/provider-api-getters';

// ============================================================
// Example 1: Option A - Static Runtime Token Override
// Use this for testing, debugging, or when tokens are known at startup
// ============================================================

/**
 * Set a static token override (highest priority).
 * This is useful for:
 * - Testing with known tokens
 * - Debugging with override tokens
 * - Simple single-tenant deployments
 */
function setupStaticTokenOverride() {
  console.log('[INFO] Setting up static token override (Option A)');

  // Set a static token - this takes highest priority
  setAPIToken('github', process.env.GITHUB_TOKEN || 'ghp_test_token');

  // Can be cleared later if needed
  // clearAPIToken('github');
}

// ============================================================
// Example 2: Option C - Register Resolver Functions (PRIMARY)
// Use this for most production scenarios with dynamic tokens
// ============================================================

/**
 * OAuth token resolver example.
 * Refreshes OAuth tokens on-demand for each request.
 *
 * @param {RequestContext} context - Request context with tenant/user info
 * @returns {Promise<string|null>} Resolved token or null
 */
async function oauthTokenResolver(context) {
  console.log('[DEBUG] OAuth resolver called', {
    tenantId: context?.tenantId,
    userId: context?.userId,
  });

  // Example: Fetch refresh token from database and exchange for access token
  if (!context?.tenantId) {
    console.warn('[WARN] No tenant ID in context, cannot resolve OAuth token');
    return null;
  }

  try {
    // Simulate OAuth token refresh
    // In production, this would:
    // 1. Look up refresh token from database by tenant ID
    // 2. Call OAuth provider to exchange for access token
    // 3. Cache the access token with TTL

    const mockAccessToken = `oauth_access_${context.tenantId}_${Date.now()}`;
    console.log('[DEBUG] OAuth token resolved', {
      tenantId: context.tenantId,
      tokenLength: mockAccessToken.length,
    });
    return mockAccessToken;
  } catch (error) {
    console.error('[ERROR] OAuth token resolution failed', {
      tenantId: context.tenantId,
      error: error.message,
    });
    return null;
  }
}

/**
 * JWT generator example.
 * Generates short-lived JWTs for service-to-service auth.
 *
 * @param {RequestContext} context - Request context
 * @returns {Promise<string>} Generated JWT
 */
async function jwtTokenResolver(context) {
  console.log('[DEBUG] JWT resolver called');

  // Example: Generate a JWT for internal service auth
  // In production, this would use a proper JWT library

  const payload = {
    iss: 'main-entry-fastify',
    sub: context?.userId || 'anonymous',
    aud: 'internal-api',
    exp: Math.floor(Date.now() / 1000) + 3600, // 1 hour
  };

  // Mock JWT (in production, use jose or similar)
  const mockJwt = `eyJ.${Buffer.from(JSON.stringify(payload)).toString('base64')}.sig`;
  return mockJwt;
}

/**
 * Setup resolver functions at server startup.
 * This is the PRIMARY recommended approach for most use cases.
 */
function setupResolverFunctions() {
  console.log('[INFO] Setting up resolver functions (Option C - PRIMARY)');

  // Register OAuth resolver for providers that need per-request tokens
  tokenRegistry.registerResolver('salesforce', oauthTokenResolver);
  tokenRegistry.registerResolver('hubspot', oauthTokenResolver);

  // Register JWT resolver for internal services
  tokenRegistry.registerResolver('internal_api', jwtTokenResolver);

  console.log('[INFO] Registered resolvers:', tokenRegistry.getRegisteredProviders());
}

// ============================================================
// Example 3: Option B - Load Resolvers from YAML (ADVANCED)
// Use this for modular/plugin architectures
// ============================================================

/**
 * Load resolvers from YAML configuration.
 * This is an ADVANCED pattern for modular architectures.
 *
 * Requires runtime_import in YAML config:
 * ```yaml
 * providers:
 *   custom_oauth_provider:
 *     token_resolver: "request"
 *     runtime_import:
 *       fastify: "@myapp/resolvers/oauth.mjs"
 * ```
 *
 * @param {Object} configStore - ConfigStore instance from @internal/app-static-config-yaml
 */
async function setupResolversFromConfig(configStore) {
  console.log('[INFO] Loading resolvers from YAML config (Option B - ADVANCED)');

  // Load resolvers from runtime_import paths in YAML
  await tokenRegistry.loadResolversFromConfig(configStore);

  // Resolve startup tokens for providers with token_resolver: "startup"
  await tokenRegistry.resolveStartupTokens(configStore);

  console.log('[INFO] Loaded resolvers:', tokenRegistry.getRegisteredProviders());
}

// ============================================================
// Fastify Plugin Integration
// ============================================================

/**
 * Fastify plugin for token resolver integration.
 *
 * This plugin:
 * 1. Decorates fastify with the token registry
 * 2. Adds a request decorator for creating RequestContext
 * 3. Provides hooks for per-request token resolution
 *
 * @param {FastifyInstance} fastify - Fastify instance
 * @param {Object} options - Plugin options
 */
async function tokenResolverPlugin(fastify, options = {}) {
  console.log('[INFO] Registering token resolver plugin');

  // Decorate fastify with the token registry
  fastify.decorate('tokenRegistry', tokenRegistry);

  // Decorate request with a helper to create RequestContext
  fastify.decorateRequest('getTokenContext', function () {
    // Extract tenant/user from request (customize based on your auth system)
    return new RequestContext({
      tenantId: this.headers['x-tenant-id'] || null,
      userId: this.user?.id || null,
      request: this,
      appState: fastify,
      extra: {
        ip: this.ip,
        userAgent: this.headers['user-agent'],
      },
    });
  });

  // Add hook to log token resolution for debugging
  if (options.debug) {
    fastify.addHook('onRequest', async (request, reply) => {
      console.log('[DEBUG] Request context:', {
        url: request.url,
        tenantId: request.headers['x-tenant-id'],
        hasTokenRegistry: !!fastify.tokenRegistry,
      });
    });
  }

  console.log('[INFO] Token resolver plugin registered');
}

// ============================================================
// Example Server Setup
// ============================================================

/**
 * Create and configure the Fastify server with token resolver.
 */
async function createServer() {
  const fastify = Fastify({
    logger: {
      level: 'info',
      transport: {
        target: 'pino-pretty',
        options: { colorize: true },
      },
    },
  });

  // ============================================================
  // Setup Token Resolution (choose one or combine)
  // ============================================================

  // Option A: Static token override (for testing)
  if (process.env.USE_STATIC_TOKENS === 'true') {
    setupStaticTokenOverride();
  }

  // Option C: Register resolver functions (PRIMARY - recommended)
  setupResolverFunctions();

  // Option B: Load from YAML config (ADVANCED)
  // const { config } = await import('@internal/app-static-config-yaml');
  // await setupResolversFromConfig(config);

  // ============================================================
  // Register Plugins
  // ============================================================

  await fastify.register(tokenResolverPlugin, {
    debug: process.env.NODE_ENV !== 'production',
  });

  // ============================================================
  // Example Routes Using Token Resolver
  // ============================================================

  // Health check for token resolver
  fastify.get('/healthz/token-resolver', async (request, reply) => {
    const debugInfo = fastify.tokenRegistry.getDebugInfo();
    return {
      status: 'ok',
      registeredProviders: debugInfo.resolverProviders,
      runtimeTokens: debugInfo.runtimeTokenProviders,
      startupTokens: debugInfo.startupTokenProviders,
    };
  });

  // Example: Get token for a provider (debugging endpoint)
  fastify.get('/api/debug/token/:provider', async (request, reply) => {
    const { provider } = request.params;
    const context = request.getTokenContext();

    try {
      // Get provider config from static config
      const providerConfig = { token_resolver: 'request' }; // Simplified

      const token = await fastify.tokenRegistry.getToken(provider, context, providerConfig);

      return {
        provider,
        hasToken: token !== null,
        tokenLength: token?.length || 0,
        context: {
          tenantId: context.tenantId,
          userId: context.userId,
        },
      };
    } catch (error) {
      return reply.status(500).send({
        error: 'Token resolution failed',
        message: error.message,
      });
    }
  });

  // Example: Admin endpoint to set/clear runtime tokens
  fastify.post('/api/admin/token/:provider', async (request, reply) => {
    const { provider } = request.params;
    const { token, action } = request.body || {};

    if (action === 'clear') {
      clearAPIToken(provider);
      return { status: 'cleared', provider };
    }

    if (token) {
      setAPIToken(provider, token);
      return { status: 'set', provider, tokenLength: token.length };
    }

    return reply.status(400).send({ error: 'Missing token or action' });
  });

  return fastify;
}

// ============================================================
// Main Entry Point
// ============================================================

if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    const fastify = await createServer();
    await fastify.listen({ port: 3000, host: '0.0.0.0' });
    console.log(`
╔══════════════════════════════════════════════════════════════╗
║           Token Resolver Integration Example                  ║
╠══════════════════════════════════════════════════════════════╣
║  Server: http://localhost:3000                               ║
║                                                              ║
║  Endpoints:                                                  ║
║    GET  /healthz/token-resolver    - Registry status         ║
║    GET  /api/debug/token/:provider - Get token for provider  ║
║    POST /api/admin/token/:provider - Set/clear token         ║
╚══════════════════════════════════════════════════════════════╝
    `);
  } catch (err) {
    console.error('Failed to start server:', err);
    process.exit(1);
  }
}

export { createServer, tokenResolverPlugin, setupResolverFunctions };
