/**
 * Tests for ConfigStore singleton
 */

import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { promises as fs } from 'fs';
import path from 'path';
import os from 'os';
import { ConfigStore, config, loadYamlConfig, LoadResult } from '../src/index.mjs';

describe('ConfigStore', () => {
  let tempDir;

  const sampleConfig = {
    providers: {
      gemini: {
        base_url: 'https://api.gemini.test',
        model: 'gemini-test',
        env_api_key: 'GEMINI_API_KEY',
      },
      openai: {
        base_url: 'https://api.openai.test',
        model: 'gpt-4-test',
        env_api_key: 'OPENAI_API_KEY',
      },
    },
    default_provider: 'gemini',
    client: {
      timeout_seconds: 30.0,
      max_connections: 5,
    },
    display: {
      separator_char: '=',
      separator_length: 60,
    },
    proxy: {
      default_environment: 'test',
      cert_verify: true,
    },
  };

  beforeEach(async () => {
    // Reset singleton state
    config.reset();

    // Create temp directory
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'static-config-test-'));
  });

  afterEach(async () => {
    // Cleanup temp directory
    if (tempDir) {
      await fs.rm(tempDir, { recursive: true, force: true });
    }
  });

  describe('Singleton Pattern', () => {
    it('should return same instance', () => {
      const store1 = ConfigStore.getInstance();
      const store2 = ConfigStore.getInstance();
      expect(store1).toBe(store2);
    });

    it('should return same instance via constructor', () => {
      const store1 = new ConfigStore();
      const store2 = new ConfigStore();
      expect(store1).toBe(store2);
    });
  });

  describe('Initial State', () => {
    it('should start uninitialized', () => {
      expect(config.isInitialized()).toBe(false);
    });

    it('should have empty load result', () => {
      const result = config.getLoadResult();
      expect(result.filesLoaded).toEqual([]);
      expect(result.errors).toEqual([]);
    });

    it('should return empty data', () => {
      expect(config.getAll()).toEqual({});
    });
  });

  describe('Loading Config', () => {
    it('should load config from directory', async () => {
      const configPath = path.join(tempDir, 'server.dev.yaml');
      const yamlContent = `
providers:
  gemini:
    base_url: "https://api.gemini.test"
    model: "gemini-test"
default_provider: "gemini"
client:
  timeout_seconds: 30.0
`;
      await fs.writeFile(configPath, yamlContent);

      const result = await config.load({ configDir: tempDir, appEnv: 'dev' });

      expect(config.isInitialized()).toBe(true);
      expect(result.filesLoaded.length).toBe(1);
      expect(result.errors.length).toBe(0);
      expect(result.appEnv).toBe('dev');
    });

    it('should handle nonexistent directory', async () => {
      const result = await config.load({ configDir: '/nonexistent/path', appEnv: 'dev' });

      expect(config.isInitialized()).toBe(true);
      expect(result.filesLoaded.length).toBe(0);
      expect(result.errors.length).toBe(1);
    });

    it('should fall back to server.yaml if env-specific not found', async () => {
      const configPath = path.join(tempDir, 'server.yaml');
      await fs.writeFile(configPath, 'default_provider: "fallback"');

      const result = await config.load({ configDir: tempDir, appEnv: 'prod' });

      expect(config.isInitialized()).toBe(true);
      expect(result.filesLoaded.length).toBe(1);
      expect(config.get('default_provider')).toBe('fallback');
    });
  });

  describe('Getting Values', () => {
    beforeEach(async () => {
      const configPath = path.join(tempDir, 'server.dev.yaml');
      const yamlContent = `
providers:
  gemini:
    base_url: "https://api.gemini.test"
    model: "gemini-test"
  openai:
    base_url: "https://api.openai.test"
default_provider: "gemini"
client:
  timeout_seconds: 30.0
  max_connections: 5
`;
      await fs.writeFile(configPath, yamlContent);
      await config.load({ configDir: tempDir, appEnv: 'dev' });
    });

    it('should get top-level values', () => {
      expect(config.get('default_provider')).toBe('gemini');
      expect(config.get('nonexistent')).toBeNull();
      expect(config.get('nonexistent', 'default')).toBe('default');
    });

    it('should get nested values', () => {
      // getNested takes only keys as arguments, returns null for missing paths
      const geminiUrl = config.getNested('providers', 'gemini', 'base_url');
      expect(geminiUrl).toBe('https://api.gemini.test');

      const timeout = config.getNested('client', 'timeout_seconds');
      expect(timeout).toBe(30.0);
    });

    it('should return null for missing nested values', () => {
      // getNested returns null when path doesn't exist
      const missing = config.getNested('foo', 'bar', 'baz');
      expect(missing).toBeNull();
    });

    it('should get all config as object', () => {
      const all = config.getAll();
      expect(all.providers).toBeDefined();
      expect(all.client).toBeDefined();
    });
  });

  describe('Reset', () => {
    it('should reset to initial state', async () => {
      const configPath = path.join(tempDir, 'server.dev.yaml');
      await fs.writeFile(configPath, 'default_provider: "test"');
      await config.load({ configDir: tempDir, appEnv: 'dev' });

      expect(config.isInitialized()).toBe(true);

      config.reset();

      expect(config.isInitialized()).toBe(false);
      expect(config.getAll()).toEqual({});
    });
  });
});

describe('loadYamlConfig', () => {
  let tempDir;

  beforeEach(async () => {
    config.reset();
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'static-config-test-'));
  });

  afterEach(async () => {
    if (tempDir) {
      await fs.rm(tempDir, { recursive: true, force: true });
    }
  });

  it('should load config with explicit appEnv', async () => {
    const configPath = path.join(tempDir, 'server.dev.yaml');
    await fs.writeFile(configPath, 'default_provider: "gemini"');

    const result = await loadYamlConfig({ configDir: tempDir, appEnv: 'dev' });

    expect(config.isInitialized()).toBe(true);
    expect(result.appEnv).toBe('dev');
  });

  it('should default to dev environment', async () => {
    const configPath = path.join(tempDir, 'server.dev.yaml');
    await fs.writeFile(configPath, 'default_provider: "gemini"');

    // Clear APP_ENV
    delete process.env.APP_ENV;

    const result = await loadYamlConfig({ configDir: tempDir });

    expect(result.appEnv).toBe('dev');
  });

  it('should use APP_ENV from environment', async () => {
    const configPath = path.join(tempDir, 'server.prod.yaml');
    await fs.writeFile(configPath, 'default_provider: "openai"');

    process.env.APP_ENV = 'prod';

    const result = await loadYamlConfig({ configDir: tempDir });

    expect(result.appEnv).toBe('prod');
    expect(config.get('default_provider')).toBe('openai');

    delete process.env.APP_ENV;
  });
});

describe('LoadResult', () => {
  it('should have correct initial state', () => {
    const result = new LoadResult();
    expect(result.filesLoaded).toEqual([]);
    expect(result.errors).toEqual([]);
    expect(result.configFile).toBeNull();
    expect(result.appEnv).toBeNull();
  });
});
