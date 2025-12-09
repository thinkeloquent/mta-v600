/**
 * PostgreSQL - Connection Test (using pg)
 *
 * Note: PostgreSQL uses its own protocol, not HTTP.
 * This file demonstrates connection testing with pg (node-postgres).
 *
 * Authentication: Password
 * Default Port: 5432
 * Health Query: SELECT 1
 *
 * TLS/SSL Options:
 *   NODE_TLS_REJECT_UNAUTHORIZED=0  - Ignore all certificate errors
 *   REQUEST_CA_BUNDLE=/path/to/ca   - Custom CA bundle file
 *   SSL_CERT_FILE=/path/to/cert     - Custom SSL certificate file
 *   NODE_EXTRA_CA_CERTS=/path/to/ca - Additional CA certificates
 */

import pg from 'pg';
import { readFileSync } from 'node:fs';
const { Client, Pool } = pg;

// ============================================================================
// Configuration - Override these values
// ============================================================================

const CONFIG = {
  // Option 1: Full Connection URL
  DATABASE_URL: process.env.DATABASE_URL || '',

  // Option 2: Individual Components
  POSTGRES_HOST: process.env.POSTGRES_HOST || 'localhost',
  POSTGRES_PORT: parseInt(process.env.POSTGRES_PORT || '5432', 10),
  POSTGRES_USER: process.env.POSTGRES_USER || 'postgres',
  POSTGRES_PASSWORD: process.env.POSTGRES_PASSWORD || '',
  POSTGRES_DB: process.env.POSTGRES_DB || 'postgres',

  // Optional: SSL Configuration
  POSTGRES_SSLMODE: process.env.POSTGRES_SSLMODE || 'prefer',
  // Options: disable, allow, prefer, require, verify-ca, verify-full

  // Optional: TLS Configuration
  // Set to false to ignore certificate errors (default: false for testing)
  // NODE_TLS_REJECT_UNAUTHORIZED=0, REQUEST_CA_BUNDLE=null, SSL_CERT_FILE=null, NODE_EXTRA_CA_CERTS=null
  REJECT_UNAUTHORIZED: false,

  // Optional: Custom CA certificates (disabled by default for testing)
  CA_BUNDLE: null,
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
      options.ca = readFileSync(CONFIG.CA_BUNDLE).toString();
      console.log(`Using custom CA bundle: ${CONFIG.CA_BUNDLE}`);
    } catch (err) {
      console.warn(`Warning: Could not read CA bundle: ${err.message}`);
    }
  }

  return options;
}

// ============================================================================
// Create PostgreSQL Client
// ============================================================================

function createClient() {
  const tlsOptions = getTlsOptions();

  if (CONFIG.DATABASE_URL) {
    console.log(`Using connection URL: ${CONFIG.DATABASE_URL.replace(/:[^:@]+@/, ':***@')}`);
    return new Client({
      connectionString: CONFIG.DATABASE_URL,
      ssl: CONFIG.DATABASE_URL.includes('sslmode=') ? undefined : tlsOptions,
    });
  }

  const sslConfig = getSslConfig(tlsOptions);

  return new Client({
    host: CONFIG.POSTGRES_HOST,
    port: CONFIG.POSTGRES_PORT,
    user: CONFIG.POSTGRES_USER,
    password: CONFIG.POSTGRES_PASSWORD,
    database: CONFIG.POSTGRES_DB,
    ssl: sslConfig,
  });
}

function getSslConfig(tlsOptions) {
  switch (CONFIG.POSTGRES_SSLMODE) {
    case 'disable':
      return false;
    case 'require':
      return {
        ...tlsOptions,
        rejectUnauthorized: false,
      };
    case 'verify-ca':
    case 'verify-full':
      return tlsOptions;
    case 'allow':
    case 'prefer':
    default:
      return {
        ...tlsOptions,
        rejectUnauthorized: false,
      };
  }
}

// ============================================================================
// Health Check
// ============================================================================

async function healthCheck() {
  console.log('\n=== PostgreSQL Health Check ===\n');

  const client = createClient();

  try {
    await client.connect();
    console.log('Connected successfully!');

    const result = await client.query('SELECT 1 as health_check');

    console.log(`Query Result: ${JSON.stringify(result.rows[0])}`);

    return { success: true, result: result.rows[0] };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.end();
  }
}

// ============================================================================
// Sample Queries
// ============================================================================

async function getVersion() {
  console.log('\n=== PostgreSQL Version ===\n');

  const client = createClient();

  try {
    await client.connect();

    const result = await client.query('SELECT version()');

    console.log(`Version: ${result.rows[0].version}`);

    return { success: true, version: result.rows[0].version };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.end();
  }
}

async function listDatabases() {
  console.log('\n=== List Databases ===\n');

  const client = createClient();

  try {
    await client.connect();

    const result = await client.query(`
      SELECT datname FROM pg_database
      WHERE datistemplate = false
      ORDER BY datname
    `);

    console.log(`Found ${result.rows.length} databases`);
    result.rows.forEach((row) => {
      console.log(`  - ${row.datname}`);
    });

    return { success: true, databases: result.rows };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.end();
  }
}

async function listTables(schema = 'public') {
  console.log(`\n=== List Tables (${schema}) ===\n`);

  const client = createClient();

  try {
    await client.connect();

    const result = await client.query(`
      SELECT tablename FROM pg_tables
      WHERE schemaname = $1
      ORDER BY tablename
    `, [schema]);

    console.log(`Found ${result.rows.length} tables`);
    result.rows.forEach((row) => {
      console.log(`  - ${row.tablename}`);
    });

    return { success: true, tables: result.rows };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.end();
  }
}

async function getDatabaseSize() {
  console.log('\n=== Database Size ===\n');

  const client = createClient();

  try {
    await client.connect();

    const result = await client.query(`
      SELECT pg_size_pretty(pg_database_size(current_database())) as size
    `);

    console.log(`Database size: ${result.rows[0].size}`);

    return { success: true, size: result.rows[0].size };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.end();
  }
}

async function getConnections() {
  console.log('\n=== Active Connections ===\n');

  const client = createClient();

  try {
    await client.connect();

    const result = await client.query(`
      SELECT count(*) as connections FROM pg_stat_activity
    `);

    console.log(`Active connections: ${result.rows[0].connections}`);

    return { success: true, connections: result.rows[0].connections };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await client.end();
  }
}

// ============================================================================
// Run Tests
// ============================================================================

async function main() {
  console.log('PostgreSQL Connection Test');
  console.log('==========================');
  console.log(`Host: ${CONFIG.POSTGRES_HOST}:${CONFIG.POSTGRES_PORT}`);
  console.log(`Database: ${CONFIG.POSTGRES_DB}`);
  console.log(`User: ${CONFIG.POSTGRES_USER}`);
  console.log(`SSL Mode: ${CONFIG.POSTGRES_SSLMODE}`);
  console.log(`TLS Verify: ${CONFIG.REJECT_UNAUTHORIZED}`);
  console.log(`CA Bundle: ${CONFIG.CA_BUNDLE || 'System default'}`);

  await healthCheck();
  // await getVersion();
  // await listDatabases();
  // await listTables();
  // await getDatabaseSize();
  // await getConnections();
}

main().catch(console.error);
