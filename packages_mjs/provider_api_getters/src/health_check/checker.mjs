/**
 * Provider health check implementation.
 */
import { getApiTokenClass } from "../api_token/index.mjs";
import { ProviderClientFactory } from "../fetch_client/factory.mjs";
import { encodeAuth } from "@internal/fetch-auth-encoding";
import pc from "picocolors";

// ============================================================================
// Console Panel Utilities
// ============================================================================

/**
 * Mask sensitive header value for safe logging, showing first N chars.
 * @param {string} value - The sensitive value to mask
 * @param {number} visibleChars - Number of characters to show (default: 10)
 * @returns {string} Masked value
 */
function maskSensitiveHeader(value, visibleChars = 10) {
  if (!value) return "<empty>";
  if (value.length <= visibleChars) return "*".repeat(value.length);
  return (
    value.substring(0, visibleChars) + "*".repeat(value.length - visibleChars)
  );
}

/**
 * Format headers for display, masking sensitive values.
 * @param {Record<string, string>} headers - Headers to format
 * @returns {Record<string, string>} Headers with sensitive values masked
 */
function formatHeadersForDisplay(headers) {
  const sensitiveHeaders = new Set([
    "authorization",
    "x-api-key",
    "x-figma-token",
    "cookie",
    "set-cookie",
  ]);
  const masked = {};
  for (const [key, value] of Object.entries(headers || {})) {
    if (sensitiveHeaders.has(key.toLowerCase())) {
      masked[key] = maskSensitiveHeader(value);
    } else {
      masked[key] = value;
    }
  }
  return masked;
}

/**
 * Strip ANSI color codes from a string to get actual display length.
 * @param {string} str - String potentially containing ANSI codes
 * @returns {number} Display length without ANSI codes
 */
