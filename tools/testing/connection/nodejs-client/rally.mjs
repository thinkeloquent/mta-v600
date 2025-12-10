#!/usr/bin/env node
/**
 * Rally API - Node.js Client Integration Test
 *
 * Authentication: Bearer Token (ZSESSIONID)
 * Base URL: https://rally1.rallydev.com/slm/webservice/v2.0
 * Health Endpoint: GET /subscription
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
const { RallyApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new RallyApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters
  RALLY_API_KEY: apiKeyResult.apiKey,
  AUTH_TYPE: apiKeyResult.authType,
  HEADER_NAME: apiKeyResult.headerName || 'ZSESSIONID',

  // Base URL (from provider or override)
  BASE_URL: provider.getBaseUrl() || 'https://rally1.rallydev.com/slm/webservice/v2.0',

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
  console.log('\n=== Rally Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('rally');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Client Factory
// ============================================================================
function createRallyClient() {
  return createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: 'custom_header',
      rawApiKey: CONFIG.RALLY_API_KEY,
      headerName: CONFIG.HEADER_NAME,
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

async function getSubscription() {
  console.log('\n=== Get Subscription ===\n');

  const client = createRallyClient();

  try {
    const response = await client.get('/subscription');

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const subscription = response.data.Subscription || {};
      console.log(`Name: ${subscription._refObjectName}`);
      console.log(`ID: ${subscription.SubscriptionID}`);
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getCurrentUser() {
  console.log('\n=== Get Current User ===\n');

  const client = createRallyClient();

  try {
    const response = await client.get('/user');

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const user = response.data.User || {};
      console.log(`Name: ${user._refObjectName}`);
      console.log(`Email: ${user.EmailAddress}`);
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function listProjects() {
  console.log('\n=== List Projects ===\n');

  const client = createRallyClient();

  try {
    const response = await client.get('/project', {
      query: { pagesize: 10, fetch: 'Name,ObjectID,State' },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const queryResult = response.data.QueryResult || {};
      const results = queryResult.Results || [];
      console.log(`Total: ${queryResult.TotalResultCount || 0}`);
      results.slice(0, 10).forEach((project) => {
        console.log(`  - ${project._refObjectName} (${project.State})`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function queryUserStories(projectId = null) {
  console.log('\n=== Query User Stories ===\n');

  const client = createRallyClient();

  const queryParams = {
    pagesize: 10,
    fetch: 'FormattedID,Name,ScheduleState,Owner',
    order: 'CreationDate desc',
  };

  if (projectId) {
    queryParams.query = `(Project.ObjectID = ${projectId})`;
  }

  try {
    const response = await client.get('/hierarchicalrequirement', {
      query: queryParams,
    });

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const queryResult = response.data.QueryResult || {};
      const results = queryResult.Results || [];
      console.log(`Total: ${queryResult.TotalResultCount || 0}`);
      results.slice(0, 10).forEach((story) => {
        const owner = story.Owner?._refObjectName || 'Unassigned';
        const name = story.Name?.slice(0, 50) || '';
        console.log(`  - ${story.FormattedID}: ${name}... (${story.ScheduleState}) - ${owner}`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function queryDefects() {
  console.log('\n=== Query Defects ===\n');

  const client = createRallyClient();

  try {
    const response = await client.get('/defect', {
      query: {
        pagesize: 10,
        fetch: 'FormattedID,Name,State,Severity,Priority,Owner',
        order: 'CreationDate desc',
      },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const queryResult = response.data.QueryResult || {};
      const results = queryResult.Results || [];
      console.log(`Total: ${queryResult.TotalResultCount || 0}`);
      results.slice(0, 10).forEach((defect) => {
        const owner = defect.Owner?._refObjectName || 'Unassigned';
        const name = defect.Name?.slice(0, 40) || '';
        console.log(`  - ${defect.FormattedID}: ${name}... (${defect.State}) - ${owner}`);
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
  console.log('Rally API Connection Test (Node.js Client Integration)');
  console.log('='.repeat(53));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`API Key: ${CONFIG.RALLY_API_KEY ? CONFIG.RALLY_API_KEY.slice(0, 10) + '...' : 'Not set'}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await getSubscription();
  // await getCurrentUser();
  // await listProjects();
  // await queryUserStories();
  // await queryDefects();
}

main().catch(console.error);
