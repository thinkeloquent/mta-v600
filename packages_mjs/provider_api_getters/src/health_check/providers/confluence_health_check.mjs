#!/usr/bin/env node
/**
 * Confluence Health Check - Standalone debugging script
 *
 * Run directly: node confluence_health_check.mjs
 *
 * Uses:
 * - static_config for YAML configuration
 * - ConfluenceApiToken for API token resolution
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
import { ConfluenceApiToken } from '../../api_token/index.mjs';

// ============================================================
// Fetch client with dispatcher
// ============================================================
import { createClientWithDispatcher } from '@internal/fetch-client';

export async function checkConfluenceHealth() {
  console.log('='.repeat(60));
  console.log('CONFLUENCE HEALTH CHECK');
  console.log('='.repeat(60));

  // Initialize provider from static config
  const provider = new ConfluenceApiToken(staticConfig);
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
  console.log(`  Email: ${apiKeyResult.email || 'N/A'}`);
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
      rawApiKey: apiKeyResult.rawApiKey,  // Use raw unencoded token, not pre-encoded apiKey
      email: apiKeyResult.email,
      headerName: apiKeyResult.headerName,
    },
    headers: {
      'Accept': 'application/json',
    },
    verify: networkConfig.certVerify,
    proxy: networkConfig.proxyUrl,
  });

  // Make health check request
  const healthEndpoint = '/rest/api/user/current';
  console.log('\n[Request]');
  console.log(`  GET ${baseUrl}${healthEndpoint}`);

  try {
    const response = await client.get(healthEndpoint);

    console.log('\n[Response]');
    console.log(`  Status: ${response.status}`);
    console.log(`  OK: ${response.ok}`);

    if (response.ok) {
      const data = response.data;
      const displayName = data.displayName || 'N/A';
      const username = data.username || 'N/A';
      const email = data.email || 'N/A';

      console.log('\n[User Info]');
      console.log(`  Display Name: ${displayName}`);
      console.log(`  Username: ${username}`);
      console.log(`  Email: ${email}`);

      return {
        success: true,
        message: `Connected as ${displayName}`,
        data: {
          displayName,
          username,
          email,
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
  } finally {
    await client.close?.();
  }
}

// Run if executed directly
if (process.argv[1] === __filename) {
  console.log('\n');
  const result = await checkConfluenceHealth();
  console.log('\n' + '='.repeat(60));
  console.log('RESULT');
  console.log('='.repeat(60));
  console.log(JSON.stringify(result, null, 2));
}
