#!/usr/bin/env node
/**
 * Figma Health Check - Standalone debugging script with explicit 7-step pattern.
 *
 * Flow: YamlConfig -> ProviderConfig -> ProxyConfig -> AuthConfig -> RequestConfig -> Fetch -> Response
 *
 * Run directly: node figma_health_check.mjs
 *
 * Uses:
 * - static_config for YAML configuration
 * - FigmaApiToken for API token resolution
 * - fetch_client for HTTP requests with proxy/auth support
 * - authResolver for consistent auth config (SINGLE SOURCE OF TRUTH)
 */
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..', '..', '..');
const CONFIG_DIR = path.join(PROJECT_ROOT, 'common', 'config');

// ============================================================
// Load static config FIRST
// ============================================================
import { loadYamlConfig, config as staticConfig } from '@internal/app-static-config-yaml';
await loadYamlConfig({ configDir: CONFIG_DIR });

// ============================================================
// Provider API getter
// ============================================================
import { FigmaApiToken } from '../../api_token/index.mjs';

// ============================================================
// Auth resolver (SINGLE SOURCE OF TRUTH)
// ============================================================
import { resolveAuthConfig, getAuthTypeCategory } from '../../utils/authResolver.mjs';

// ============================================================
// Fetch client with dispatcher
// ============================================================
import { createClientWithDispatcher } from '@internal/fetch-client';

// ============================================================
// Console print utilities
// ============================================================
import { printSection, printJson, maskSensitive } from '@internal/console-print';

/**
 * Figma Health Check - Explicit 7-step building block pattern.
 *
 * Flow: YamlConfig -> ProviderConfig -> ProxyConfig -> AuthConfig -> RequestConfig -> Fetch -> Response
 *
 * This pattern is identical across:
 * - FastAPI endpoints
 * - Fastify endpoints
 * - Standalone scripts (this file)
 * - CLI tools
 * - SDKs
 *
 * @param {Object} config - Configuration store (if null, uses staticConfig)
 * @returns {Promise<Object>} Health check result with success status, data/error, and configUsed metadata
 */
