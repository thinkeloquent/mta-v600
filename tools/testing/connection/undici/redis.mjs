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
 */

import Redis from 'ioredis';

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
  REJECT_UNAUTHORIZED: true, // Set to false to skip TLS verification (testing only)
};

// ============================================================================
// Create Redis Client
// ============================================================================

function createClient() {
  if (CONFIG.REDIS_URL) {
    console.log(`Using connection URL: ${CONFIG.REDIS_URL.replace(/:[^:@]+@/, ':***@')}`);
    return new Redis(CONFIG.REDIS_URL, {
      tls: CONFIG.REDIS_URL.startsWith('rediss://') ? {
        rejectUnauthorized: CONFIG.REJECT_UNAUTHORIZED,
      } : undefined,
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
    options.tls = {
      rejectUnauthorized: CONFIG.REJECT_UNAUTHORIZED,
    };
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

  await healthCheck();
  // await serverInfo();
  // await basicOperations();
  // await listKeys('*');
  // await getDatabaseSize();
}

main().catch(console.error);
