/**
 * Token Resolver module exports.
 *
 * Primary API (Option C - recommended):
 *   tokenRegistry.registerResolver(providerName, resolverFn)
 *
 * Override API (Option A):
 *   setAPIToken(providerName, token)
 *   clearAPIToken(providerName)
 *
 * Advanced API (Option B):
 *   tokenRegistry.loadResolversFromConfig(configStore)
 *   tokenRegistry.resolveStartupTokens(configStore)
 */

export {
  TokenResolverRegistry,
  tokenRegistry,
  setAPIToken,
  clearAPIToken,
} from './registry.mjs';