export async function checkFigmaHealth(config = null) {
  // ============================================================
  // Step 1: YAML CONFIG LOADING
  // ============================================================
  printSection('1. YAML CONFIG LOADING');

  if (!config) {
    config = staticConfig;
  }

  const configSource = config._source || 'unknown';
  console.log(`  Loaded from: ${configSource}`);

  // ============================================================
  // Step 2: PROVIDER CONFIG EXTRACTION
  // ============================================================
  printSection('2. PROVIDER CONFIG EXTRACTION');

  const provider = new FigmaApiToken(config);

  const providerConfig = {
    providerName: provider.providerName,
    baseUrl: provider.getBaseUrl(),
    healthEndpoint: provider.healthEndpoint,
    authType: provider.getAuthType(),
    headerName: provider.getHeaderName(),
  };
  printJson(providerConfig);

  // Early exit if missing critical config
  if (!providerConfig.baseUrl) {
    return {
      success: false,
      error: 'No base URL configured',
      configUsed: { provider: providerConfig },
    };
  }

  // ============================================================
  // Step 3: PROXY CONFIG RESOLUTION
  // ============================================================
  printSection('3. PROXY CONFIG RESOLUTION');

  const networkConfig = provider.getNetworkConfig();

  const proxyConfig = {
    proxyUrl: networkConfig.proxyUrl,
    certVerify: networkConfig.certVerify,
    caBundle: networkConfig.caBundle,
    agentProxy: networkConfig.agentProxy,
  };
  printJson(proxyConfig);

  // ============================================================
  // Step 4: AUTH CONFIG RESOLUTION (uses shared utility)
  // ============================================================
  printSection('4. AUTH CONFIG RESOLUTION');

  const apiKeyResult = provider.getApiKey();

  console.log(`  Has credentials: ${apiKeyResult.hasCredentials}`);
  console.log(`  Is placeholder: ${apiKeyResult.isPlaceholder}`);

  if (!apiKeyResult.hasCredentials || apiKeyResult.isPlaceholder) {
    return {
      success: false,
      error: 'Missing or placeholder credentials',
      configUsed: {
        provider: providerConfig,
        proxy: proxyConfig,
      },
    };
  }

  // Use shared auth resolver (SINGLE SOURCE OF TRUTH)
  const authType = provider.getAuthType();
  const headerName = provider.getHeaderName();
  const authConfig = resolveAuthConfig(authType, apiKeyResult, headerName);
  const authCategory = getAuthTypeCategory(authType);

  console.log(`  Provider authType: ${authType}`);
  console.log(`  Auth category: ${authCategory}`);
  console.log(`  Resolved to: type=${authConfig.type}`);
  console.log(`  Header: ${authConfig.headerName || 'Authorization'}`);
  console.log(`  API key: ${maskSensitive(authConfig.rawApiKey)}`);

  // ============================================================
  // Step 5: REQUEST CONFIG
  // ============================================================
  printSection('5. REQUEST CONFIG');

  const requestConfig = {
    method: 'GET',
    url: `${providerConfig.baseUrl}${providerConfig.healthEndpoint}`,
    headers: provider.getHeadersConfig() || {},
    timeout: 30000,
  };

  // Figma-specific headers
  requestConfig.headers = {
    ...requestConfig.headers,
    'Accept': 'application/json',
  };

  printJson(requestConfig);

  // ============================================================
  // Step 6: FETCH (with all configs applied)
  // ============================================================
  printSection('6. FETCH');

  console.log('  Creating client with dispatcher...');
  console.log(`  Base URL: ${providerConfig.baseUrl}`);
  console.log(`  Auth type: ${authConfig.type}`);
  console.log(`  Proxy: ${proxyConfig.proxyUrl || 'None'}`);
  console.log(`  Verify SSL: ${proxyConfig.certVerify}`);

  const client = await createClientWithDispatcher({
    baseUrl: providerConfig.baseUrl,
    auth: authConfig,
    headers: requestConfig.headers,
    verify: proxyConfig.certVerify,
    proxy: proxyConfig.proxyUrl,
  });

  const startTime = performance.now();

  let response;
  try {
    console.log('\n  Sending request...');
    console.log(`  GET ${requestConfig.url}`);
    response = await client.get(providerConfig.healthEndpoint);
  } finally {
    await client.close?.();
  }

  const latencyMs = performance.now() - startTime;

  // ============================================================
  // Step 7: RESPONSE HANDLING
  // ============================================================
  printSection('7. RESPONSE HANDLING');

  console.log(`  Status: ${response.status}`);
  console.log(`  OK: ${response.ok}`);
  console.log(`  Latency: ${latencyMs.toFixed(2)}ms`);

  // Build configUsed for debugging
  const configUsed = {
    provider: providerConfig,
    proxy: proxyConfig,
    authType,
    authCategory,
  };

  if (response.ok) {
    const data = response.data;
    const userId = data.id || 'N/A';
    const handle = data.handle || 'N/A';
    const email = data.email || 'N/A';
    const imgUrl = data.img_url || 'N/A';

    console.log('\n  [User Info]');
    console.log(`  User ID: ${userId}`);
    console.log(`  Handle: ${handle}`);
    console.log(`  Email: ${email}`);
    console.log(`  Avatar: ${imgUrl}`);

    return {
      success: true,
      message: `Connected as ${handle}`,
      data: {
        id: userId,
        handle,
        email,
        imgUrl,
      },
      latencyMs,
      configUsed,
    };
  } else {
    console.log('\n  [Error Response]');
    printJson(response.data);

    return {
      success: false,
      statusCode: response.status,
      error: response.data,
      latencyMs,
      configUsed,
    };
  }
}

// Run if executed directly
if (process.argv[1] === __filename) {
  console.log('\n');
  console.log('='.repeat(60));
  console.log('FIGMA HEALTH CHECK - Explicit 7-Step Pattern');
  console.log('='.repeat(60));
  console.log('Flow: YamlConfig -> Provider -> Proxy -> Auth -> Request -> Fetch -> Response');

  const result = await checkFigmaHealth();

  console.log('\n' + '='.repeat(60));
  console.log('FINAL RESULT');
  console.log('='.repeat(60));
  console.log(JSON.stringify(result, null, 2));
}
