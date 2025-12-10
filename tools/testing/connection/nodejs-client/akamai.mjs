#!/usr/bin/env node
/**
 * Akamai Edge API - Node.js Client Integration Test
 *
 * Authentication: EdgeGrid (signature-based)
 * Base URL: https://<host>.luna.akamaiapis.net
 * Health Endpoint: GET /-/client-api/active-grants/implicit
 *
 * Uses internal packages:
 *   - @internal/fetch-proxy-dispatcher: Environment-aware proxy configuration
 *   - @internal/fetch-client: HTTP client with auth support
 *   - @internal/provider_api_getters: API key resolution (EdgeGrid credentials)
 *   - @internal/app-static-config-yaml: YAML configuration loading
 *
 * API Documentation:
 *   https://techdocs.akamai.com/developer/docs/authenticate-with-edgegrid
 *
 * EdgeGrid Authentication:
 *   Akamai uses signature-based authentication. Each request must include
 *   an Authorization header with a signature computed from:
 *   - client_token, client_secret, access_token
 *   - Request method, path, headers, and body
 *
 * Note: This test file uses the akamai-edgegrid package for signature generation.
 * Install with: npm install akamai-edgegrid
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
const { AkamaiApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new AkamaiApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();
const credentials = provider.getCredentials();

const CONFIG = {
  // From provider_api_getters (EdgeGrid credentials)
  CLIENT_TOKEN: credentials.clientToken,
  CLIENT_SECRET: credentials.clientSecret,
  ACCESS_TOKEN: credentials.accessToken,
  HOST: credentials.host,
  AUTH_TYPE: apiKeyResult.authType,
  HAS_CREDENTIALS: apiKeyResult.hasCredentials,

  // Base URL (derived from host)
  BASE_URL: provider.getBaseUrl(),

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
// EdgeGrid Authentication Helper
// ============================================================================
async function getEdgeGridAuth() {
  /**
   * Create EdgeGrid authentication object.
   *
   * Requires: npm install akamai-edgegrid
   */
  try {
    const { default: EdgeGrid } = await import('akamai-edgegrid');

    if (!CONFIG.HAS_CREDENTIALS) {
      console.log('Error: EdgeGrid credentials not found.');
      console.log('Set AKAMAI_CLIENT_TOKEN, AKAMAI_CLIENT_SECRET, AKAMAI_ACCESS_TOKEN, AKAMAI_HOST');
      console.log('Or create ~/.edgerc file with [default] section.');
      return null;
    }

    return new EdgeGrid(
      CONFIG.CLIENT_TOKEN,
      CONFIG.CLIENT_SECRET,
      CONFIG.ACCESS_TOKEN,
      CONFIG.HOST
    );
  } catch (e) {
    if (e.code === 'ERR_MODULE_NOT_FOUND') {
      console.log('Error: akamai-edgegrid package not installed.');
      console.log('Install with: npm install akamai-edgegrid');
    } else {
      console.log(`Error loading EdgeGrid: ${e.message}`);
    }
    return null;
  }
}

function createAkamaiClient() {
  return createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: 'custom',  // EdgeGrid requires custom signing per request
      rawApiKey: '',  // Not used directly, signing handled separately
    },
    headers: {
      Accept: 'application/json',
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });
}

