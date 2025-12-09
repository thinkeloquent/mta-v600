/**
 * Rally API - undici Connection Test
 *
 * Note: Rally integration is currently a placeholder and not yet implemented.
 *
 * Authentication: ZSESSIONID or API Key
 * Base URL: https://rally1.rallydev.com/slm/webservice/v2.0
 * Health Endpoint: GET /subscription
 *
 * TLS/SSL Options:
 *   NODE_TLS_REJECT_UNAUTHORIZED=0  - Ignore all certificate errors
 *   REQUEST_CA_BUNDLE=/path/to/ca   - Custom CA bundle file
 *   SSL_CERT_FILE=/path/to/cert     - Custom SSL certificate file
 *   NODE_EXTRA_CA_CERTS=/path/to/ca - Additional CA certificates
 */

import { request, ProxyAgent, Agent } from 'undici';
import { readFileSync } from 'node:fs';

// ============================================================================
// Configuration - Override these values
// ============================================================================

const CONFIG = {
  // Required
  RALLY_API_KEY: process.env.RALLY_API_KEY || 'your_rally_api_key_here',

  // Base URL
  BASE_URL: process.env.RALLY_BASE_URL || 'https://rally1.rallydev.com/slm/webservice/v2.0',

  // Optional: Proxy Configuration
  HTTPS_PROXY: process.env.HTTPS_PROXY || '', // e.g., 'http://proxy.example.com:8080'

  // Optional: TLS Configuration
  // Set NODE_TLS_REJECT_UNAUTHORIZED=0 to ignore certificate errors
  REJECT_UNAUTHORIZED: process.env.NODE_TLS_REJECT_UNAUTHORIZED !== '0',

  // Optional: Custom CA certificates
  // REQUEST_CA_BUNDLE or SSL_CERT_FILE - path to custom CA bundle
  // NODE_EXTRA_CA_CERTS - handled automatically by Node.js
  CA_BUNDLE: process.env.REQUEST_CA_BUNDLE || process.env.SSL_CERT_FILE || '',
};

// ============================================================================
// TLS Configuration Helper
// ============================================================================

function getTlsConnectOptions() {
  const options = {
    rejectUnauthorized: CONFIG.REJECT_UNAUTHORIZED,
  };

  // Load custom CA bundle if specified
  if (CONFIG.CA_BUNDLE) {
    try {
      options.ca = readFileSync(CONFIG.CA_BUNDLE);
      console.log(`Using custom CA bundle: ${CONFIG.CA_BUNDLE}`);
    } catch (err) {
      console.warn(`Warning: Could not read CA bundle: ${err.message}`);
    }
  }

  return options;
}

// ============================================================================
// Create Dispatcher (with or without proxy)
// ============================================================================

function createDispatcher() {
  const tlsOptions = getTlsConnectOptions();

  if (CONFIG.HTTPS_PROXY) {
    console.log(`Using proxy: ${CONFIG.HTTPS_PROXY}`);
    return new ProxyAgent({
      uri: CONFIG.HTTPS_PROXY,
      connect: tlsOptions,
    });
  }
  return new Agent({
    connect: tlsOptions,
  });
}

// ============================================================================
// Health Check
// ============================================================================

async function healthCheck() {
  console.log('\n=== Rally Health Check ===\n');
  console.log('Note: Rally integration is a placeholder - not yet implemented.\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/subscription`, {
      method: 'GET',
      headers: {
        'ZSESSIONID': CONFIG.RALLY_API_KEY,
        'Content-Type': 'application/json',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log('Response:', JSON.stringify(data, null, 2));

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

// ============================================================================
// Sample API Calls (Reference)
// ============================================================================

async function getCurrentUser() {
  console.log('\n=== Get Current User ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/user`, {
      method: 'GET',
      headers: {
        'ZSESSIONID': CONFIG.RALLY_API_KEY,
        'Content-Type': 'application/json',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log('Response:', JSON.stringify(data, null, 2));

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function listProjects() {
  console.log('\n=== List Projects ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/project`, {
      method: 'GET',
      headers: {
        'ZSESSIONID': CONFIG.RALLY_API_KEY,
        'Content-Type': 'application/json',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    const results = data.QueryResult?.Results || [];
    console.log(`Found ${results.length} projects`);
    results.slice(0, 10).forEach((project) => {
      console.log(`  - ${project.Name}`);
    });

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function queryUserStories(projectName) {
  console.log(`\n=== Query User Stories: ${projectName} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const query = encodeURIComponent(`(Project.Name = "${projectName}")`);
    const response = await request(`${CONFIG.BASE_URL}/hierarchicalrequirement?query=${query}`, {
      method: 'GET',
      headers: {
        'ZSESSIONID': CONFIG.RALLY_API_KEY,
        'Content-Type': 'application/json',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    const results = data.QueryResult?.Results || [];
    console.log(`Found ${results.length} user stories`);
    results.slice(0, 10).forEach((story) => {
      console.log(`  - ${story.FormattedID}: ${story.Name}`);
    });

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function listDefects() {
  console.log('\n=== List Defects ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/defect`, {
      method: 'GET',
      headers: {
        'ZSESSIONID': CONFIG.RALLY_API_KEY,
        'Content-Type': 'application/json',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    const results = data.QueryResult?.Results || [];
    console.log(`Found ${results.length} defects`);
    results.slice(0, 10).forEach((defect) => {
      console.log(`  - ${defect.FormattedID}: ${defect.Name}`);
    });

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

// ============================================================================
// Run Tests
// ============================================================================

async function main() {
  console.log('Rally API Connection Test');
  console.log('=========================');
  console.log('Status: PLACEHOLDER - Not yet implemented\n');
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Proxy: ${CONFIG.HTTPS_PROXY || 'None'}`);
  console.log(`API Key: ${CONFIG.RALLY_API_KEY.slice(0, 10)}...`);
  console.log(`TLS Verify: ${CONFIG.REJECT_UNAUTHORIZED}`);
  console.log(`CA Bundle: ${CONFIG.CA_BUNDLE || 'System default'}`);

  await healthCheck();
  // await getCurrentUser();
  // await listProjects();
  // await queryUserStories('My Project');
  // await listDefects();
}

main().catch(console.error);
