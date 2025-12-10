#!/usr/bin/env node
/**
 * Redis Health Check - Standalone debugging script
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

export async function checkRedisHealth() {
  console.log('='.repeat(60));
  console.log('REDIS HEALTH CHECK');
  console.log('='.repeat(60));

  // Initialize provider from static config
  const provider = new RedisApiToken(staticConfig);
  const apiKeyResult = provider.getApiKey();
  const connectionConfig = provider.getConnectionConfig();

  // Debug output
  console.log('\n[Config]');
  console.log(`  Host: ${connectionConfig.host || 'N/A'}`);
  console.log(`  Port: ${connectionConfig.port || 'N/A'}`);
  console.log(`  Database: ${connectionConfig.database ?? 'N/A'}`);
  console.log(`  Username: ${connectionConfig.username || 'N/A'}`);
  console.log(`  Has credentials: ${apiKeyResult.hasCredentials}`);
  console.log(`  Is placeholder: ${apiKeyResult.isPlaceholder}`);

  if (!apiKeyResult.hasCredentials || apiKeyResult.isPlaceholder) {
    console.log('\n[ERROR] Missing or placeholder credentials');
    return { success: false, error: 'Missing credentials' };
  }

  // Try to import ioredis
  let Redis;
  try {
    const ioredis = await import('ioredis');
    Redis = ioredis.default || ioredis;
  } catch {
    console.log('\n[ERROR] ioredis not installed');
    console.log('  Install with: npm install ioredis');
    return { success: false, error: 'ioredis not installed' };
  }

  // Build connection parameters
  const host = connectionConfig.host || 'localhost';
  const port = connectionConfig.port || 6379;
  const db = connectionConfig.database ?? 0;
  const username = connectionConfig.username || undefined;
  const password = apiKeyResult.apiKey;

  console.log('\n[Connecting]');
  console.log(`  redis://${username ? username + ':****@' : ''}${host}:${port}/${db}`);

  const client = new Redis({
    host,
    port,
    db,
    username,
    password,
    connectTimeout: 10000,
    lazyConnect: true,
  });

  try {
    // Connect
    await client.connect();
    console.log('\n[Connection Established]');

    // Run health check - PING
    const pong = await client.ping();
    const info = await client.info('server');
    const versionMatch = info.match(/redis_version:(\S+)/);
    const version = versionMatch ? versionMatch[1] : 'unknown';

    console.log('\n[Query Results]');
    console.log(`  PING: ${pong}`);
    console.log(`  Version: ${version}`);

    return {
      success: true,
      message: 'Connected to Redis',
      data: {
        host,
        port,
        database: db,
        version,
        pong,
      },
    };
  } catch (error) {
    if (error.message.includes('NOAUTH') || error.message.includes('AUTH')) {
      console.log('\n[Authentication Error]');
      console.log(`  ${error.message}`);
      return {
        success: false,
        error: 'Invalid password',
      };
    } else if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
      console.log('\n[Connection Error]');
      console.log(`  ${error.message}`);
      return {
        success: false,
        error: `Cannot connect to ${host}:${port}`,
      };
    } else {
      console.log('\n[Exception]');
      console.log(`  ${error.name}: ${error.message}`);
      return {
        success: false,
        error: error.message,
      };
    }
  } finally {
    await client.quit().catch(() => {});
  }
}

// Run if executed directly
if (process.argv[1] === __filename) {
  console.log('\n');
  const result = await checkRedisHealth();
  console.log('\n' + '='.repeat(60));
  console.log('RESULT');
  console.log('='.repeat(60));
  console.log(JSON.stringify(result, null, 2));
}
