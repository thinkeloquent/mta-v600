/**
 * Loader for centralized sensitive test data.
 *
 * Provides functions to access test data from the YAML configuration file.
 * Supports both flat key access and dot notation for nested values.
 *
 * @example
 * import { get, getAll, has, getMany } from '@internal/test-sensitive-data';
 *
 * // Flat access
 * const email = get('email');
 *
 * // Dot notation for nested values
 * const confluenceEmail = get('credentials.confluence.email');
 *
 * // Check if a key exists
 * if (has('credentials.jira.token')) { ... }
 *
 * // Get multiple values at once
 * const [email, password] = getMany('email', 'password');
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import yaml from 'js-yaml';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/** @type {Record<string, any> | null} */
let _data = null;

/**
 * Load data from the YAML file (cached after first load).
 * @returns {Record<string, any>} The parsed YAML data
 */
export function loadData() {
  if (_data === null) {
    const yamlPath = join(__dirname, '..', 'sensitive-data.yaml');
    const content = readFileSync(yamlPath, 'utf-8');
    _data = yaml.load(content);
  }
  return _data;
}

/**
 * Get a value by key, supporting dot notation for nested values.
 *
 * @param {string} path - The key path (e.g., 'email' or 'credentials.confluence.email')
 * @returns {any} The value at the path, or undefined if not found
 *
 * @example
 * get('email')                      // 'test@example.com'
 * get('credentials.email')          // 'test@example.com'
 * get('credentials.confluence.email') // 'confluence-test@example.com'
 * get('nonexistent')                // undefined
 */
export function get(path) {
  const data = loadData();

  // Try flat key first
  if (!path.includes('.') && path in data) {
    return data[path];
  }

  // Try dot notation path
  const keys = path.split('.');
  let result = data;

  for (const key of keys) {
    if (result === null || result === undefined) {
      return undefined;
    }
    if (typeof result !== 'object') {
      return undefined;
    }
    result = result[key];
  }

  return result;
}

/**
 * Get all data as a plain object.
 * @returns {Record<string, any>} The complete data object
 */
export function getAll() {
  return loadData();
}

/**
 * Check if a key exists in the data.
 *
 * @param {string} path - The key path to check
 * @returns {boolean} True if the key exists and has a defined value
 *
 * @example
 * has('email')                      // true
 * has('credentials.confluence.email') // true
 * has('nonexistent')                // false
 */
export function has(path) {
  return get(path) !== undefined;
}

/**
 * Get multiple values at once.
 *
 * @param {...string} paths - The key paths to retrieve
 * @returns {any[]} An array of values in the same order as the paths
 *
 * @example
 * const [email, password] = getMany('email', 'password');
 * const [jiraEmail, jiraToken] = getMany('credentials.jira.email', 'credentials.jira.token');
 */
export function getMany(...paths) {
  return paths.map((p) => get(p));
}

/**
 * Get a value with a default fallback if the key doesn't exist.
 *
 * @param {string} path - The key path
 * @param {any} defaultValue - The default value to return if key not found
 * @returns {any} The value at the path, or the default value
 *
 * @example
 * getOrDefault('email', 'fallback@example.com')  // 'test@example.com'
 * getOrDefault('nonexistent', 'default')         // 'default'
 */
export function getOrDefault(path, defaultValue) {
  const value = get(path);
  return value !== undefined ? value : defaultValue;
}

/**
 * Reset the cached data (useful for testing the loader itself).
 * @internal
 */
export function _resetCache() {
  _data = null;
}