function stripAnsiLength(str) {
  // eslint-disable-next-line no-control-regex
  return str.replace(/\x1b\[[0-9;]*m/g, "").length;
}

/**
 * Print a panel with header bar, plain JSON content, and footer bar.
 * @param {string} title - Panel title (with color codes)
 * @param {string} content - JSON string to display
 * @param {string} borderColor - Color for the border (cyan, magenta, green, red, yellow)
 */
function printPanel(title, content, borderColor = "cyan") {
  // Get the actual display length of the title (without ANSI codes)
  const titleDisplayLen = stripAnsiLength(title);
  // Fixed width based on title length + padding
  const width = titleDisplayLen + 8;

  const colorFn = pc[borderColor] || pc.cyan;

  // Header bar with title
  const titlePadded = ` ${title} `;
  const titlePaddedDisplayLen = titleDisplayLen + 2; // space on each side
  const topBorderLen = Math.max(0, width - titlePaddedDisplayLen - 2);
  const topLeft = Math.floor(topBorderLen / 2);
  const topRight = topBorderLen - topLeft;

  console.log(
    colorFn("╭" + "─".repeat(topLeft)) +
      titlePadded +
      colorFn("─".repeat(topRight) + "╮")
  );
  console.log(colorFn("╰" + "─".repeat(width - 2) + "╯"));

  // Plain JSON content
  console.log(content);

  // Footer bar
  console.log(colorFn("╰" + "─".repeat(width - 2) + "╯"));
}

/**
 * Print a pretty panel for the proxy/network configuration.
 * @param {string} providerName - Provider name
 * @param {Object} apiToken - API token instance
 * @param {Object} apiKeyResult - Result from getApiKey() with credentials info
 * @param {Object} configUsed - Configuration object
 */
function printProxyConfigPanel(
  providerName,
  apiToken,
  apiKeyResult,
  configUsed
) {
  if (!configUsed) return;

  const proxyConfig = configUsed.proxy || {};
  const clientConfig = configUsed.client || {};

  const configInfo = {
    provider: providerName,
    base_url: configUsed.base_url,
    auth_type: configUsed.auth_type,
    proxy: {
      default_environment: proxyConfig.default_environment,
      proxy_urls: proxyConfig.proxy_urls || "(none)",
      ca_bundle: proxyConfig.ca_bundle || "(system default)",
      cert: proxyConfig.cert || "(none)",
      cert_verify: proxyConfig.cert_verify,
      agent_proxy: proxyConfig.agent_proxy || "(none)",
    },
    client: {
      timeout_seconds: clientConfig.timeout_seconds,
      max_connections: clientConfig.max_connections,
    },
    overrides: {
      has_provider_override: configUsed.has_provider_override || false,
      has_runtime_override: configUsed.has_runtime_override || false,
    },
  };

  // Debug log with redacted sensitive data
  const redactedApiKey = apiKeyResult?.apiKey
    ? `${apiKeyResult.apiKey.substring(0, 10)}...[REDACTED]`
    : null;
  console.log(
    `printProxyConfigPanel: provider=${providerName}, ` +
      `tokenClass=${apiToken?.constructor?.name || "null"}, ` +
      `apiKey=${redactedApiKey}, ` +
      `hasCredentials=${apiKeyResult?.hasCredentials}`
  );

  const title = pc.bold(
    pc.magenta(`Provider Config → ${providerName.toUpperCase()}`)
  );
  printPanel(title, JSON.stringify(configInfo, null, 2), "magenta");
}

/**
 * Print a pretty panel for the health check request.
 * @param {string} providerName - Provider name
 * @param {string} method - HTTP method
 * @param {string} url - Request URL
 * @param {Record<string, string>} headers - Request headers
 * @param {string} authType - Authentication type
 */
function printHealthRequestPanel(providerName, method, url, headers, authType) {
  const maskedHeaders = formatHeadersForDisplay(headers);

  const requestInfo = {
    provider: providerName,
    method: method,
    url: url,
    auth_type: authType || "unknown",
    headers: maskedHeaders,
  };

  const title = pc.bold(
    pc.cyan(`Provider Health Request → ${providerName.toUpperCase()}`)
  );
  printPanel(title, JSON.stringify(requestInfo, null, 2), "cyan");
}

/**
 * Print a pretty panel for the health check response.
 * @param {string} providerName - Provider name
 * @param {string} status - Connection status (connected, error, etc.)
 * @param {number} statusCode - HTTP status code
 * @param {number} latencyMs - Request latency in milliseconds
 * @param {Record<string, string>} responseHeaders - Response headers
 * @param {any} responseData - Response body data
 * @param {string} error - Error message if any
 */
function printHealthResponsePanel(
  providerName,
  status,
  statusCode,
  latencyMs,
  responseHeaders,
  responseData,
  error
) {
  // Determine color based on status
  let borderColor = "yellow";
  let statusDisplay = status.toUpperCase();

  if (status === "connected") {
    borderColor = "green";
  } else if (status === "error") {
    borderColor = "red";
  }

  const maskedRespHeaders = formatHeadersForDisplay(responseHeaders || {});

  const responseInfo = {
    provider: providerName,
    status: status,
    http_status: statusCode,
    latency_ms: Math.round(latencyMs * 100) / 100,
    headers: maskedRespHeaders,
  };

  // Include response data (truncated if too large)
  if (responseData !== null && responseData !== undefined) {
    if (typeof responseData === "object") {
      responseInfo.data = responseData;
    } else if (typeof responseData === "string" && responseData.length > 500) {
      responseInfo.data = responseData.substring(0, 500) + "...";
    } else {
      responseInfo.data = responseData;
    }
  }

  if (error) {
    responseInfo.error = error;
  }

  const colorFn = pc[borderColor] || pc.yellow;
  const title = pc.bold(
    colorFn(
      `Provider Health Response ← ${providerName.toUpperCase()} (${statusDisplay})`
    )
  );
  printPanel(title, JSON.stringify(responseInfo, null, 2), borderColor);
}

/**
 * Print a pretty panel for database connection check.
 * @param {string} providerName - Provider name (postgres, redis, elasticsearch)
 * @param {string} connectionType - Connection type (Sequelize, ioredis, HTTP)
 * @param {Object} configUsed - Configuration used
 */
function printDatabaseConfigPanel(providerName, connectionType, configUsed) {
  if (!configUsed) return;

  const configInfo = {
    provider: providerName,
    connection_type: connectionType,
    auth_type: configUsed.auth_type || "connection_string",
    proxy: configUsed.proxy || "(not applicable)",
    client: configUsed.client || {},
    overrides: {
      has_provider_override: configUsed.has_provider_override || false,
      has_runtime_override: configUsed.has_runtime_override || false,
    },
  };

  const title = pc.bold(
    pc.magenta(`Provider Config → ${providerName.toUpperCase()}`)
  );
  printPanel(title, JSON.stringify(configInfo, null, 2), "magenta");
}

/**
 * Print a pretty panel for database connection result.
 * @param {string} providerName - Provider name
 * @param {string} status - Connection status
 * @param {number} latencyMs - Latency in milliseconds
 * @param {string} message - Result message
 * @param {string} error - Error message if any
 */
function printDatabaseResponsePanel(
  providerName,
  status,
  latencyMs,
  message,
  error
) {
  let borderColor = "yellow";
  if (status === "connected") {
    borderColor = "green";
  } else if (status === "error") {
    borderColor = "red";
  }

  const responseInfo = {
    provider: providerName,
    status: status,
    latency_ms: Math.round(latencyMs * 100) / 100,
  };

  if (message) {
    responseInfo.message = message;
  }

  if (error) {
    responseInfo.error = error;
  }

  const colorFn = pc[borderColor] || pc.yellow;
  const title = pc.bold(
    colorFn(
      `Provider Health Response ← ${providerName.toUpperCase()} (${status.toUpperCase()})`
    )
  );
  printPanel(title, JSON.stringify(responseInfo, null, 2), borderColor);
}

// ============================================================================
// Response Class
// ============================================================================

/**
 * Response from a provider connection health check.
 */
export class ProviderConnectionResponse {
  constructor({
    provider,
    status,
    latencyMs = null,
    message = null,
    error = null,
    timestamp = null,
    configUsed = null,
  }) {
    this.provider = provider;
    this.status = status;
    this.latency_ms = latencyMs;
    this.message = message;
    this.error = error;
    this.timestamp = timestamp || new Date().toISOString();
    this.config_used = configUsed;
  }

  toJSON() {
    return {
      provider: this.provider,
      status: this.status,
      latency_ms: this.latency_ms,
      message: this.message,
      error: this.error,
      timestamp: this.timestamp,
      config_used: this.config_used,
    };
  }
}

export class ProviderHealthChecker {
  #configStore = null;
  #clientFactory = null;
  #runtimeOverride = null;

  /**
   * @param {Object} configStore - Static config store
   * @param {Object} runtimeOverride - Optional runtime override for proxy/client settings
   */
  constructor(configStore = null, runtimeOverride = null) {
    this.#configStore = configStore;
    this.#runtimeOverride = runtimeOverride;
    this.#clientFactory = new ProviderClientFactory(configStore);
  }

  get configStore() {
    return this.#configStore;
  }

  set configStore(value) {
    this.#configStore = value;
    this.#clientFactory.configStore = value;
  }

  get runtimeOverride() {
    return this.#runtimeOverride;
  }

  /**
   * Build config_used object for response
   */
  _buildConfigUsed(providerName, apiToken) {
    const mergedConfig = this.#clientFactory._getMergedConfigForProvider(
      providerName,
      this.#runtimeOverride
    );

    return {
      base_url: apiToken?.getBaseUrl?.() || null,
      proxy: mergedConfig.proxy,
      client: mergedConfig.client,
      auth_type: apiToken?.getAuthType?.() || null,
      has_provider_override: mergedConfig.has_provider_override,
      has_runtime_override: mergedConfig.has_runtime_override,
    };
  }

  async check(providerName) {
    const providerNameLower = providerName.toLowerCase();

    const TokenClass = getApiTokenClass(providerNameLower);
    if (!TokenClass) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: "error",
        error: `Unknown provider: ${providerName}`,
      });
    }

    const apiToken = new TokenClass(this.#configStore);
    const apiKeyResult = apiToken.getApiKey();
    const configUsed = this._buildConfigUsed(providerNameLower, apiToken);

    if (apiKeyResult.isPlaceholder) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: "not_implemented",
        message: apiKeyResult.placeholderMessage,
        configUsed,
      });
    }

    if (providerNameLower === "postgres") {
      return this._checkPostgres(apiToken, configUsed);
    } else if (providerNameLower === "redis") {
      return this._checkRedis(apiToken, configUsed);
    } else if (providerNameLower === "elasticsearch") {
      return this._checkElasticsearch(apiToken, configUsed);
    } else {
      return this._checkHttp(providerName, apiToken, apiKeyResult, configUsed);
    }
  }

  async _checkPostgres(apiToken, configUsed = null) {
    const startTime = performance.now();

    // Print database config panel
    printDatabaseConfigPanel("postgres", "Sequelize", configUsed);

    try {
      const sequelize = await apiToken.getClient();
      if (!sequelize) {
        const errorMsg =
          "Failed to create Sequelize instance. Check sequelize/pg installation and credentials.";
        printDatabaseResponsePanel(
          "postgres",
          "error",
          performance.now() - startTime,
          null,
          errorMsg
        );
        return new ProviderConnectionResponse({
          provider: "postgres",
          status: "error",
          error: errorMsg,
          configUsed,
        });
      }

      // Use Sequelize's authenticate() to test connection
      await sequelize.authenticate();
      const latencyMs = performance.now() - startTime;

      // Close the connection
      await sequelize.close();

      const message = "PostgreSQL connection successful (Sequelize)";
      printDatabaseResponsePanel(
        "postgres",
        "connected",
        latencyMs,
        message,
        null
      );

      return new ProviderConnectionResponse({
        provider: "postgres",
        status: "connected",
        latencyMs: Math.round(latencyMs * 100) / 100,
        message,
        configUsed,
      });
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      printDatabaseResponsePanel(
        "postgres",
        "error",
        latencyMs,
        null,
        e.message
      );
      return new ProviderConnectionResponse({
        provider: "postgres",
        status: "error",
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
        configUsed,
      });
    }
  }

  async _checkRedis(apiToken, configUsed = null) {
    const startTime = performance.now();

    // Print database config panel
    printDatabaseConfigPanel("redis", "ioredis", configUsed);

    try {
      const client = await apiToken.getClient();
      if (!client) {
        const errorMsg =
          "Failed to create Redis client. Check ioredis installation and credentials.";
        printDatabaseResponsePanel(
          "redis",
          "error",
          performance.now() - startTime,
          null,
          errorMsg
        );
        return new ProviderConnectionResponse({
          provider: "redis",
          status: "error",
          error: errorMsg,
          configUsed,
        });
      }

      const result = await client.ping();
      const latencyMs = performance.now() - startTime;
      await client.quit();

      if (result === "PONG") {
        const message = "Redis connection successful (PONG)";
        printDatabaseResponsePanel(
          "redis",
          "connected",
          latencyMs,
          message,
          null
        );
        return new ProviderConnectionResponse({
          provider: "redis",
          status: "connected",
          latencyMs: Math.round(latencyMs * 100) / 100,
          message,
          configUsed,
        });
      }

      const errorMsg = "PING did not return expected response";
      printDatabaseResponsePanel("redis", "error", latencyMs, null, errorMsg);
      return new ProviderConnectionResponse({
        provider: "redis",
        status: "error",
        error: errorMsg,
        configUsed,
      });
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      printDatabaseResponsePanel("redis", "error", latencyMs, null, e.message);
      return new ProviderConnectionResponse({
        provider: "redis",
        status: "error",
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
        configUsed,
      });
    }
  }

  async _checkElasticsearch(apiToken, configUsed = null) {
    // Use HTTP directly to support both Elasticsearch and OpenSearch
    // (the official @elastic/elasticsearch client rejects OpenSearch servers)
    // Uses proxy factory with YAML config for fetch dispatcher
    const startTime = performance.now();

    // Print database config panel
    printDatabaseConfigPanel(
      "elasticsearch",
      "HTTP (native fetch)",
      configUsed
    );

    try {
      const connectionUrl = apiToken.getConnectionUrl();

      // Parse the URL to extract credentials and build auth header
      // fetch() doesn't allow credentials in the URL directly
      const parsedUrl = new URL(connectionUrl);
      const username = parsedUrl.username;
      const password = parsedUrl.password;

      // Remove credentials from URL for fetch
      parsedUrl.username = "";
      parsedUrl.password = "";
      // Build health URL - ensure no double slashes
      const baseUrl = parsedUrl.toString().replace(/\/+$/, "");
      const healthUrl = `${baseUrl}/_cluster/health`;

      // Get dispatcher from factory with YAML proxy config
      const dispatcher = await this.#clientFactory._createDispatcher();

      const headers = { Accept: "application/json" };

      // Add Basic Auth header if credentials were in the URL
      if (username && password) {
        // Use fetch-auth-encoding package
        const auth = encodeAuth("basic", { username, password });
        headers["Authorization"] = auth.Authorization;
      }

      // Print request panel (for HTTP-based elasticsearch check)
      printHealthRequestPanel(
        "elasticsearch",
        "GET",
        healthUrl,
        headers,
        username ? "basic" : "none"
      );

      const fetchOptions = {
        method: "GET",
        headers,
      };

      // Add dispatcher if available (for proxy support)
      if (dispatcher) {
        fetchOptions.dispatcher = dispatcher;
      }

      const response = await fetch(healthUrl, fetchOptions);

      const latencyMs = performance.now() - startTime;

      // Get response headers as object
      const responseHeaders = {};
      response.headers.forEach((value, key) => {
        responseHeaders[key] = value;
      });

      if (response.ok) {
        const result = await response.json();

        if (result && result.cluster_name) {
          const clusterStatus = result.status || "unknown";
          const message = `Cluster '${result.cluster_name}' is ${clusterStatus}`;

          // Print success response panel
          printHealthResponsePanel(
            "elasticsearch",
            "connected",
            response.status,
            latencyMs,
            responseHeaders,
            result,
            null
          );

          return new ProviderConnectionResponse({
            provider: "elasticsearch",
            status: "connected",
            latencyMs: Math.round(latencyMs * 100) / 100,
            message,
            configUsed,
          });
        }

        const errorMsg = "Unexpected response from cluster health check";
        printHealthResponsePanel(
          "elasticsearch",
          "error",
          response.status,
          latencyMs,
          responseHeaders,
          result,
          errorMsg
        );
        return new ProviderConnectionResponse({
          provider: "elasticsearch",
          status: "error",
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: errorMsg,
          configUsed,
        });
      } else {
        const text = await response.text();
        const errorMsg = `HTTP ${response.status}: ${text.substring(0, 200)}`;
        printHealthResponsePanel(
          "elasticsearch",
          "error",
          response.status,
          latencyMs,
          responseHeaders,
          text.substring(0, 200),
          errorMsg
        );
        return new ProviderConnectionResponse({
          provider: "elasticsearch",
          status: "error",
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: errorMsg,
          configUsed,
        });
      }
    } catch (e) {
      const latencyMs = performance.now() - startTime;
      // Print error response panel for exceptions
      printHealthResponsePanel(
        "elasticsearch",
        "error",
        0,
        latencyMs,
        {},
        null,
        e.message
      );
      return new ProviderConnectionResponse({
        provider: "elasticsearch",
        status: "error",
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
        configUsed,
      });
    }
  }

  async _checkHttp(providerName, apiToken, apiKeyResult, configUsed = null) {
    const startTime = performance.now();

    // Print proxy/network config panel
    printProxyConfigPanel(providerName, apiToken, apiKeyResult, configUsed);

    if (!apiKeyResult.hasCredentials) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: "error",
        error: "No API credentials configured",
        configUsed,
      });
    }

    const baseUrl = apiToken.getBaseUrl();
    if (!baseUrl) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: "error",
        error: "No base URL configured",
        configUsed,
      });
    }

    const client = await this.#clientFactory.getClient(apiToken.providerName);
    if (!client) {
      return new ProviderConnectionResponse({
        provider: providerName,
        status: "error",
        error: "Failed to create HTTP client",
        configUsed,
      });
    }

    // Build request headers for logging (get from apiToken config)
    const healthEndpoint = apiToken.healthEndpoint;
    const fullUrl = `${baseUrl}${healthEndpoint}`;
    const authType =
      apiToken.getAuthType?.() || configUsed?.auth_type || "unknown";

    // Get headers configuration from apiToken
    const headersConfig = apiToken.getHeadersConfig?.() || {};
    const requestHeaders = {
      "User-Agent": "provider-api-getters/1.0",
      ...headersConfig,
    };

    // Add auth header for display (from apiKeyResult)
    const headerName = apiToken.getHeaderName?.() || "Authorization";
    if (apiKeyResult.apiKey) {
      requestHeaders[headerName] = apiKeyResult.apiKey;
    }

    // Print request panel
    printHealthRequestPanel(
      providerName,
      "GET",
      fullUrl,
      requestHeaders,
      authType
    );

    try {
      const response = await client.get(healthEndpoint);
      const latencyMs = performance.now() - startTime;

      // Get response headers (if available)
      const responseHeaders = response.headers || {};

      if (response.status >= 200 && response.status < 300) {
        const message = this._extractSuccessMessage(
          providerName,
          response.data
        );

        // Print success response panel
        printHealthResponsePanel(
          providerName,
          "connected",
          response.status,
          latencyMs,
          responseHeaders,
          response.data,
          null
        );

        return new ProviderConnectionResponse({
          provider: providerName,
          status: "connected",
          latencyMs: Math.round(latencyMs * 100) / 100,
          configUsed,
          message,
        });
      } else {
        const errorMsg = `HTTP ${response.status}: ${JSON.stringify(
          response.data
        )}`;

        // Print error response panel
        printHealthResponsePanel(
          providerName,
          "error",
          response.status,
          latencyMs,
          responseHeaders,
          response.data,
          errorMsg
        );

        return new ProviderConnectionResponse({
          provider: providerName,
          status: "error",
          latencyMs: Math.round(latencyMs * 100) / 100,
          error: errorMsg,
          configUsed,
        });
      }
    } catch (e) {
      const latencyMs = performance.now() - startTime;

      // Print error response panel for exceptions
      printHealthResponsePanel(
        providerName,
        "error",
        0,
        latencyMs,
        {},
        null,
        e.message
      );

      return new ProviderConnectionResponse({
        provider: providerName,
        status: "error",
        latencyMs: Math.round(latencyMs * 100) / 100,
        error: e.message,
        configUsed,
      });
    } finally {
      try {
        await client.close();
      } catch {
        // Ignore close errors
      }
    }
  }

  _extractSuccessMessage(providerName, data) {
    if (!data || typeof data !== "object") {
      return `Connected to ${providerName}`;
    }

    const providerLower = providerName.toLowerCase();

    if (providerLower === "figma") {
      const email = data.email;
      if (email) return `Connected as ${email}`;
    } else if (providerLower === "github") {
      const login = data.login;
      if (login) return `Connected as @${login}`;
    } else if (providerLower === "jira" || providerLower === "confluence") {
      const displayName = data.displayName;
      const email = data.emailAddress;
      if (displayName) return `Connected as ${displayName}`;
      if (email) return `Connected as ${email}`;
    } else if (["gemini", "openai", "gemini_openai"].includes(providerLower)) {
      const models = data.data;
      if (Array.isArray(models)) {
        return `Connected, ${models.length} models available`;
      }
    }

    return `Connected to ${providerName}`;
  }
}

let _checker = null;

/**
 * Check connectivity to a provider.
 *
 * Uses the ConfigStore singleton from @internal/static-config-property-management
 * to automatically load provider configuration.
 *
 * @param {string} providerName - Provider name (e.g., 'github', 'jira', 'figma')
 * @returns {Promise<ProviderConnectionResponse>} Health check result
 */
export async function checkProviderConnection(providerName) {
  if (_checker === null) {
    // Lazy-load ConfigStore singleton to avoid circular dependencies
    try {
      const { config } = await import(
        "@internal/static-config-property-management"
      );
      _checker = new ProviderHealthChecker(config);
    } catch {
      // Fallback to checker without config (will use env vars)
      _checker = new ProviderHealthChecker();
    }
  }
  return _checker.check(providerName);
}
