/**
 * Figma API - undici Connection Test
 *
 * Authentication: X-Figma-Token header
 * Base URL: https://api.figma.com/v1
 * Health Endpoint: GET /v1/me
 */

import { request, ProxyAgent, Agent } from 'undici';

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
  REJECT_UNAUTHORIZED: true, // Set to false to skip TLS verification (testing only)
};

// ============================================================================
// Create Dispatcher (with or without proxy)
// ============================================================================

function createDispatcher() {
  if (CONFIG.HTTPS_PROXY) {
    console.log(`Using proxy: ${CONFIG.HTTPS_PROXY}`);
    return new ProxyAgent({
      uri: CONFIG.HTTPS_PROXY,
      connect: {
        rejectUnauthorized: CONFIG.REJECT_UNAUTHORIZED,
      },
    });
  }
  return new Agent({
    connect: {
      rejectUnauthorized: CONFIG.REJECT_UNAUTHORIZED,
    },
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

  await healthCheck();
  // await getFile('file_key_here');
  // await getFileNodes('file_key_here', ['node_id_1', 'node_id_2']);
  // await getFileImages('file_key_here', ['node_id_1'], 'png');
  // await listTeamProjects('team_id_here');
}

main().catch(console.error);
