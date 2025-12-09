#!/usr/bin/env node
/**
 * Redis Connection Test - Node.js Client Integration
 *
 * Authentication: Password or ACL (username:password)
 * Protocol: Redis protocol (not HTTP)
 * Health Check: PING command
 *
 * Uses internal packages:
 *   - @internal/provider_api_getters: Credential resolution
 *   - @internal/app-static-config-yaml: YAML configuration loading
 *
 * Note: Redis uses its own protocol, not HTTP. This file uses ioredis.
 */
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import Redis from 'ioredis';

// ============================================================================
// Project Setup
// ============================================================================
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..', '..');

// Load static config
const { loadYamlConfig, config: staticConfig } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'app-static-config-yaml', 'src', 'index.mjs')
);
const configDir = resolve(PROJECT_ROOT, 'common', 'config');
await loadYamlConfig({ configDir });

// Import internal packages
const { RedisApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new RedisApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters or environment
  REDIS_HOST: process.env.REDIS_HOST || 'localhost',
  REDIS_PORT: parseInt(process.env.REDIS_PORT || '6379', 10),
  REDIS_PASSWORD: apiKeyResult.apiKey || process.env.REDIS_PASSWORD || '',
  REDIS_USERNAME: apiKeyResult.username || process.env.REDIS_USERNAME || '',
  REDIS_DB: parseInt(process.env.REDIS_DB || '0', 10),

  // Optional: TLS Configuration
  REDIS_USE_SSL: (process.env.REDIS_USE_SSL || '').toLowerCase() === 'true',

  // Debug
  DEBUG: !['false', '0'].includes((process.env.DEBUG || '').toLowerCase()),
};

// ============================================================================
// Health Check
// ============================================================================
async function healthCheck() {
  console.log('\n=== Redis Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('redis');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Sample Operations using ioredis
// ============================================================================
async function healthCheckIoredis() {
  console.log('\n=== Redis Health Check (ioredis) ===\n');

  console.log(`Connecting to: ${CONFIG.REDIS_HOST}:${CONFIG.REDIS_PORT}/${CONFIG.REDIS_DB}`);

  const redisOptions = {
    host: CONFIG.REDIS_HOST,
    port: CONFIG.REDIS_PORT,
    db: CONFIG.REDIS_DB,
    lazyConnect: true,
  };

  if (CONFIG.REDIS_PASSWORD) {
    redisOptions.password = CONFIG.REDIS_PASSWORD;
  }
  if (CONFIG.REDIS_USERNAME) {
    redisOptions.username = CONFIG.REDIS_USERNAME;
  }
  if (CONFIG.REDIS_USE_SSL) {
    redisOptions.tls = {};
  }

  const client = new Redis(redisOptions);

  try {
    await client.connect();

    // Test connection
    const pong = await client.ping();
    console.log(`PING: ${pong}`);

    // Get server info
    const info = await client.info('server');
    const lines = info.split('\n');
    const version = lines.find((l) => l.startsWith('redis_version:'))?.split(':')[1]?.trim();
    const os = lines.find((l) => l.startsWith('os:'))?.split(':')[1]?.trim();
    console.log(`Redis Version: ${version}`);
    console.log(`OS: ${os}`);

    return { success: true, data: { ping: pong, version } };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.quit();
  }
}

async function sampleOperations() {
  console.log('\n=== Sample Redis Operations ===\n');

  const redisOptions = {
    host: CONFIG.REDIS_HOST,
    port: CONFIG.REDIS_PORT,
    db: CONFIG.REDIS_DB,
    lazyConnect: true,
  };

  if (CONFIG.REDIS_PASSWORD) {
    redisOptions.password = CONFIG.REDIS_PASSWORD;
  }
  if (CONFIG.REDIS_USERNAME) {
    redisOptions.username = CONFIG.REDIS_USERNAME;
  }
  if (CONFIG.REDIS_USE_SSL) {
    redisOptions.tls = {};
  }

  const client = new Redis(redisOptions);

  try {
    await client.connect();

    // SET/GET
    await client.set('test:key', 'hello world');
    const value = await client.get('test:key');
    console.log(`SET/GET: ${value}`);

    // HSET/HGET
    await client.hset('test:hash', 'field1', 'value1', 'field2', 'value2');
    const hashValue = await client.hgetall('test:hash');
    console.log(`HSET/HGETALL:`, hashValue);

    // LIST
    await client.rpush('test:list', 'item1', 'item2', 'item3');
    const listValue = await client.lrange('test:list', 0, -1);
    console.log(`RPUSH/LRANGE:`, listValue);

    // Cleanup
    await client.del('test:key', 'test:hash', 'test:list');
    console.log('Cleanup: Deleted test keys');

    return { success: true };
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
  console.log('Redis Connection Test (Node.js Client Integration)');
  console.log('='.repeat(49));
  console.log(`Host: ${CONFIG.REDIS_HOST}:${CONFIG.REDIS_PORT}`);
  console.log(`Database: ${CONFIG.REDIS_DB}`);
  console.log(`SSL: ${CONFIG.REDIS_USE_SSL}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await healthCheckIoredis();
  // await sampleOperations();
}

main().catch(console.error);
