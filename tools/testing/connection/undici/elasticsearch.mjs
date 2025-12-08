/**
 * Elasticsearch - undici Connection Test
 *
 * Authentication: Basic (username:password)
 * Base URL: http://localhost:9200 or https://...
 * Health Endpoint: GET /_cluster/health
 */

import { request, ProxyAgent, Agent } from 'undici';

// ============================================================================
// Configuration - Override these values
// ============================================================================

const CONFIG = {
  // Option 1: Full Connection URL
  ELASTIC_DB_URL: process.env.ELASTIC_DB_URL || '',

  // Option 2: Individual Components
  ELASTIC_DB_HOST: process.env.ELASTIC_DB_HOST || 'localhost',
  ELASTIC_DB_PORT: process.env.ELASTIC_DB_PORT || '9200',
  ELASTIC_DB_USERNAME: process.env.ELASTIC_DB_USERNAME || '',
  ELASTIC_DB_ACCESS_KEY: process.env.ELASTIC_DB_ACCESS_KEY || '',
  ELASTIC_DB_TLS: process.env.ELASTIC_DB_TLS || 'false', // 'true' for HTTPS

  // Optional: Proxy Configuration
  HTTPS_PROXY: process.env.HTTPS_PROXY || '', // e.g., 'http://proxy.example.com:8080'

  // Optional: TLS Configuration
  REJECT_UNAUTHORIZED: true, // Set to false to skip TLS verification (testing only)
};

// ============================================================================
// Build Base URL
// ============================================================================

function getBaseUrl() {
  if (CONFIG.ELASTIC_DB_URL) {
    return CONFIG.ELASTIC_DB_URL;
  }

  const useTls = CONFIG.ELASTIC_DB_TLS === 'true' ||
    ['443', '9243', '25060'].includes(CONFIG.ELASTIC_DB_PORT);
  const protocol = useTls ? 'https' : 'http';

  let url = `${protocol}://`;

  if (CONFIG.ELASTIC_DB_USERNAME && CONFIG.ELASTIC_DB_ACCESS_KEY) {
    url += `${CONFIG.ELASTIC_DB_USERNAME}:${CONFIG.ELASTIC_DB_ACCESS_KEY}@`;
  }

  url += `${CONFIG.ELASTIC_DB_HOST}:${CONFIG.ELASTIC_DB_PORT}`;

  return url;
}

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
// Create Basic Auth Header
// ============================================================================

function createBasicAuthHeader() {
  if (!CONFIG.ELASTIC_DB_USERNAME || !CONFIG.ELASTIC_DB_ACCESS_KEY) {
    return null;
  }
  const credentials = `${CONFIG.ELASTIC_DB_USERNAME}:${CONFIG.ELASTIC_DB_ACCESS_KEY}`;
  return `Basic ${Buffer.from(credentials).toString('base64')}`;
}

// ============================================================================
// Health Check
// ============================================================================

async function healthCheck() {
  console.log('\n=== Elasticsearch Health Check ===\n');

  const dispatcher = createDispatcher();
  const baseUrl = getBaseUrl();

  try {
    const headers = {
      'Accept': 'application/json',
    };

    const authHeader = createBasicAuthHeader();
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    const response = await request(`${baseUrl}/_cluster/health`, {
      method: 'GET',
      headers,
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

async function getClusterInfo() {
  console.log('\n=== Cluster Info ===\n');

  const dispatcher = createDispatcher();
  const baseUrl = getBaseUrl();

  try {
    const headers = { 'Accept': 'application/json' };
    const authHeader = createBasicAuthHeader();
    if (authHeader) headers['Authorization'] = authHeader;

    const response = await request(baseUrl, {
      method: 'GET',
      headers,
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

async function listIndices() {
  console.log('\n=== List Indices ===\n');

  const dispatcher = createDispatcher();
  const baseUrl = getBaseUrl();

  try {
    const headers = { 'Accept': 'application/json' };
    const authHeader = createBasicAuthHeader();
    if (authHeader) headers['Authorization'] = authHeader;

    const response = await request(`${baseUrl}/_cat/indices?format=json`, {
      method: 'GET',
      headers,
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log(`Found ${data.length} indices`);
    data.slice(0, 10).forEach((index) => {
      console.log(`  - ${index.index} (${index.health}, ${index['docs.count']} docs)`);
    });

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function searchIndex(indexName, query = { match_all: {} }) {
  console.log(`\n=== Search Index: ${indexName} ===\n`);

  const dispatcher = createDispatcher();
  const baseUrl = getBaseUrl();

  try {
    const headers = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };
    const authHeader = createBasicAuthHeader();
    if (authHeader) headers['Authorization'] = authHeader;

    const response = await request(`${baseUrl}/${indexName}/_search`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ query }),
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log(`Found ${data.hits?.total?.value || 0} documents`);

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function indexDocument(indexName, document) {
  console.log(`\n=== Index Document: ${indexName} ===\n`);

  const dispatcher = createDispatcher();
  const baseUrl = getBaseUrl();

  try {
    const headers = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };
    const authHeader = createBasicAuthHeader();
    if (authHeader) headers['Authorization'] = authHeader;

    const response = await request(`${baseUrl}/${indexName}/_doc`, {
      method: 'POST',
      headers,
      body: JSON.stringify(document),
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log('Response:', JSON.stringify(data, null, 2));

    return { success: response.statusCode === 201, data };
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
  const baseUrl = getBaseUrl();

  console.log('Elasticsearch Connection Test');
  console.log('=============================');
  console.log(`Base URL: ${baseUrl.replace(/:[^:@]+@/, ':***@')}`); // Mask password
  console.log(`Proxy: ${CONFIG.HTTPS_PROXY || 'None'}`);

  await healthCheck();
  // await getClusterInfo();
  // await listIndices();
  // await searchIndex('my-index');
  // await indexDocument('my-index', { title: 'Test', content: 'Hello World' });
}

main().catch(console.error);
