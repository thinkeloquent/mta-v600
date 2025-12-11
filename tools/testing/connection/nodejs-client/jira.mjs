#!/usr/bin/env node
/**
 * Jira API - Node.js Client Integration Test
 *
 * Authentication: Basic (email:api_token)
 * Base URL: https://{company}.atlassian.net
 * Health Endpoint: GET /myself
 *
 * Uses internal packages:
 *   - @internal/fetch-proxy-dispatcher: Environment-aware proxy configuration
 *   - @internal/fetch-client: HTTP client with auth support
 *   - @internal/provider_api_getters: API key resolution
 *   - @internal/app-static-config-yaml: YAML configuration loading
 */
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

// ============================================================================
// Project Setup
// ============================================================================
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, "..", "..", "..", "..");

// Load static config
const { loadYamlConfig, config: staticConfig } = await import(
  resolve(
    PROJECT_ROOT,
    "packages_mjs",
    "app-static-config-yaml",
    "src",
    "index.mjs"
  )
);
const configDir = resolve(PROJECT_ROOT, "common", "config");
await loadYamlConfig({ configDir });

// Import internal packages
const { getProxyDispatcher } = await import(
  resolve(
    PROJECT_ROOT,
    "packages_mjs",
    "fetch-proxy-dispatcher",
    "src",
    "index.mts"
  )
);
const { createClient } = await import(
  resolve(PROJECT_ROOT, "packages_mjs", "fetch-client", "src", "index.mts")
);
const { JiraApiToken, ProviderHealthChecker } = await import(
  resolve(
    PROJECT_ROOT,
    "packages_mjs",
    "provider_api_getters",
    "src",
    "index.mjs"
  )
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new JiraApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters
  JIRA_API_TOKEN: apiKeyResult.apiKey, // Raw API token
  JIRA_EMAIL: apiKeyResult.email || apiKeyResult.username,
  AUTH_TYPE: "basic_email_token", // Atlassian APIs use Basic <base64(email:token)>

  // Base URL (from provider or override)
  BASE_URL:
    provider.getBaseUrl() ||
    process.env.JIRA_BASE_URL ||
    "https://your-company.atlassian.net",

  // Dispatcher (from fetch-proxy-dispatcher)
  DISPATCHER: getProxyDispatcher(),

  // Proxy Configuration (set to override YAML/environment config)
  PROXY: process.env.HTTPS_PROXY || process.env.HTTP_PROXY || undefined,

  // SSL/TLS Configuration (runtime override, or undefined to use YAML config)
  SSL_VERIFY: false, // Set to undefined to use YAML config

  // Debug
  DEBUG: !["false", "0"].includes((process.env.DEBUG || "").toLowerCase()),
};

// ============================================================================
// Health Check
// ============================================================================
async function healthCheck() {
  console.log("\n=== Jira Health Check (ProviderHealthChecker) ===\n");

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check("jira");

  console.log(`Status: ${result.status}`);
  if (result.latency_ms)
    console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === "connected", result };
}

// ============================================================================
// Sample API Calls using fetch-client
// ============================================================================
async function getMyself() {
  console.log("\n=== Get Current User ===\n");

  const client = createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: "basic_email_token",
      rawApiKey: CONFIG.JIRA_API_TOKEN,
      email: CONFIG.JIRA_EMAIL,
    },
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });

  try {
    const response = await client.get("/myself");

    console.log(`Status: ${response.status}`);
    console.log("Response:", JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function listProjects() {
  console.log("\n=== List Projects ===\n");

  const client = createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: "basic_email_token",
      rawApiKey: CONFIG.JIRA_API_TOKEN,
      email: CONFIG.JIRA_EMAIL,
    },
    headers: {
      Accept: "application/json",
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });

  try {
    const response = await client.get("/project");

    console.log(`Status: ${response.status}`);
    if (response.ok && Array.isArray(response.data)) {
      console.log(`Found ${response.data.length} projects`);
      response.data.slice(0, 10).forEach((project) => {
        console.log(`  - ${project.key}: ${project.name}`);
      });
    } else {
      console.log("Response:", JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function searchIssues(jql) {
  console.log(`\n=== Search Issues: ${jql} ===\n`);

  const client = createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: "basic_email_token",
      rawApiKey: CONFIG.JIRA_API_TOKEN,
      email: CONFIG.JIRA_EMAIL,
    },
    headers: {
      Accept: "application/json",
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });

  try {
    const response = await client.get("/search", {
      query: { jql, maxResults: 10 },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok) {
      console.log(`Found ${response.data.total || 0} issues`);
      (response.data.issues || []).slice(0, 5).forEach((issue) => {
        console.log(`  - ${issue.key}: ${issue.fields.summary}`);
      });
    } else {
      console.log("Response:", JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function getIssue(issueKey) {
  console.log(`\n=== Get Issue: ${issueKey} ===\n`);

  const client = createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: "basic_email_token",
      rawApiKey: CONFIG.JIRA_API_TOKEN,
      email: CONFIG.JIRA_EMAIL,
    },
    headers: {
      Accept: "application/json",
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });

  try {
    const response = await client.get(`/issue/${issueKey}`);

    console.log(`Status: ${response.status}`);
    console.log("Response:", JSON.stringify(response.data, null, 2));

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

// ============================================================================
// Run Tests
// ============================================================================
async function main() {
  console.log("Jira API Connection Test (Node.js Client Integration)");
  console.log("=".repeat(52));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Email: ${CONFIG.JIRA_EMAIL}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await getMyself();
  // await listProjects();
  // await searchIssues('project = MYPROJECT ORDER BY created DESC');
  // await getIssue('MYPROJECT-123');
}

main().catch(console.error);
