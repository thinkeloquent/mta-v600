#!/usr/bin/env node
/**
 * Redis Health Check - Standalone debugging script with explicit 7-step pattern.
 *
 * Flow: YamlConfig -> ProviderConfig -> ConnectionConfig -> ClientConfig -> Connect -> Query -> Response
 *
 * Run directly: node redis_health_check.mjs
 *
 * Uses:
 * - static_config for YAML configuration
 * - RedisApiToken for connection config resolution
 * - ioredis for native Redis connection
 */
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..', '..', '..');
const CONFIG_DIR = path.join(PROJECT_ROOT, 'common', 'config');

// ============================================================
// Load static config FIRST
// ============================================================
import { loadYamlConfig, config as staticConfig } from '@internal/app-static-config-yaml';
await loadYamlConfig({ configDir: CONFIG_DIR });

// ============================================================
// Provider API getter
// ============================================================
import { RedisApiToken } from '../../api_token/index.mjs';

/**
 * Print a section header.
 * @param {string} title - Section title
 */
function printSection(title) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Step: ${title}`);
  console.log('='.repeat(60));
}

/**
 * Print JSON data with indentation.
 * @param {Object} data - Data to print
 */
function printJson(data) {
  console.log(JSON.stringify(data, null, 2));
}

/**
 * Mask sensitive values for logging.
 * @param {string} value - Value to mask
 * @param {number} showChars - Characters to show before masking
 * @returns {string} Masked value
 */
function maskSensitive(value, showChars = 4) {
  if (!value) return '<none>';
  if (value.length <= showChars) return '*'.repeat(value.length);
  return value.substring(0, showChars) + '***';
}

/**
 * Redis Health Check - Explicit 7-step building block pattern.
 *
 * Flow: YamlConfig -> ProviderConfig -> ConnectionConfig -> ClientConfig -> Connect -> Query -> Response
 *
 * This pattern is identical across:
 * - FastAPI endpoints
 * - Fastify endpoints
 * - Standalone scripts (this file)
 * - CLI tools
 * - SDKs
 *
 * @param {Object} config - Configuration store (if null, uses staticConfig)
 * @returns {Promise<Object>} Health check result with success status, data/error, and configUsed metadata
 */
export async function checkRedisHealth(config = null) {
  // ============================================================
  // Step 1: YAML CONFIG LOADING
  // ============================================================
  printSection('1. YAML CONFIG LOADING');

  if (!config) {
    config = staticConfig;
  }

  const configSource = config._source || 'unknown';
  console.log(`  Loaded from: ${configSource}`);

  // ============================================================
  // Step 2: PROVIDER CONFIG EXTRACTION
  // ============================================================
  printSection('2. PROVIDER CONFIG EXTRACTION');

  const provider = new RedisApiToken(config);

  const providerConfig = {
    providerName: provider.providerName,
  };
  printJson(providerConfig);

  // ============================================================
  // Step 3: CONNECTION CONFIG RESOLUTION
  // ============================================================
  printSection('3. CONNECTION CONFIG RESOLUTION');

  const connectionConfig = provider.getConnectionConfig();
  const apiKeyResult = provider.getApiKey();

  const connConfig = {
    host: connectionConfig.host || 'localhost',
    port: connectionConfig.port || 6379,
    database: connectionConfig.database ?? 0,
    username: connectionConfig.username || undefined,
    hasPassword: !!apiKeyResult.apiKey,
  };
  printJson(connConfig);

  console.log(`  Has credentials: ${apiKeyResult.hasCredentials}`);
  console.log(`  Is placeholder: ${apiKeyResult.isPlaceholder}`);

  if (!apiKeyResult.hasCredentials || apiKeyResult.isPlaceholder) {
    return {
      success: false,
      error: 'Missing or placeholder credentials',
      configUsed: {
        provider: providerConfig,
        connection: connConfig,
      },
    };
  }

  // ============================================================
  // Step 4: CLIENT CONFIG (ioredis options)
  // ============================================================
  printSection('4. CLIENT CONFIG');

  // Try to import ioredis
  let Redis;
  try {
    const ioredis = await import('ioredis');
    Redis = ioredis.default || ioredis;
  } catch {
    console.log('  ERROR: ioredis not installed');
    console.log('  Install with: npm install ioredis');
    return {
      success: false,
      error: 'ioredis not installed',
      configUsed: {
        provider: providerConfig,
        connection: connConfig,
      },
    };
  }

  // Build ioredis client options
  // IMPORTANT: maxRetriesPerRequest limits retries to avoid long waits
  const clientConfig = {
    host: connConfig.host,
    port: connConfig.port,
    db: connConfig.database,
    username: connConfig.username,
    password: apiKeyResult.apiKey,
    connectTimeout: 10000,        // 10 second connection timeout
    maxRetriesPerRequest: 5,      // Limit retries (default is 20, too high)
    retryStrategy: (times) => {
      // Retry with exponential backoff, max 3 seconds
      const delay = Math.min(times * 200, 3000);
      console.log(`  Retry attempt ${times}, waiting ${delay}ms...`);
      return delay;
    },
    lazyConnect: true,            // Don't connect until explicitly called
  };

  console.log(`  Host: ${clientConfig.host}`);
  console.log(`  Port: ${clientConfig.port}`);
  console.log(`  Database: ${clientConfig.db}`);
  console.log(`  Username: ${clientConfig.username || 'N/A'}`);
  console.log(`  Password: ${maskSensitive(clientConfig.password)}`);
  console.log(`  Connect timeout: ${clientConfig.connectTimeout}ms`);
  console.log(`  Max retries per request: ${clientConfig.maxRetriesPerRequest}`);

  // ============================================================
  // Step 5: CONNECT
  // ============================================================
  printSection('5. CONNECT');

  const connectionUrl = `redis://${connConfig.username ? connConfig.username + ':****@' : ''}${connConfig.host}:${connConfig.port}/${connConfig.database}`;
  console.log(`  URL: ${connectionUrl}`);

  const client = new Redis(clientConfig);

  const startTime = performance.now();

  try {
    console.log('  Connecting...');
    await client.connect();
    console.log('  Connected!');

    // ============================================================
    // Step 6: QUERY (PING and INFO)
    // ============================================================
    printSection('6. QUERY');

    console.log('  Sending PING...');
    const pong = await client.ping();
    console.log(`  PING response: ${pong}`);

    console.log('  Getting server info...');
    const info = await client.info('server');
    const versionMatch = info.match(/redis_version:(\S+)/);
    const version = versionMatch ? versionMatch[1] : 'unknown';
    console.log(`  Redis version: ${version}`);

    const latencyMs = performance.now() - startTime;

    // ============================================================
    // Step 7: RESPONSE HANDLING
    // ============================================================
    printSection('7. RESPONSE HANDLING');

    console.log(`  Status: connected`);
    console.log(`  Latency: ${latencyMs.toFixed(2)}ms`);

    // Build configUsed for debugging
    const configUsed = {
      provider: providerConfig,
      connection: connConfig,
      clientOptions: {
        connectTimeout: clientConfig.connectTimeout,
        maxRetriesPerRequest: clientConfig.maxRetriesPerRequest,
      },
    };

    return {
      success: true,
      message: 'Connected to Redis',
      data: {
        host: connConfig.host,
        port: connConfig.port,
        database: connConfig.database,
        version,
        pong,
      },
      latencyMs,
      configUsed,
    };
  } catch (error) {
    const latencyMs = performance.now() - startTime;

    // ============================================================
    // Step 7: RESPONSE HANDLING (Error)
    // ============================================================
    printSection('7. RESPONSE HANDLING (Error)');

    console.log(`  Error: ${error.message}`);
    console.log(`  Latency: ${latencyMs.toFixed(2)}ms`);

    // Build configUsed for debugging
    const configUsed = {
      provider: providerConfig,
      connection: connConfig,
      clientOptions: {
        connectTimeout: clientConfig.connectTimeout,
        maxRetriesPerRequest: clientConfig.maxRetriesPerRequest,
      },
    };

    if (error.message.includes('NOAUTH') || error.message.includes('AUTH')) {
      console.log('  [Authentication Error]');
      return {
        success: false,
        error: 'Invalid password',
        latencyMs,
        configUsed,
      };
    } else if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
      console.log('  [Connection Error]');
      return {
        success: false,
        error: `Cannot connect to ${connConfig.host}:${connConfig.port}`,
        latencyMs,
        configUsed,
      };
    } else if (error.message.includes('max retries')) {
      console.log('  [Max Retries Exceeded]');
      return {
        success: false,
        error: `Connection failed after ${clientConfig.maxRetriesPerRequest} retries`,
        latencyMs,
        configUsed,
      };
    } else {
      console.log(`  [Exception: ${error.name}]`);
      return {
        success: false,
        error: error.message,
        latencyMs,
        configUsed,
      };
    }
  } finally {
    await client.quit().catch(() => {});
  }
}

// Run if executed directly
if (process.argv[1] === __filename) {
  console.log('\n');
  console.log('='.repeat(60));
  console.log('REDIS HEALTH CHECK - Explicit 7-Step Pattern');
  console.log('='.repeat(60));
  console.log('Flow: YamlConfig -> Provider -> Connection -> Client -> Connect -> Query -> Response');

  const result = await checkRedisHealth();

  console.log('\n' + '='.repeat(60));
  console.log('FINAL RESULT');
  console.log('='.repeat(60));
  console.log(JSON.stringify(result, null, 2));
}
