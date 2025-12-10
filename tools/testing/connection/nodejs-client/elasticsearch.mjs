#!/usr/bin/env node
/**
 * Elasticsearch API - Node.js Client Integration Test
 *
 * Authentication: Basic (username:password) or API Key
 * Base URL: https://{host}:{port}
 * Health Endpoint: GET /
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
const { createClient } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'fetch-client', 'src', 'index.mts')
);
const { ElasticsearchApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new ElasticsearchApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters
  ES_API_KEY: apiKeyResult.apiKey,
  ES_USERNAME: apiKeyResult.username,
  AUTH_TYPE: apiKeyResult.authType,

  // Base URL (from provider or override)
  BASE_URL: provider.getBaseUrl() || process.env.ELASTICSEARCH_URL || 'http://localhost:9200',

  // Dispatcher (from fetch-proxy-dispatcher)
  DISPATCHER: getProxyDispatcher(),

  // Proxy Configuration (set to override YAML/environment config)
  PROXY: process.env.HTTPS_PROXY || process.env.HTTP_PROXY || undefined,

  // SSL/TLS Configuration (runtime override, or undefined to use YAML config)
  SSL_VERIFY: false,  // Set to undefined to use YAML config

  // Debug
  DEBUG: !['false', '0'].includes((process.env.DEBUG || '').toLowerCase()),
};

// ============================================================================
// Health Check
// ============================================================================
async function healthCheck() {
  console.log('\n=== Elasticsearch Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('elasticsearch');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Sample API Calls using fetch-client
// ============================================================================
function createEsClient(headers = { Accept: 'application/json' }) {
  const authConfig =
    CONFIG.AUTH_TYPE === 'bearer'
      ? { type: 'bearer', rawApiKey: CONFIG.ES_API_KEY }
      : { type: 'basic', rawApiKey: CONFIG.ES_API_KEY, username: CONFIG.ES_USERNAME };

  return createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: authConfig,
    headers,
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });
}

async function getClusterInfo() {
  console.log('\n=== Get Cluster Info ===\n');

  const client = createEsClient();

  try {
    const response = await client.get('/');

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      console.log(`Name: ${response.data.name}`);
      console.log(`Cluster: ${response.data.cluster_name}`);
      console.log(`Version: ${response.data.version?.number}`);
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getClusterHealth() {
  console.log('\n=== Get Cluster Health ===\n');

  const client = createEsClient();

  try {
    const response = await client.get('/_cluster/health');

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      console.log(`Cluster: ${response.data.cluster_name}`);
      console.log(`Health: ${response.data.status}`);
      console.log(`Nodes: ${response.data.number_of_nodes}`);
      console.log(`Data Nodes: ${response.data.number_of_data_nodes}`);
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function listIndices() {
  console.log('\n=== List Indices ===\n');

  const client = createEsClient();

  try {
    const response = await client.get('/_cat/indices', {
      query: { format: 'json' },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok && Array.isArray(response.data)) {
      console.log(`Found ${response.data.length} indices`);
      response.data.slice(0, 10).forEach((idx) => {
        console.log(`  - ${idx.index}: ${idx['docs.count']} docs (${idx['store.size']})`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function searchIndex(index, query) {
  console.log(`\n=== Search Index: ${index} ===\n`);

  const client = createEsClient();

  try {
    const response = await client.post(`/${index}/_search`, {
      json: query,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const hits = response.data.hits || {};
      console.log(`Total hits: ${hits.total?.value || 0}`);
      (hits.hits || []).slice(0, 5).forEach((hit) => {
        console.log(`  - ${hit._id}:`, hit._source);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

// ============================================================================
// Run Tests
// ============================================================================
async function main() {
  console.log('Elasticsearch API Connection Test (Node.js Client Integration)');
  console.log('='.repeat(61));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Username: ${CONFIG.ES_USERNAME}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await getClusterInfo();
  // await getClusterHealth();
  // await listIndices();
  // await searchIndex('my-index', { query: { match_all: {} } });
}

main().catch(console.error);
