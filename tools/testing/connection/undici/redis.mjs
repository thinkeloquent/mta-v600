/**
 * Redis - Connection Test (using ioredis)
 *
 * Note: Redis uses its own protocol, not HTTP.
 * This file demonstrates connection testing with ioredis.
 * For HTTP-based Redis (like Redis REST API), use the httpRedis example.
 *
 * Authentication: Password or ACL (username:password)
 * Default Port: 6379
 * Health Command: PING
 *
 * TLS/SSL Options:
 *   NODE_TLS_REJECT_UNAUTHORIZED=0  - Ignore all certificate errors
 *   REQUEST_CA_BUNDLE=/path/to/ca   - Custom CA bundle file
 *   SSL_CERT_FILE=/path/to/cert     - Custom SSL certificate file
 *   NODE_EXTRA_CA_CERTS=/path/to/ca - Additional CA certificates
 */

import Redis from 'ioredis';
import { readFileSync } from 'node:fs';

// ============================================================================
// Configuration - Override these values
// ============================================================================

const CONFIG = {
  // Option 1: Full Connection URL
  REDIS_URL: process.env.REDIS_URL || '',

  // Option 2: Individual Components
  REDIS_HOST: process.env.REDIS_HOST || 'localhost',
  REDIS_PORT: parseInt(process.env.REDIS_PORT || '6379', 10),
  REDIS_USERNAME: process.env.REDIS_USERNAME || '',
  REDIS_PASSWORD: process.env.REDIS_PASSWORD || '',
  REDIS_DB: parseInt(process.env.REDIS_DB || '0', 10),
  REDIS_TLS: process.env.REDIS_TLS || 'false', // 'true' for TLS

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

function getTlsOptions() {
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
// Create Redis Client
// ============================================================================

function createClient() {
  const tlsOptions = getTlsOptions();

  if (CONFIG.REDIS_URL) {
    console.log(`Using connection URL: ${CONFIG.REDIS_URL.replace(/:[^:@]+@/, ':***@')}`);
    return new Redis(CONFIG.REDIS_URL, {
      tls: CONFIG.REDIS_URL.startsWith('rediss://') ? tlsOptions : undefined,
    });
  }

  const useTls = CONFIG.REDIS_TLS === 'true' || CONFIG.REDIS_PORT === 25061;

  const options = {
    host: CONFIG.REDIS_HOST,
    port: CONFIG.REDIS_PORT,
    db: CONFIG.REDIS_DB,
  };

  if (CONFIG.REDIS_PASSWORD) {
    options.password = CONFIG.REDIS_PASSWORD;
  }

  if (CONFIG.REDIS_USERNAME) {
    options.username = CONFIG.REDIS_USERNAME;
  }

  if (useTls) {
    options.tls = tlsOptions;
  }

  console.log(`Connecting to: ${CONFIG.REDIS_HOST}:${CONFIG.REDIS_PORT}`);
  return new Redis(options);
}

// ============================================================================
// Health Check
// ============================================================================

async function healthCheck() {
  console.log('\n=== Redis Health Check ===\n');

  const client = createClient();

  try {
    const result = await client.ping();

    console.log(`PING Response: ${result}`);
    console.log('Connection successful!');

    return { success: result === 'PONG', result };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.quit();
  }
}

// ============================================================================
// Sample Commands
// ============================================================================

async function serverInfo() {
  console.log('\n=== Server Info ===\n');

  const client = createClient();

  try {
    const info = await client.info();

    // Parse key info
    const lines = info.split('\n');
    const version = lines.find((l) => l.startsWith('redis_version:'));
    const memory = lines.find((l) => l.startsWith('used_memory_human:'));
    const clients = lines.find((l) => l.startsWith('connected_clients:'));

    console.log(version);
    console.log(memory);
    console.log(clients);

    return { success: true, info };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.quit();
  }
}

async function basicOperations() {
  console.log('\n=== Basic Operations ===\n');

  const client = createClient();

  try {
    // SET
    const setResult = await client.set('test:key', 'Hello World');
    console.log(`SET test:key: ${setResult}`);

    // GET
    const getResult = await client.get('test:key');
    console.log(`GET test:key: ${getResult}`);

    // DEL
    const delResult = await client.del('test:key');
    console.log(`DEL test:key: ${delResult}`);

    // Verify deletion
    const verifyResult = await client.get('test:key');
    console.log(`GET test:key (after delete): ${verifyResult}`);

    return { success: true };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.quit();
  }
}

async function listKeys(pattern = '*') {
  console.log(`\n=== List Keys: ${pattern} ===\n`);

  const client = createClient();

  try {
    const keys = await client.keys(pattern);

    console.log(`Found ${keys.length} keys`);
    keys.slice(0, 20).forEach((key) => {
      console.log(`  - ${key}`);
    });

    return { success: true, keys };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.quit();
  }
}

async function getDatabaseSize() {
  console.log('\n=== Database Size ===\n');

  const client = createClient();

  try {
    const size = await client.dbsize();
    console.log(`Database size: ${size} keys`);

    return { success: true, size };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.quit();
  }
}

// ============================================================================
// Run Tests
// ============================================================================

async function main() {
  console.log('Redis Connection Test');
  console.log('=====================');
  console.log(`Host: ${CONFIG.REDIS_HOST}:${CONFIG.REDIS_PORT}`);
  console.log(`Database: ${CONFIG.REDIS_DB}`);
  console.log(`TLS: ${CONFIG.REDIS_TLS}`);
  console.log(`TLS Verify: ${CONFIG.REJECT_UNAUTHORIZED}`);
  console.log(`CA Bundle: ${CONFIG.CA_BUNDLE || 'System default'}`);

  await healthCheck();
  // await serverInfo();
  // await basicOperations();
  // await listKeys('*');
  // await getDatabaseSize();
}

main().catch(console.error);