// ============================================================================
// Health Check
// ============================================================================
async function healthCheck() {
  console.log('\n=== Akamai Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('akamai');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Sample API Calls using EdgeGrid auth
// ============================================================================
async function getActiveGrants() {
  console.log('\n=== Get Active Grants ===\n');

  const eg = await getEdgeGridAuth();
  if (!eg) {
    return { success: false, error: 'No EdgeGrid auth' };
  }

  return new Promise((resolve) => {
    eg.auth({
      path: '/-/client-api/active-grants/implicit',
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    eg.send((error, response, body) => {
      if (error) {
        console.log(`Error: ${error.message}`);
        resolve({ success: false, error: error.message });
        return;
      }

      console.log(`Status: ${response.statusCode}`);
      try {
        const data = JSON.parse(body);
        console.log('Response:', JSON.stringify(data, null, 2));
        resolve({ success: response.statusCode >= 200 && response.statusCode < 300, data });
      } catch (e) {
        console.log('Response:', body);
        resolve({ success: false, error: 'Failed to parse response' });
      }
    });
  });
}

async function getContracts() {
  console.log('\n=== Get Contracts ===\n');

  const eg = await getEdgeGridAuth();
  if (!eg) {
    return { success: false, error: 'No EdgeGrid auth' };
  }

  return new Promise((resolve) => {
    eg.auth({
      path: '/papi/v1/contracts',
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    eg.send((error, response, body) => {
      if (error) {
        console.log(`Error: ${error.message}`);
        resolve({ success: false, error: error.message });
        return;
      }

      console.log(`Status: ${response.statusCode}`);
      try {
        const data = JSON.parse(body);
        const contracts = data.contracts?.items || [];
        console.log(`Found ${contracts.length} contracts`);
        contracts.slice(0, 5).forEach((contract) => {
          console.log(`  - ${contract.contractId}: ${contract.contractTypeName}`);
        });
        resolve({ success: response.statusCode >= 200 && response.statusCode < 300, data });
      } catch (e) {
        console.log('Response:', body);
        resolve({ success: false, error: 'Failed to parse response' });
      }
    });
  });
}

async function getGroups() {
  console.log('\n=== Get Groups ===\n');

  const eg = await getEdgeGridAuth();
  if (!eg) {
    return { success: false, error: 'No EdgeGrid auth' };
  }

  return new Promise((resolve) => {
    eg.auth({
      path: '/papi/v1/groups',
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    eg.send((error, response, body) => {
      if (error) {
        console.log(`Error: ${error.message}`);
        resolve({ success: false, error: error.message });
        return;
      }

      console.log(`Status: ${response.statusCode}`);
      try {
        const data = JSON.parse(body);
        const groups = data.groups?.items || [];
        console.log(`Found ${groups.length} groups`);
        groups.slice(0, 5).forEach((group) => {
          console.log(`  - ${group.groupId}: ${group.groupName}`);
        });
        resolve({ success: response.statusCode >= 200 && response.statusCode < 300, data });
      } catch (e) {
        console.log('Response:', body);
        resolve({ success: false, error: 'Failed to parse response' });
      }
    });
  });
}

async function getProperties(contractId, groupId) {
  console.log(`\n=== Get Properties (contract: ${contractId}, group: ${groupId}) ===\n`);

  const eg = await getEdgeGridAuth();
  if (!eg) {
    return { success: false, error: 'No EdgeGrid auth' };
  }

  return new Promise((resolve) => {
    eg.auth({
      path: `/papi/v1/properties?contractId=${contractId}&groupId=${groupId}`,
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    eg.send((error, response, body) => {
      if (error) {
        console.log(`Error: ${error.message}`);
        resolve({ success: false, error: error.message });
        return;
      }

      console.log(`Status: ${response.statusCode}`);
      try {
        const data = JSON.parse(body);
        const properties = data.properties?.items || [];
        console.log(`Found ${properties.length} properties`);
        properties.slice(0, 10).forEach((prop) => {
          console.log(`  - ${prop.propertyId}: ${prop.propertyName}`);
        });
        resolve({ success: response.statusCode >= 200 && response.statusCode < 300, data });
      } catch (e) {
        console.log('Response:', body);
        resolve({ success: false, error: 'Failed to parse response' });
      }
    });
  });
}

async function purgeCache(hostname, paths) {
  console.log(`\n=== Purge Cache (hostname: ${hostname}) ===\n`);

  const eg = await getEdgeGridAuth();
  if (!eg) {
    return { success: false, error: 'No EdgeGrid auth' };
  }

  const payload = {
    hostname,
    objects: paths,
  };

  return new Promise((resolve) => {
    eg.auth({
      path: '/ccu/v3/invalidate/url/production',
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: payload,
    });

    eg.send((error, response, body) => {
      if (error) {
        console.log(`Error: ${error.message}`);
        resolve({ success: false, error: error.message });
        return;
      }

      console.log(`Status: ${response.statusCode}`);
      try {
        const data = JSON.parse(body);
        console.log('Response:', JSON.stringify(data, null, 2));
        resolve({ success: response.statusCode >= 200 && response.statusCode < 300, data });
      } catch (e) {
        console.log('Response:', body);
        resolve({ success: false, error: 'Failed to parse response' });
      }
    });
  });
}

// ============================================================================
// Run Tests
// ============================================================================
async function main() {
  console.log('Akamai Edge API Connection Test (Node.js Client Integration)');
  console.log('='.repeat(60));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Host: ${CONFIG.HOST || 'Not set'}`);
  console.log(`Client Token: ${CONFIG.CLIENT_TOKEN ? CONFIG.CLIENT_TOKEN.slice(0, 10) + '...' : 'Not set'}`);
  console.log(`Access Token: ${CONFIG.ACCESS_TOKEN ? CONFIG.ACCESS_TOKEN.slice(0, 10) + '...' : 'Not set'}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`Has Credentials: ${CONFIG.HAS_CREDENTIALS}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests (requires akamai-edgegrid package):
  // await getActiveGrants();
  // await getContracts();
  // await getGroups();
  // await getProperties('ctr_XXX', 'grp_XXX');
  // await purgeCache('www.example.com', ['/path/to/purge']);
}

main().catch(console.error);
