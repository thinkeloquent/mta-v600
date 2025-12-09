/**
 * SauceLabs API - undici Connection Test
 *
 * Authentication: Basic (username:access_key)
 * Base URL: https://api.us-west-1.saucelabs.com
 * Health Endpoint: GET /rest/v1/users/{username}
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
  SAUCE_USERNAME: process.env.SAUCE_USERNAME || 'your_saucelabs_username',
  SAUCE_ACCESS_KEY: process.env.SAUCE_ACCESS_KEY || 'your_saucelabs_access_key',

  // Base URL (choose your region)
  BASE_URL: process.env.SAUCE_BASE_URL || 'https://api.us-west-1.saucelabs.com',
  // Other regions:
  // - US East: https://api.us-east-4.saucelabs.com
  // - EU Central: https://api.eu-central-1.saucelabs.com

  // Optional: Proxy Configuration
  HTTPS_PROXY: process.env.HTTPS_PROXY || '', // e.g., 'http://proxy.example.com:8080'

  // Optional: TLS Configuration
  // Set to false to ignore certificate errors (default: false for testing)
  // NODE_TLS_REJECT_UNAUTHORIZED=0, REQUEST_CA_BUNDLE=null, SSL_CERT_FILE=null, NODE_EXTRA_CA_CERTS=null
  REJECT_UNAUTHORIZED: false,

  // Optional: Custom CA certificates (disabled by default for testing)
  CA_BUNDLE: null,
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
// Create Basic Auth Header
// ============================================================================

function createBasicAuthHeader() {
  const credentials = `${CONFIG.SAUCE_USERNAME}:${CONFIG.SAUCE_ACCESS_KEY}`;
  return `Basic ${Buffer.from(credentials).toString('base64')}`;
}

// ============================================================================
// Health Check
// ============================================================================

async function healthCheck() {
  console.log('\n=== SauceLabs Health Check ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/rest/v1/users/${CONFIG.SAUCE_USERNAME}`, {
      method: 'GET',
      headers: {
        'Authorization': createBasicAuthHeader(),
        'Accept': 'application/json',
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

async function listJobs(limit = 10) {
  console.log(`\n=== List Jobs (limit: ${limit}) ===\n`);

  const dispatcher = createDispatcher();

  try {
    const url = new URL(`${CONFIG.BASE_URL}/rest/v1/${CONFIG.SAUCE_USERNAME}/jobs`);
    url.searchParams.set('limit', limit.toString());

    const response = await request(url.toString(), {
      method: 'GET',
      headers: {
        'Authorization': createBasicAuthHeader(),
        'Accept': 'application/json',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log(`Found ${data.length} jobs`);
    data.slice(0, 5).forEach((job) => {
      console.log(`  - ${job.id}: ${job.name || 'Unnamed'} (${job.status})`);
    });

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function getJob(jobId) {
  console.log(`\n=== Get Job: ${jobId} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/rest/v1/${CONFIG.SAUCE_USERNAME}/jobs/${jobId}`, {
      method: 'GET',
      headers: {
        'Authorization': createBasicAuthHeader(),
        'Accept': 'application/json',
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

async function getUsage() {
  console.log('\n=== Get Account Usage ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/rest/v1/users/${CONFIG.SAUCE_USERNAME}/usage`, {
      method: 'GET',
      headers: {
        'Authorization': createBasicAuthHeader(),
        'Accept': 'application/json',
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

async function listPlatforms() {
  console.log('\n=== List Available Platforms ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/rest/v1/info/platforms/webdriver`, {
      method: 'GET',
      headers: {
        'Authorization': createBasicAuthHeader(),
        'Accept': 'application/json',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log(`Found ${data.length} platforms`);
    data.slice(0, 10).forEach((platform) => {
      console.log(`  - ${platform.long_name} (${platform.short_version})`);
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
  console.log('SauceLabs API Connection Test');
  console.log('=============================');
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Proxy: ${CONFIG.HTTPS_PROXY || 'None'}`);
  console.log(`Username: ${CONFIG.SAUCE_USERNAME}`);
  console.log(`TLS Verify: ${CONFIG.REJECT_UNAUTHORIZED}`);
  console.log(`CA Bundle: ${CONFIG.CA_BUNDLE || 'System default'}`);

  await healthCheck();
  // await listJobs();
  // await getJob('job_id_here');
  // await getUsage();
  // await listPlatforms();
}

main().catch(console.error);
