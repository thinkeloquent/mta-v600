#!/usr/bin/env node
/**
 * Elasticsearch Health Check - Standalone debugging script
 *
 * Run directly: node elasticsearch_health_check.mjs
 *
 * Uses:
 * - static_config for YAML configuration
 * - ElasticsearchApiToken for API token resolution
 * - fetch_client for HTTP requests with proxy/auth support
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
import { ElasticsearchApiToken } from '../../api_token/index.mjs';

// ============================================================
// Fetch client with dispatcher
// ============================================================
import { createClientWithDispatcher } from '@internal/fetch-client';

export async function checkElasticsearchHealth() {
  console.log('='.repeat(60));
  console.log('ELASTICSEARCH HEALTH CHECK');
  console.log('='.repeat(60));

  // Initialize provider from static config
  const provider = new ElasticsearchApiToken(staticConfig);
  const apiKeyResult = provider.getApiKey();
  const networkConfig = provider.getNetworkConfig();
  const baseUrl = provider.getBaseUrl();

  // Debug output
  console.log('\n[Config]');
  console.log(`  Base URL: ${baseUrl}`);
  console.log(`  Has credentials: ${apiKeyResult.hasCredentials}`);
  console.log(`  Is placeholder: ${apiKeyResult.isPlaceholder}`);
  console.log(`  Auth type: ${apiKeyResult.authType}`);
  console.log(`  Header name: ${apiKeyResult.headerName}`);
  console.log(`  Username: ${apiKeyResult.username || 'N/A'}`);
  console.log('\n[Network Config]');
  console.log(`  Proxy URL: ${networkConfig.proxyUrl || 'None'}`);
  console.log(`  Cert verify: ${networkConfig.certVerify}`);

  if (!apiKeyResult.hasCredentials || apiKeyResult.isPlaceholder) {
    console.log('\n[ERROR] Missing or placeholder credentials');
    return { success: false, error: 'Missing credentials' };
  }

  if (!baseUrl) {
    console.log('\n[ERROR] No base URL configured');
    return { success: false, error: 'No base URL' };
  }

  // Create client with dispatcher (handles proxy, SSL, auth)
  console.log('\n[Creating Client]');
  console.log(`  Auth type: ${apiKeyResult.authType}`);

  const client = await createClientWithDispatcher({
    baseUrl,
    auth: {
      type: apiKeyResult.authType,
      rawApiKey: apiKeyResult.rawApiKey,  // Use raw unencoded token
      username: apiKeyResult.username,
      headerName: apiKeyResult.headerName,
    },
    headers: {
      'Accept': 'application/json',
    },
    verify: networkConfig.certVerify,
    proxy: networkConfig.proxyUrl,
  });

  // Make health check request - cluster health endpoint
  const healthEndpoint = '/_cluster/health';
  console.log('\n[Request]');
  console.log(`  GET ${baseUrl}${healthEndpoint}`);

  try {
    const response = await client.get(healthEndpoint);

    console.log('\n[Response]');
    console.log(`  Status: ${response.status}`);
    console.log(`  OK: ${response.ok}`);

    if (response.ok) {
      const data = response.data;
      const clusterName = data.cluster_name || 'N/A';
      const clusterStatus = data.status || 'unknown';
      const numberOfNodes = data.number_of_nodes || 0;
      const activeShards = data.active_shards || 0;

      console.log('\n[Cluster Info]');
      console.log(`  Cluster Name: ${clusterName}`);
      console.log(`  Status: ${clusterStatus}`);
      console.log(`  Number of Nodes: ${numberOfNodes}`);
      console.log(`  Active Shards: ${activeShards}`);

      return {
        success: true,
        message: `Connected to ${clusterName} (${clusterStatus})`,
        data: {
          clusterName,
          status: clusterStatus,
          numberOfNodes,
          activeShards,
        },
      };
    } else {
      console.log('\n[Error Response]');
      console.log(JSON.stringify(response.data, null, 2));
      return {
        success: false,
        statusCode: response.status,
        error: response.data,
      };
    }
  } catch (error) {
    console.log('\n[Exception]');
    console.log(`  ${error.name}: ${error.message}`);
    return {
      success: false,
      error: error.message,
    };
  } finally {
    await client.close?.();
  }
}

// Run if executed directly
if (process.argv[1] === __filename) {
  console.log('\n');
  const result = await checkElasticsearchHealth();
  console.log('\n' + '='.repeat(60));
  console.log('RESULT');
  console.log('='.repeat(60));
  console.log(JSON.stringify(result, null, 2));
}
