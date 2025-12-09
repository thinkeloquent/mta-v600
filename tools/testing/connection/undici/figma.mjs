/**
 * Figma API - undici Connection Test
 *
 * Authentication: X-Figma-Token header
 * Base URL: https://api.figma.com/v1
 * Health Endpoint: GET /v1/me
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
  FIGMA_TOKEN: process.env.FIGMA_TOKEN || 'your_figma_token_here',

  // Base URL
  BASE_URL: 'https://api.figma.com',

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
  console.log('\n=== Figma Health Check ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/v1/me`, {
      method: 'GET',
      headers: {
        'X-Figma-Token': CONFIG.FIGMA_TOKEN,
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
// Sample API Calls
// ============================================================================

async function getFile(fileKey) {
  console.log(`\n=== Get File: ${fileKey} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/v1/files/${fileKey}`, {
      method: 'GET',
      headers: {
        'X-Figma-Token': CONFIG.FIGMA_TOKEN,
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log('File Name:', data.name);
    console.log('Last Modified:', data.lastModified);

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function getFileNodes(fileKey, nodeIds) {
  console.log(`\n=== Get File Nodes: ${fileKey} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const url = new URL(`${CONFIG.BASE_URL}/v1/files/${fileKey}/nodes`);
    url.searchParams.set('ids', nodeIds.join(','));

    const response = await request(url.toString(), {
      method: 'GET',
      headers: {
        'X-Figma-Token': CONFIG.FIGMA_TOKEN,
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

async function getFileImages(fileKey, nodeIds, format = 'png') {
  console.log(`\n=== Get File Images: ${fileKey} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const url = new URL(`${CONFIG.BASE_URL}/v1/images/${fileKey}`);
    url.searchParams.set('ids', nodeIds.join(','));
    url.searchParams.set('format', format);

    const response = await request(url.toString(), {
      method: 'GET',
      headers: {
        'X-Figma-Token': CONFIG.FIGMA_TOKEN,
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log('Images:', data.images);

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function listTeamProjects(teamId) {
  console.log(`\n=== List Team Projects: ${teamId} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/v1/teams/${teamId}/projects`, {
      method: 'GET',
      headers: {
        'X-Figma-Token': CONFIG.FIGMA_TOKEN,
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log(`Found ${data.projects?.length || 0} projects`);
    data.projects?.forEach((project) => {
      console.log(`  - ${project.name} (${project.id})`);
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
  console.log('Figma API Connection Test');
  console.log('=========================');
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Proxy: ${CONFIG.HTTPS_PROXY || 'None'}`);
  console.log(`Token: ${CONFIG.FIGMA_TOKEN.slice(0, 10)}...`);
  console.log(`TLS Verify: ${CONFIG.REJECT_UNAUTHORIZED}`);
  console.log(`CA Bundle: ${CONFIG.CA_BUNDLE || 'System default'}`);

  await healthCheck();
  // await getFile('file_key_here');
  // await getFileNodes('file_key_here', ['node_id_1', 'node_id_2']);
  // await getFileImages('file_key_here', ['node_id_1'], 'png');
  // await listTeamProjects('team_id_here');
}

main().catch(console.error);
