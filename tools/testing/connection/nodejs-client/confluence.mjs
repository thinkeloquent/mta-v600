#!/usr/bin/env node
/**
 * Confluence API - Node.js Client Integration Test
 *
 * Authentication: Basic (email:api_token)
 * Base URL: https://{company}.atlassian.net/wiki
 * Health Endpoint: GET /rest/api/space
 *
 * Uses internal packages:
 *   - @internal/fetch-proxy-dispatcher: Environment-aware proxy configuration
 *   - @internal/fetch-client: HTTP client with auth support
 *   - @internal/provider_api_getters: API key resolution
 *   - @internal/app-static-config-yaml: YAML configuration loading
 */
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

// ============================================================================
// Project Setup
// ============================================================================
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..', '..');

// Load static config
const { loadYamlConfig, config: staticConfig } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'app-static-config-yaml', 'src', 'index.mjs')
);
const configDir = resolve(PROJECT_ROOT, 'common', 'config');
await loadYamlConfig({ configDir });

// Import internal packages
const { getProxyDispatcher } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'fetch-proxy-dispatcher', 'src', 'index.mts')
);
const { createClient, createClientWithDispatcher } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'fetch-client', 'src', 'index.mts')
);
const { ConfluenceApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new ConfluenceApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters
  CONFLUENCE_API_TOKEN: apiKeyResult.apiKey,
  CONFLUENCE_EMAIL: apiKeyResult.username,
  AUTH_TYPE: apiKeyResult.authType,

  // Base URL (from provider or override)
  BASE_URL: provider.getBaseUrl() || process.env.CONFLUENCE_BASE_URL || 'https://your-company.atlassian.net/wiki',

  // Dispatcher (from fetch-proxy-dispatcher) - used by createClient
  DISPATCHER: getProxyDispatcher(),

  // Proxy Configuration (set to override YAML/environment config)
  // Examples: "http://proxy:8080", "http://user:pass@proxy:8080", "socks5://proxy:1080"
  PROXY: process.env.HTTPS_PROXY || process.env.HTTP_PROXY || undefined,

  // SSL/TLS Configuration (runtime override, or undefined to use YAML config)
  SSL_VERIFY: false, // Set to undefined to use YAML config

  // Debug
  DEBUG: !['false', '0'].includes((process.env.DEBUG || '').toLowerCase()),
};

// ============================================================================
// Health Check
// ============================================================================
async function healthCheck() {
  console.log('\n=== Confluence Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('confluence');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Sample API Calls using fetch-client
// ============================================================================
async function listSpaces() {
  console.log('\n=== List Spaces ===\n');

  const client = await createClientWithDispatcher({
    baseUrl: CONFIG.BASE_URL,
    auth: {
      type: 'basic',
      apiKey: CONFIG.CONFLUENCE_API_TOKEN,
      username: CONFIG.CONFLUENCE_EMAIL,
    },
    headers: {
      Accept: 'application/json',
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });

  try {
    const response = await client.get('/rest/api/space');

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const results = response.data.results || [];
      console.log(`Found ${results.length} spaces`);
      results.slice(0, 10).forEach((space) => {
        console.log(`  - ${space.key}: ${space.name}`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getSpace(spaceKey) {
  console.log(`\n=== Get Space: ${spaceKey} ===\n`);

  const client = await createClientWithDispatcher({
    baseUrl: CONFIG.BASE_URL,
    auth: {
      type: 'basic',
      apiKey: CONFIG.CONFLUENCE_API_TOKEN,
      username: CONFIG.CONFLUENCE_EMAIL,
    },
    headers: {
      Accept: 'application/json',
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });

  try {
    const response = await client.get(`/rest/api/space/${spaceKey}`);

    console.log(`Status: ${response.status}`);
    console.log('Response:', JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function searchContent(query) {
  console.log(`\n=== Search Content: ${query} ===\n`);

  const client = await createClientWithDispatcher({
    baseUrl: CONFIG.BASE_URL,
    auth: {
      type: 'basic',
      apiKey: CONFIG.CONFLUENCE_API_TOKEN,
      username: CONFIG.CONFLUENCE_EMAIL,
    },
    headers: {
      Accept: 'application/json',
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });

  try {
    const response = await client.get('/rest/api/content/search', {
      query: { cql: query, limit: 10 },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const results = response.data.results || [];
      console.log(`Found ${results.length} results`);
      results.slice(0, 5).forEach((content) => {
        console.log(`  - ${content.title}`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getPage(pageId) {
  console.log(`\n=== Get Page: ${pageId} ===\n`);

  const client = await createClientWithDispatcher({
    baseUrl: CONFIG.BASE_URL,
    auth: {
      type: 'basic',
      apiKey: CONFIG.CONFLUENCE_API_TOKEN,
      username: CONFIG.CONFLUENCE_EMAIL,
    },
    headers: {
      Accept: 'application/json',
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });

  try {
    const response = await client.get(`/rest/api/content/${pageId}`, {
      query: { expand: 'body.storage,version' },
    });

    console.log(`Status: ${response.status}`);
    console.log('Response:', JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

// ============================================================================
// Run Tests
// ============================================================================
async function main() {
  console.log('Confluence API Connection Test (Node.js Client Integration)');
  console.log('='.repeat(58));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Email: ${CONFIG.CONFLUENCE_EMAIL}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`SSL Verify: ${CONFIG.SSL_VERIFY}`);
  console.log(`Proxy: ${CONFIG.PROXY || '(using YAML/env config)'}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await listSpaces();
  // await getSpace('MYSPACE');
  // await searchContent('type=page AND space=MYSPACE');
  // await getPage('123456');
}

main().catch(console.error);
