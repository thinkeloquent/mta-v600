/**
 * Jira API - undici Connection Test
 *
 * Authentication: Basic (email:api_token)
 * Base URL: https://{company}.atlassian.net
 * Health Endpoint: GET /rest/api/2/myself
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
  JIRA_BASE_URL: process.env.JIRA_BASE_URL || 'https://your-company.atlassian.net',
  JIRA_EMAIL: process.env.JIRA_EMAIL || 'your.email@example.com',
  JIRA_API_TOKEN: process.env.JIRA_API_TOKEN || 'your_jira_api_token_here',

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
  const credentials = `${CONFIG.JIRA_EMAIL}:${CONFIG.JIRA_API_TOKEN}`;
  return `Basic ${Buffer.from(credentials).toString('base64')}`;
}

// ============================================================================
// Health Check
// ============================================================================

async function healthCheck() {
  console.log('\n=== Jira Health Check ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.JIRA_BASE_URL}/rest/api/2/myself`, {
      method: 'GET',
      headers: {
        'Authorization': createBasicAuthHeader(),
        'Accept': 'application/json',
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
// Sample API Calls
// ============================================================================

async function searchIssues(jql) {
  console.log(`\n=== Search Issues: ${jql} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const url = new URL(`${CONFIG.JIRA_BASE_URL}/rest/api/2/search`);
    url.searchParams.set('jql', jql);
    url.searchParams.set('maxResults', '10');

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
    console.log(`Found ${data.total} issues`);
    data.issues?.slice(0, 5).forEach((issue) => {
      console.log(`  - ${issue.key}: ${issue.fields.summary}`);
    });

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function getIssue(issueKey) {
  console.log(`\n=== Get Issue: ${issueKey} ===\n`);

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.JIRA_BASE_URL}/rest/api/2/issue/${issueKey}`, {
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

async function listProjects() {
  console.log('\n=== List Projects ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.JIRA_BASE_URL}/rest/api/2/project`, {
      method: 'GET',
      headers: {
        'Authorization': createBasicAuthHeader(),
        'Accept': 'application/json',
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log(`Found ${data.length} projects`);
    data.slice(0, 10).forEach((project) => {
      console.log(`  - ${project.key}: ${project.name}`);
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
  console.log('Jira API Connection Test');
  console.log('========================');
  console.log(`Base URL: ${CONFIG.JIRA_BASE_URL}`);
  console.log(`Proxy: ${CONFIG.HTTPS_PROXY || 'None'}`);
  console.log(`Email: ${CONFIG.JIRA_EMAIL}`);
  console.log(`TLS Verify: ${CONFIG.REJECT_UNAUTHORIZED}`);
  console.log(`CA Bundle: ${CONFIG.CA_BUNDLE || 'System default'}`);

  await healthCheck();
  // await listProjects();
  // await searchIssues('project = MYPROJECT ORDER BY created DESC');
  // await getIssue('MYPROJECT-123');
}

main().catch(console.error);
