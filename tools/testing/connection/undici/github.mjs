/**
 * GitHub API - undici Connection Test
 *
 * Authentication: Bearer Token
 * Base URL: https://api.github.com
 * Health Endpoint: GET /user
 */

import { request, ProxyAgent, Agent } from 'undici';

// ============================================================================
// Configuration - Override these values
// ============================================================================

const CONFIG = {
  // Required
  GITHUB_TOKEN: process.env.GITHUB_TOKEN || 'your_github_token_here',

  // Base URL
  BASE_URL: 'https://api.github.com',

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
  console.log('\n=== GitHub Health Check ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/user`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${CONFIG.GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'undici-test',
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

async function listRepositories() {
  console.log('\n=== List Repositories ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/user/repos`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${CONFIG.GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'undici-test',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log(`Found ${data.length} repositories`);
    data.slice(0, 5).forEach((repo) => {
      console.log(`  - ${repo.full_name}`);
    });

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function getRepository(owner, repo) {
  console.log(`\n=== Get Repository: ${owner}/${repo} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/repos/${owner}/${repo}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${CONFIG.GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'undici-test',
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
// Run Tests
// ============================================================================

async function main() {
  console.log('GitHub API Connection Test');
  console.log('==========================');
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Proxy: ${CONFIG.HTTPS_PROXY || 'None'}`);
  console.log(`Token: ${CONFIG.GITHUB_TOKEN.slice(0, 10)}...`);

  await healthCheck();
  // await listRepositories();
  // await getRepository('owner', 'repo');
}

main().catch(console.error);
