#!/usr/bin/env node
/**
 * SauceLabs API - Node.js Client Integration Test
 *
 * Authentication: Basic (username:access_key)
 * Base URL: https://api.{region}.saucelabs.com
 * Health Endpoint: GET /rest/v1.2/users/{username}
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
const { SaucelabsApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new SaucelabsApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters
  SAUCELABS_ACCESS_KEY: apiKeyResult.apiKey,
  SAUCELABS_USERNAME: apiKeyResult.username || process.env.SAUCE_USERNAME || '',
  AUTH_TYPE: apiKeyResult.authType,

  // Base URL (from provider or override)
  BASE_URL: provider.getBaseUrl() || process.env.SAUCELABS_BASE_URL || 'https://api.us-west-1.saucelabs.com',

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
  console.log('\n=== SauceLabs Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('saucelabs');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Client Factory
// ============================================================================
function createSaucelabsClient() {
  return createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: 'basic',
      rawApiKey: CONFIG.SAUCELABS_ACCESS_KEY,
      username: CONFIG.SAUCELABS_USERNAME,
    },
    headers: {
      Accept: 'application/json',
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });
}

// ============================================================================
// Sample API Calls using fetch-client
// ============================================================================
async function getUser() {
  console.log('\n=== Get User Info ===\n');

  const client = createSaucelabsClient();

  try {
    const response = await client.get(`/rest/v1.2/users/${CONFIG.SAUCELABS_USERNAME}`);

    console.log(`Status: ${response.status}`);
    console.log('Response:', JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function listJobs(limit = 10) {
  console.log(`\n=== List Jobs (limit: ${limit}) ===\n`);

  const client = createSaucelabsClient();

  try {
    const response = await client.get(`/rest/v1.1/${CONFIG.SAUCELABS_USERNAME}/jobs`, {
      query: { limit },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok && Array.isArray(response.data)) {
      console.log(`Found ${response.data.length} jobs`);
      response.data.slice(0, 5).forEach((job) => {
        console.log(`  - ${job.id}: ${job.name} (${job.status})`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getJob(jobId) {
  console.log(`\n=== Get Job: ${jobId} ===\n`);

  const client = createSaucelabsClient();

  try {
    const response = await client.get(`/rest/v1.1/${CONFIG.SAUCELABS_USERNAME}/jobs/${jobId}`);

    console.log(`Status: ${response.status}`);
    console.log('Response:', JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getUsage() {
  console.log('\n=== Get Usage Statistics ===\n');

  const client = createSaucelabsClient();

  try {
    const response = await client.get(`/rest/v1.2/users/${CONFIG.SAUCELABS_USERNAME}/concurrency`);

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
  console.log('SauceLabs API Connection Test (Node.js Client Integration)');
  console.log('='.repeat(57));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Username: ${CONFIG.SAUCELABS_USERNAME}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await getUser();
  // await listJobs(5);
  // await getJob('your_job_id');
  // await getUsage();
}

main().catch(console.error);
