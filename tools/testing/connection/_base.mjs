#!/usr/bin/env node
/**
 * Base module for connection testing.
 *
 * Provides shared setup and utilities for provider connection tests.
 */
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..');

// Dynamic imports for internal modules
const { loadYamlConfig, config: staticConfig } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'app_static_config_yaml', 'src', 'index.mjs')
);
const { ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// Load static config
const configDir = resolve(PROJECT_ROOT, 'common', 'config');
await loadYamlConfig({ configDir });

// ANSI color codes
const colors = {
  green: '\x1b[92m',
  red: '\x1b[91m',
  yellow: '\x1b[93m',
  reset: '\x1b[0m',
};

const statusIcons = {
  connected: `${colors.green}✓${colors.reset}`,
  error: `${colors.red}✗${colors.reset}`,
  not_implemented: `${colors.yellow}○${colors.reset}`,
};

/**
 * Print a provider connection result in a formatted way.
 */
export function printResult(result) {
  const icon = statusIcons[result.status] || '?';

  console.log(`\n${'='.repeat(60)}`);
  console.log(`${icon} Provider: ${result.provider}`);
  console.log(`  Status: ${result.status}`);

  if (result.latency_ms !== null && result.latency_ms !== undefined) {
    console.log(`  Latency: ${result.latency_ms.toFixed(2)}ms`);
  }

  if (result.message) {
    console.log(`  Message: ${result.message}`);
  }

  if (result.error) {
    console.log(`  Error: ${colors.red}${result.error}${colors.reset}`);
  }

  console.log(`  Timestamp: ${result.timestamp}`);
  console.log(`${'='.repeat(60)}\n`);

  return result.status === 'connected';
}

/**
 * Test a single provider connection.
 */
export async function testProvider(providerName) {
  console.log(`\nTesting connection to: ${providerName}`);
  console.log('-'.repeat(40));

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check(providerName);

  return { success: printResult(result), result };
}

/**
 * Test multiple providers and return summary.
 */
export async function testAllProviders(providers) {
  const results = {
    connected: [],
    error: [],
    not_implemented: [],
  };

  for (const provider of providers) {
    const checker = new ProviderHealthChecker(staticConfig);
    const result = await checker.check(provider);
    printResult(result);
    results[result.status].push(provider);
  }

  return results;
}

/**
 * Print a summary of all test results.
 */
export function printSummary(results) {
  const total = results.connected.length + results.error.length + results.not_implemented.length;

  console.log('\n' + '='.repeat(60));
  console.log('SUMMARY');
  console.log('='.repeat(60));
  console.log(`Total providers tested: ${total}`);
  console.log(
    `${colors.green}✓ Connected:${colors.reset} ${results.connected.length} - ${results.connected.join(', ') || 'None'}`
  );
  console.log(
    `${colors.red}✗ Error:${colors.reset} ${results.error.length} - ${results.error.join(', ') || 'None'}`
  );
  console.log(
    `${colors.yellow}○ Not Implemented:${colors.reset} ${results.not_implemented.length} - ${results.not_implemented.join(', ') || 'None'}`
  );
  console.log('='.repeat(60) + '\n');
}

/**
 * Run a single provider test (entry point for individual scripts).
 */
export async function runSingleTest(providerName) {
  const { success } = await testProvider(providerName);
  process.exit(success ? 0 : 1);
}

/**
 * Run all provider tests (entry point for all_providers script).
 */
export async function runAllTests(providers) {
  const results = await testAllProviders(providers);
  printSummary(results);
  process.exit(results.error.length === 0 ? 0 : 1);
}
