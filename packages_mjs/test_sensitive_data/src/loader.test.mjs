/**
 * Tests for the sensitive test data loader.
 */
import { describe, it, expect } from 'vitest';
import { get, getAll, has, getMany, getOrDefault, _resetCache } from './loader.mjs';

describe('test-sensitive-data loader', () => {
  describe('get()', () => {
    it('should get flat key values', () => {
      expect(get('email')).toBe('test@example.com');
      expect(get('username')).toBe('testuser');
      expect(get('password')).toBe('TestPassword123!');
      expect(get('api_key')).toBe('sk-test-1234567890abcdef');
    });

    it('should get nested values with dot notation', () => {
      expect(get('credentials.email')).toBe('test@example.com');
      expect(get('credentials.confluence.email')).toBe('confluence-test@example.com');
      expect(get('credentials.jira.token')).toBe('jira-test-token-xyz789');
      expect(get('aws.access_key_id')).toBe('AKIAIOSFODNN7EXAMPLE');
    });

    it('should return undefined for non-existent keys', () => {
      expect(get('nonexistent')).toBeUndefined();
      expect(get('credentials.nonexistent')).toBeUndefined();
      expect(get('credentials.confluence.nonexistent')).toBeUndefined();
    });

    it('should get NLP benchmark data', () => {
      expect(get('nlp_benchmarks.rte.name')).toBe('RTE');
      expect(get('nlp_benchmarks.sst_2.sample.text')).toBe('This movie was absolutely wonderful!');
    });
  });

  describe('has()', () => {
    it('should return true for existing keys', () => {
      expect(has('email')).toBe(true);
      expect(has('credentials.email')).toBe(true);
      expect(has('credentials.confluence.email')).toBe(true);
    });

    it('should return false for non-existent keys', () => {
      expect(has('nonexistent')).toBe(false);
      expect(has('credentials.nonexistent')).toBe(false);
    });
  });

  describe('getMany()', () => {
    it('should return array of values', () => {
      const [email, password, apiKey] = getMany('email', 'password', 'api_key');
      expect(email).toBe('test@example.com');
      expect(password).toBe('TestPassword123!');
      expect(apiKey).toBe('sk-test-1234567890abcdef');
    });

    it('should return undefined for missing keys', () => {
      const [email, missing] = getMany('email', 'nonexistent');
      expect(email).toBe('test@example.com');
      expect(missing).toBeUndefined();
    });
  });

  describe('getOrDefault()', () => {
    it('should return value if key exists', () => {
      expect(getOrDefault('email', 'fallback@example.com')).toBe('test@example.com');
    });

    it('should return default if key does not exist', () => {
      expect(getOrDefault('nonexistent', 'default-value')).toBe('default-value');
    });
  });

  describe('getAll()', () => {
    it('should return complete data object', () => {
      const data = getAll();
      expect(data).toHaveProperty('email');
      expect(data).toHaveProperty('credentials');
      expect(data).toHaveProperty('tokens');
      expect(data).toHaveProperty('nlp_benchmarks');
    });
  });
});
