#!/usr/bin/env node
/**
 * Sonar API - Node.js Client Integration Test
 *
 * Authentication: Bearer Token
 * Base URL: https://sonarcloud.io or https://your-sonar.example.com (SonarQube)
 * Health Endpoint: GET /api/authentication/validate
 *
 * Uses internal packages:
 *   - @internal/fetch-proxy-dispatcher: Environment-aware proxy configuration
 *   - @internal/fetch-client: HTTP client with auth support
 *   - @internal/provider_api_getters: API key resolution
 *   - @internal/app-static-config-yaml: YAML configuration loading
 *
 * API Documentation:
 *   SonarCloud: https://sonarcloud.io/web_api
 *   SonarQube: https://docs.sonarqube.org/latest/extension-guide/web-api/
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
const { SonarApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new SonarApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters
  SONAR_TOKEN: apiKeyResult.apiKey,
  AUTH_TYPE: apiKeyResult.authType,

  // Base URL (from provider or override)
  BASE_URL: provider.getBaseUrl() || process.env.SONAR_BASE_URL || 'https://sonarcloud.io',

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
// Client Factory
// ============================================================================
function createSonarClient() {
  return createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: 'bearer',
      rawApiKey: CONFIG.SONAR_TOKEN,
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
  console.log('\n=== Sonar Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('sonar');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Sample API Calls using fetch-client
// ============================================================================
async function validateAuth() {
  console.log('\n=== Validate Authentication ===\n');

  const client = createSonarClient();

  try {
    const response = await client.get('/api/authentication/validate');

    console.log(`Status: ${response.status}`);
    console.log('Response:', JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getSystemStatus() {
  console.log('\n=== Get System Status ===\n');

  const client = createSonarClient();

  try {
    const response = await client.get('/api/system/status');

    console.log(`Status: ${response.status}`);
    console.log('Response:', JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function listProjects(organization = null, pageSize = 10) {
  console.log(`\n=== List Projects (pageSize: ${pageSize}) ===\n`);

  const client = createSonarClient();
  const query = { ps: pageSize };
  if (organization) {
    query.organization = organization;
  }

  try {
    const response = await client.get('/api/projects/search', { query });

    console.log(`Status: ${response.status}`);
    if (response.ok && response.data) {
      const components = response.data.components || [];
      const paging = response.data.paging || {};
      console.log(`Total: ${paging.total || 0}`);
      components.slice(0, 10).forEach((project) => {
        console.log(`  - ${project.key}: ${project.name}`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getProjectStatus(projectKey) {
  console.log(`\n=== Get Project Status: ${projectKey} ===\n`);

  const client = createSonarClient();

  try {
    const response = await client.get('/api/qualitygates/project_status', {
      query: { projectKey },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok && response.data) {
      const projectStatus = response.data.projectStatus || {};
      console.log(`Quality Gate: ${projectStatus.status}`);
      const conditions = projectStatus.conditions || [];
      conditions.slice(0, 5).forEach((condition) => {
        console.log(`  - ${condition.metricKey}: ${condition.status} (${condition.actualValue})`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getProjectMetrics(projectKey) {
  console.log(`\n=== Get Project Metrics: ${projectKey} ===\n`);

  const metricKeys = 'bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density';

  const client = createSonarClient();

  try {
    const response = await client.get('/api/measures/component', {
      query: { component: projectKey, metricKeys },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok && response.data) {
      const component = response.data.component || {};
      const measures = component.measures || [];
      console.log(`Project: ${component.name}`);
      measures.forEach((measure) => {
        console.log(`  - ${measure.metric}: ${measure.value}`);
      });
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function listIssues(projectKey = null, pageSize = 10) {
  console.log(`\n=== List Issues (pageSize: ${pageSize}) ===\n`);

  const client = createSonarClient();
  const query = { ps: pageSize, resolved: 'false' };
  if (projectKey) {
    query.componentKeys = projectKey;
  }

  try {
    const response = await client.get('/api/issues/search', { query });

    console.log(`Status: ${response.status}`);
    if (response.ok && response.data) {
      const issues = response.data.issues || [];
      const paging = response.data.paging || {};
      console.log(`Total: ${paging.total || 0}`);
      issues.slice(0, 10).forEach((issue) => {
        const severity = issue.severity || 'UNKNOWN';
        const type = issue.type || 'UNKNOWN';
        let message = issue.message || '';
        if (message.length > 50) message = message.slice(0, 50) + '...';
        console.log(`  - [${severity}] ${type}: ${message}`);
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
  console.log('Sonar API Connection Test (Node.js Client Integration)');
  console.log('='.repeat(55));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Token: ${CONFIG.SONAR_TOKEN ? CONFIG.SONAR_TOKEN.slice(0, 10) + '...' : 'Not set'}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await validateAuth();
  // await getSystemStatus();
  // await listProjects('your-org');
  // await getProjectStatus('your-project-key');
  // await getProjectMetrics('your-project-key');
  // await listIssues();
}

main().catch(console.error);
