#!/usr/bin/env node
/**
 * PostgreSQL Health Check - Standalone debugging script
 *
 * Run directly: node postgres_health_check.mjs
 *
 * Uses:
 * - static_config for YAML configuration
 * - PostgresApiToken for connection config resolution
 * - pg for native PostgreSQL connection
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
import { PostgresApiToken } from '../../api_token/index.mjs';

export async function checkPostgresHealth() {
  console.log('='.repeat(60));
  console.log('POSTGRESQL HEALTH CHECK');
  console.log('='.repeat(60));

  // Initialize provider from static config
  const provider = new PostgresApiToken(staticConfig);
  const apiKeyResult = provider.getApiKey();
  const connectionConfig = provider.getConnectionConfig();

  // Debug output
  console.log('\n[Config]');
  console.log(`  Host: ${connectionConfig.host || 'N/A'}`);
  console.log(`  Port: ${connectionConfig.port || 'N/A'}`);
  console.log(`  Database: ${connectionConfig.database || 'N/A'}`);
  console.log(`  Username: ${connectionConfig.username || 'N/A'}`);
  console.log(`  Has credentials: ${apiKeyResult.hasCredentials}`);
  console.log(`  Is placeholder: ${apiKeyResult.isPlaceholder}`);

  if (!apiKeyResult.hasCredentials || apiKeyResult.isPlaceholder) {
    console.log('\n[ERROR] Missing or placeholder credentials');
    return { success: false, error: 'Missing credentials' };
  }

  // Try to import pg
  let pg;
  try {
    pg = await import('pg');
  } catch {
    console.log('\n[ERROR] pg not installed');
    console.log('  Install with: npm install pg');
    return { success: false, error: 'pg not installed' };
  }

  const { Client } = pg.default || pg;

  // Build connection parameters
  const host = connectionConfig.host || 'localhost';
  const port = connectionConfig.port || 5432;
  const database = connectionConfig.database || 'postgres';
  const username = connectionConfig.username || 'postgres';
  const password = apiKeyResult.apiKey;

  // Check if SSL should be disabled via environment variables
  // SSL_CERT_VERIFY=0 or NODE_TLS_REJECT_UNAUTHORIZED=0 means disable SSL
  const sslCertVerify = process.env.SSL_CERT_VERIFY || '';
  const nodeTls = process.env.NODE_TLS_REJECT_UNAUTHORIZED || '';
  const disableSsl = sslCertVerify === '0' || nodeTls === '0';

  console.log('\n[Connecting]');
  console.log(`  postgresql://${username}:****@${host}:${port}/${database}`);
  console.log(`  SSL disabled: ${disableSsl} (SSL_CERT_VERIFY=${sslCertVerify || 'not set'}, NODE_TLS_REJECT_UNAUTHORIZED=${nodeTls || 'not set'})`);

  // Configure SSL: false = no SSL, undefined = let pg decide
  const sslConfig = disableSsl ? false : undefined;

  const client = new Client({
    host,
    port,
    database,
    user: username,
    password,
    connectionTimeoutMillis: 10000,
    ssl: sslConfig,
  });

  try {
    // Connect
    await client.connect();
    console.log('\n[Connection Established]');

    // Run health check query
    const result = await client.query('SELECT 1 as check');
    const versionResult = await client.query('SELECT version()');
    const version = versionResult.rows[0].version;

    console.log('\n[Query Results]');
    console.log(`  SELECT 1: ${result.rows[0].check}`);
    console.log(`  Version: ${version.length > 60 ? version.substring(0, 60) + '...' : version}`);

    return {
      success: true,
      message: 'Connected to PostgreSQL',
      data: {
        host,
        port,
        database,
        version,
      },
    };
  } catch (error) {
    if (error.code === '28P01') {
      console.log('\n[Authentication Error]');
      console.log(`  ${error.message}`);
      return {
        success: false,
        error: 'Invalid password',
      };
    } else if (error.code === '3D000') {
      console.log('\n[Database Error]');
      console.log(`  ${error.message}`);
      return {
        success: false,
        error: `Database '${database}' does not exist`,
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
    await client.end().catch(() => {});
  }
}

// Run if executed directly
if (process.argv[1] === __filename) {
  console.log('\n');
  const result = await checkPostgresHealth();
  console.log('\n' + '='.repeat(60));
  console.log('RESULT');
  console.log('='.repeat(60));
  console.log(JSON.stringify(result, null, 2));
}
