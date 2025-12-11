#!/usr/bin/env node
/**
 * PostgreSQL Connection Test - Node.js Client Integration
 *
 * Authentication: Password
 * Protocol: PostgreSQL wire protocol (not HTTP)
 * Health Check: SELECT 1
 *
 * Uses internal packages:
 *   - @internal/provider_api_getters: Credential resolution
 *   - @internal/app-static-config-yaml: YAML configuration loading
 *
 * Note: PostgreSQL uses its own wire protocol, not HTTP.
 * This file uses pg (node-postgres) for connections.
 */
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import pg from 'pg';

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
const { PostgresApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new PostgresApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

// Check if SSL should be disabled via environment variables
// SSL_CERT_VERIFY=0 or NODE_TLS_REJECT_UNAUTHORIZED=0 means disable SSL
const sslCertVerify = process.env.SSL_CERT_VERIFY || '';
const nodeTls = process.env.NODE_TLS_REJECT_UNAUTHORIZED || '';
const disableSsl = sslCertVerify === '0' || nodeTls === '0';

const CONFIG = {
  // From provider_api_getters or environment
  POSTGRES_HOST: process.env.POSTGRES_HOST || 'localhost',
  POSTGRES_PORT: parseInt(process.env.POSTGRES_PORT || '5432', 10),
  POSTGRES_USER: apiKeyResult.username || process.env.POSTGRES_USER || 'postgres',
  POSTGRES_PASSWORD: apiKeyResult.apiKey || process.env.POSTGRES_PASSWORD || '',
  POSTGRES_DB: process.env.POSTGRES_DB || 'postgres',
  POSTGRES_SCHEMA: process.env.POSTGRES_SCHEMA || 'public',

  // Connection URL (alternative)
  DATABASE_URL: process.env.DATABASE_URL || '',

  // SSL configuration
  // When SSL_CERT_VERIFY=0 or NODE_TLS_REJECT_UNAUTHORIZED=0, disable SSL entirely
  DISABLE_SSL: disableSsl,

  // Debug
  DEBUG: !['false', '0'].includes((process.env.DEBUG || '').toLowerCase()),
};

function getConnectionUrl() {
  if (CONFIG.DATABASE_URL) {
    return CONFIG.DATABASE_URL;
  }
  return `postgresql://${CONFIG.POSTGRES_USER}:${CONFIG.POSTGRES_PASSWORD}@${CONFIG.POSTGRES_HOST}:${CONFIG.POSTGRES_PORT}/${CONFIG.POSTGRES_DB}`;
}

// ============================================================================
// Health Check
// ============================================================================
async function healthCheck() {
  console.log('\n=== PostgreSQL Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('postgres');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Sample Operations using pg
// ============================================================================
async function healthCheckPg() {
  console.log('\n=== PostgreSQL Health Check (pg) ===\n');

  const { Pool } = pg;

  console.log(`Connecting to: ${CONFIG.POSTGRES_HOST}:${CONFIG.POSTGRES_PORT}/${CONFIG.POSTGRES_DB}`);
  console.log(`SSL disabled: ${CONFIG.DISABLE_SSL} (SSL_CERT_VERIFY=${sslCertVerify || 'not set'}, NODE_TLS_REJECT_UNAUTHORIZED=${nodeTls || 'not set'})`);

  // Configure SSL: false = no SSL, undefined = let pg decide
  const sslConfig = CONFIG.DISABLE_SSL ? false : undefined;

  const pool = new Pool({
    host: CONFIG.POSTGRES_HOST,
    port: CONFIG.POSTGRES_PORT,
    user: CONFIG.POSTGRES_USER,
    password: CONFIG.POSTGRES_PASSWORD,
    database: CONFIG.POSTGRES_DB,
    ssl: sslConfig,
  });

  try {
    const client = await pool.connect();

    try {
      // Test connection
      const result = await client.query('SELECT 1 as test');
      console.log(`SELECT 1: ${result.rows[0].test}`);

      // Get version
      const versionResult = await client.query('SELECT version()');
      console.log(`Version: ${versionResult.rows[0].version}`);

      // Get current database
      const dbResult = await client.query('SELECT current_database()');
      console.log(`Database: ${dbResult.rows[0].current_database}`);

      return { success: true, data: { version: versionResult.rows[0].version } };
    } finally {
      client.release();
    }
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await pool.end();
  }
}

async function sampleOperations() {
  console.log('\n=== Sample PostgreSQL Operations ===\n');

  const { Pool } = pg;

  // Configure SSL: false = no SSL, undefined = let pg decide
  const sslConfig = CONFIG.DISABLE_SSL ? false : undefined;

  const pool = new Pool({
    host: CONFIG.POSTGRES_HOST,
    port: CONFIG.POSTGRES_PORT,
    user: CONFIG.POSTGRES_USER,
    password: CONFIG.POSTGRES_PASSWORD,
    database: CONFIG.POSTGRES_DB,
    ssl: sslConfig,
  });

  try {
    const client = await pool.connect();

    try {
      // List schemas
      const schemasResult = await client.query(`
        SELECT schema_name
        FROM information_schema.schemata
        ORDER BY schema_name
        LIMIT 10
      `);
      console.log('Schemas:');
      schemasResult.rows.forEach((row) => {
        console.log(`  - ${row.schema_name}`);
      });

      // List tables in public schema
      const tablesResult = await client.query(`
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = $1
        ORDER BY table_name
        LIMIT 10
      `, [CONFIG.POSTGRES_SCHEMA]);
      console.log(`\nTables in ${CONFIG.POSTGRES_SCHEMA}:`);
      tablesResult.rows.forEach((row) => {
        console.log(`  - ${row.table_name}`);
      });

      // Get database size
      const sizeResult = await client.query(`
        SELECT pg_size_pretty(pg_database_size(current_database())) as size
      `);
      console.log(`\nDatabase size: ${sizeResult.rows[0].size}`);

      return { success: true };
    } finally {
      client.release();
    }
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await pool.end();
  }
}

// ============================================================================
// Run Tests
// ============================================================================
async function main() {
  console.log('PostgreSQL Connection Test (Node.js Client Integration)');
  console.log('='.repeat(55));
  console.log(`Host: ${CONFIG.POSTGRES_HOST}:${CONFIG.POSTGRES_PORT}`);
  console.log(`Database: ${CONFIG.POSTGRES_DB}`);
  console.log(`User: ${CONFIG.POSTGRES_USER}`);
  console.log(`Schema: ${CONFIG.POSTGRES_SCHEMA}`);
  console.log(`SSL Disabled: ${CONFIG.DISABLE_SSL}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await healthCheckPg();
  // await sampleOperations();
}

main().catch(console.error);
