/**
 * @internal/test-sensitive-data
 *
 * Centralized sensitive test data for test suites.
 *
 * This package provides a single source of truth for all test credentials,
 * tokens, PII data, and other sensitive information used in tests.
 *
 * @example
 * import { get, getAll, has, getMany } from '@internal/test-sensitive-data';
 *
 * // Simple flat access
 * const email = get('email');
 * const password = get('password');
 *
 * // Dot notation for nested/categorized data
 * const confluenceEmail = get('credentials.confluence.email');
 * const jiraToken = get('credentials.jira.token');
 *
 * // Check if a key exists
 * if (has('credentials.figma.token')) { ... }
 *
 * // Get multiple values at once
 * const [email, password, apiKey] = getMany('email', 'password', 'api_key');
 *
 * // Get all data
 * const allData = getAll();
 */

export {
  get,
  getAll,
  has,
  getMany,
  getOrDefault,
  loadData,
  _resetCache,
} from './loader.mjs';
