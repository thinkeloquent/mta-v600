#!/usr/bin/env node
/**
 * Jira Health Check - Standalone debugging script
 *
 * Run directly: node jira_health_check.mjs
 *
 * Uses:
 * - static_config for YAML configuration
 * - JiraApiToken for API token resolution
 * - fetch_client for HTTP requests with proxy/auth support
 */
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const LOG_PREFIX = `[AUTH:${__filename}]`;
const PROJECT_ROOT = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  "..",
  "..",
  "..",
  ".."
);
const CONFIG_DIR = path.join(PROJECT_ROOT, "common", "config");

// ============================================================
// Load static config FIRST
// ============================================================
import {
  loadYamlConfig,
  config as staticConfig,
} from "@internal/app-static-config-yaml";
await loadYamlConfig({ configDir: CONFIG_DIR });

// ============================================================
// Provider API getter
// ============================================================
import { JiraApiToken } from "../../api_token/index.mjs";

// ============================================================
// Fetch client with dispatcher
// ============================================================
import { createClientWithDispatcher } from "@internal/fetch-client";

export async function checkJiraHealth() {
  console.log("=".repeat(60));
  console.log("JIRA HEALTH CHECK");
  console.log("=".repeat(60));

  // Initialize provider from static config
  const provider = new JiraApiToken(staticConfig);
  const apiKeyResult = provider.getApiKey();
  const networkConfig = provider.getNetworkConfig();
  const baseUrl = provider.getBaseUrl();

  // Mask function for sensitive values
  const maskValue = (val) => {
    if (!val) return "<empty>";
    if (val.length <= 10) return "*".repeat(val.length);
    return val.substring(0, 10) + "*".repeat(val.length - 10);
  };

  // Debug output
  console.log("\n[Config]");
  console.log(`  Base URL: ${baseUrl}`);
  console.log(`  Has credentials: ${apiKeyResult.hasCredentials}`);
  console.log(`  Is placeholder: ${apiKeyResult.isPlaceholder}`);
  console.log(`  Auth type: ${apiKeyResult.authType}`);
  console.log(`  Header name: ${apiKeyResult.headerName}`);
  console.log(`  Email: ${apiKeyResult.email || "N/A"}`);

  // AUTH TRACING: Log the credential values from provider
  console.log(`\n${LOG_PREFIX} [Provider Output]`);
  console.log(`  apiKeyResult.apiKey (pre-encoded): ${maskValue(apiKeyResult.apiKey)}`);
  console.log(`  apiKeyResult.rawApiKey (unencoded): ${maskValue(apiKeyResult.rawApiKey)}`);
  console.log(`  apiKeyResult.email: ${apiKeyResult.email || "N/A"}`);
  console.log(`  apiKeyResult.authType: ${apiKeyResult.authType}`);
  console.log("\n[Network Config]");
  console.log(`  Proxy URL: ${networkConfig.proxyUrl || "None"}`);
  console.log(`  Cert verify: ${networkConfig.certVerify}`);

  if (!apiKeyResult.hasCredentials || apiKeyResult.isPlaceholder) {
    console.log("\n[ERROR] Missing or placeholder credentials");
    return { success: false, error: "Missing credentials" };
  }

  if (!baseUrl) {
    console.log("\n[ERROR] No base URL configured");
    return { success: false, error: "No base URL" };
  }

  // Create client with dispatcher (handles proxy, SSL, auth)
  console.log("\n[Creating Client]");
  console.log(`  Auth type: ${apiKeyResult.authType}`);

  // AUTH TRACING: Log what we're passing to fetch-client
  console.log(`\n${LOG_PREFIX} [Passing to fetch-client]`);
  console.log(`  auth.type: ${apiKeyResult.authType}`);
  console.log(`  auth.rawApiKey: ${maskValue(apiKeyResult.rawApiKey)}`);
  console.log(`  auth.email: ${apiKeyResult.email || "N/A"}`);
  console.log(`  auth.headerName: ${apiKeyResult.headerName}`);

  const client = await createClientWithDispatcher({
    baseUrl,
    auth: {
      type: apiKeyResult.authType,
      rawApiKey: apiKeyResult.rawApiKey,  // Use raw unencoded token, not pre-encoded apiKey
      email: apiKeyResult.email,
      headerName: apiKeyResult.headerName,
    },
    headers: {
      Accept: "application/json",
    },
    verify: networkConfig.certVerify,
    proxy: networkConfig.proxyUrl,
  });

  // Make health check request
  const healthEndpoint = "/myself";
  console.log("\n[Request]");
  console.log(`  GET ${baseUrl}${healthEndpoint}`);

  try {
    const response = await client.get(healthEndpoint);

    console.log("\n[Response]");
    console.log(`  Status: ${response.status}`);
    console.log(`  OK: ${response.ok}`);

    if (response.ok) {
      const data = response.data;
      const displayName = data.displayName || "N/A";
      const emailAddress = data.emailAddress || "N/A";
      const accountId = data.accountId || "N/A";
      const active = data.active || false;

      console.log("\n[User Info]");
      console.log(`  Display Name: ${displayName}`);
      console.log(`  Email: ${emailAddress}`);
      console.log(`  Account ID: ${accountId}`);
      console.log(`  Active: ${active}`);

      return {
        success: true,
        message: `Connected as ${displayName}`,
        data: {
          displayName,
          email: emailAddress,
          accountId,
          active,
        },
      };
    } else {
      console.log("\n[Error Response]");
      console.log(JSON.stringify(response.data, null, 2));
      return {
        success: false,
        statusCode: response.status,
        error: response.data,
      };
    }
  } finally {
    await client.close?.();
  }
}

// Run if executed directly
if (process.argv[1] === __filename) {
  console.log("\n");
  const result = await checkJiraHealth();
  console.log("\n" + "=".repeat(60));
  console.log("RESULT");
  console.log("=".repeat(60));
  console.log(JSON.stringify(result, null, 2));
}
