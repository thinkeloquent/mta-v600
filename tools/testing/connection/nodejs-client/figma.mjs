#!/usr/bin/env node
/**
 * Figma API - Node.js Client Integration Test
 *
 * Authentication: X-Figma-Token header
 * Base URL: https://api.figma.com
 * Health Endpoint: GET /v1/me
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
const { FigmaApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new FigmaApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters
  FIGMA_TOKEN: apiKeyResult.apiKey,
  AUTH_TYPE: apiKeyResult.authType,
  HEADER_NAME: apiKeyResult.headerName || 'X-Figma-Token',

  // Base URL (from provider or override)
  BASE_URL: provider.getBaseUrl() || 'https://api.figma.com',

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
  console.log('\n=== Figma Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('figma');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Client Factory
// ============================================================================
function createFigmaClient() {
  return createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: 'custom_header',
      rawApiKey: CONFIG.FIGMA_TOKEN,
      headerName: CONFIG.HEADER_NAME,
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });
}

// ============================================================================
// Sample API Calls using fetch-client
// ============================================================================
async function getMe() {
  console.log('\n=== Get Current User ===\n');

  const client = createFigmaClient();

  try {
    const response = await client.get('/v1/me');

    console.log(`Status: ${response.status}`);
    console.log('Response:', JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getFile(fileKey) {
  console.log(`\n=== Get File: ${fileKey} ===\n`);

  const client = createFigmaClient();

  try {
    const response = await client.get(`/v1/files/${fileKey}`);

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      console.log(`File name: ${response.data.name}`);
      console.log(`Last modified: ${response.data.lastModified}`);
      console.log(`Version: ${response.data.version}`);
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getFileNodes(fileKey, nodeIds) {
  console.log(`\n=== Get File Nodes: ${fileKey} ===\n`);

  const client = createFigmaClient();

  try {
    const response = await client.get(`/v1/files/${fileKey}/nodes`, {
      query: { ids: nodeIds.join(',') },
    });

    console.log(`Status: ${response.status}`);
    console.log('Response:', JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getTeamProjects(teamId) {
  console.log(`\n=== Get Team Projects: ${teamId} ===\n`);

  const client = createFigmaClient();

  try {
    const response = await client.get(`/v1/teams/${teamId}/projects`);

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      const projects = response.data.projects || [];
      console.log(`Found ${projects.length} projects`);
      projects.slice(0, 10).forEach((project) => {
        console.log(`  - ${project.name} (id: ${project.id})`);
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
  console.log('Figma API Connection Test (Node.js Client Integration)');
  console.log('='.repeat(53));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Token: ${CONFIG.FIGMA_TOKEN ? CONFIG.FIGMA_TOKEN.slice(0, 10) + '...' : 'Not set'}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`Header: ${CONFIG.HEADER_NAME}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await getMe();
  // await getFile('your_file_key');
  // await getFileNodes('your_file_key', ['0:1', '0:2']);
  // await getTeamProjects('your_team_id');
}

main().catch(console.error);
