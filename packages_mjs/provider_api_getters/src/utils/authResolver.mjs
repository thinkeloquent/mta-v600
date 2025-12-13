/**
 * Auth Config Resolution Utility.
 *
 * This is the SINGLE SOURCE OF TRUTH for auth type interpretation.
 * Used by: factory.mjs, all standalone health check scripts, CLI tools, SDKs.
 *
 * The auth resolution logic determines how to configure fetch_client based on
 * the provider's api_auth_type from YAML config.
 */

/**
 * Resolve auth configuration from provider auth_type.
 *
 * This function determines how to configure fetch_client's auth based on
 * the provider's api_auth_type setting.
 *
 * Auth Type Categories:
 * ---------------------
 * 1. Raw Passthrough Types ("custom", "x-api-key"):
 *    - Pass the raw API key value with a custom header
 *    - Header name comes from provider config
 *    - fetch_client uses the value as-is
 *
 * 2. Bearer Types ("bearer", "bearer_*"):
 *    - Pass the raw token value
 *    - fetch_client automatically adds "Bearer " prefix
 *    - Uses standard Authorization header
 *
 * 3. Pre-computed Types (all others - "basic", "basic_email_token", etc.):
 *    - Provider has already computed the full header value
 *    - e.g., "Basic base64(email:token)"
 *    - Pass as custom type with the pre-computed value
 *
 * @param {string} authType - The api_auth_type from provider YAML config
 * @param {Object} apiKeyResult - ApiKeyResult from provider.getApiKey()
 * @param {string} [headerName] - Header name from provider.getHeaderName()
 * @returns {Object} Auth config object with keys: type, rawApiKey, headerName (optional)
 *
 * @example
 * const auth = resolveAuthConfig('bearer', apiKeyResult, 'Authorization');
 * const client = createClient({ auth, ... });
 */
export function resolveAuthConfig(authType, apiKeyResult, headerName = null) {
  // Category 1: Raw passthrough - value used as-is with custom header
  const rawPassthroughTypes = new Set(['custom', 'custom_header', 'x-api-key']);

  // Category 2: Bearer types - fetch_client adds "Bearer " prefix
  const isBearerType = authType === 'bearer' || authType.startsWith('bearer_');

  if (rawPassthroughTypes.has(authType)) {
    // Use rawApiKey if available, fallback to apiKey
    const rawKey = apiKeyResult.rawApiKey || apiKeyResult.apiKey || '';
    return {
      type: 'custom',
      rawApiKey: rawKey,
      headerName: headerName || 'Authorization',
    };
  }

  if (isBearerType) {
    // Bearer auth: pass raw token, fetch_client adds "Bearer " prefix
    const rawKey = apiKeyResult.rawApiKey || apiKeyResult.apiKey || '';
    const computedKey = apiKeyResult.apiKey || '';

    // Guard: If computedKey already starts with "Basic ", the YAML config is wrong
    // The provider computed Basic auth but config says bearer - use the computed value
    if (computedKey && computedKey.startsWith('Basic ')) {
      console.warn(
        `[AUTH] resolveAuthConfig: Config mismatch! authType='${authType}' but ` +
        `provider computed Basic auth. Using pre-computed value instead.`
      );
      return {
        type: 'custom',
        rawApiKey: computedKey,
        headerName: headerName || 'Authorization',
      };
    }

    return {
      type: 'bearer',
      rawApiKey: rawKey,
    };
  }

  // Pre-computed value (e.g., "Basic base64(email:token)")
  // Use apiKey (not rawApiKey) as it contains the full computed value
  const computedKey = apiKeyResult.apiKey || '';
  return {
    type: 'custom',
    rawApiKey: computedKey,
    headerName: headerName || 'Authorization',
  };
}

/**
 * Get the category of an auth type for debugging/logging.
 *
 * @param {string} authType - The api_auth_type from provider YAML config
 * @returns {string} Category string: "raw_passthrough", "bearer", or "pre_computed"
 */
export function getAuthTypeCategory(authType) {
  const rawPassthroughTypes = new Set(['custom', 'custom_header', 'x-api-key']);
  const isBearerType = authType === 'bearer' || authType.startsWith('bearer_');

  if (rawPassthroughTypes.has(authType)) {
    return 'raw_passthrough';
  }
  if (isBearerType) {
    return 'bearer';
  }
  return 'pre_computed';
}

/**
 * Format auth config for debug logging (masks sensitive values).
 *
 * @param {Object} authConfig - Auth config object
 * @param {string} providerAuthType - Original provider auth type
 * @returns {Object} Safe-to-log representation
 */
export function formatAuthConfigForDebug(authConfig, providerAuthType) {
  const masked = authConfig.rawApiKey
    ? authConfig.rawApiKey.substring(0, 10) + '***'
    : '<none>';

  return {
    provider_auth_type: providerAuthType,
    resolved_type: authConfig.type,
    header_name: authConfig.headerName || 'Authorization',
    category: getAuthTypeCategory(providerAuthType),
    raw_api_key: masked,
  };
}
