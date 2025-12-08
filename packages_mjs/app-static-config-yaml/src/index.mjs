/**
 * Static Config Property Management
 *
 * JavaScript module for loading and managing static YAML configuration properties.
 * Provides a singleton ConfigStore for accessing loaded configuration.
 */

import { promises as fs, existsSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";
import yaml from "js-yaml";

/**
 * Logger for config operations
 */
export const logger = {
  debug: (message) => console.log(`[DEBUG] ${message}`),
  info: (message) => console.log(`[INFO] ${message}`),
  error: (message) => console.error(`[ERROR] ${message}`),
};

/**
 * Load result class
 */
export class LoadResult {
  constructor() {
    this.filesLoaded = [];
    this.errors = [];
    this.configFile = null;
    this.appEnv = null;
  }
}

/**
 * Singleton store for configuration loaded from YAML files.
 */
class ConfigStore {
  static instance = null;

  constructor() {
    if (ConfigStore.instance) {
      return ConfigStore.instance;
    }
    this.data = {};
    this.initialized = false;
    this.loadResult = new LoadResult();
    ConfigStore.instance = this;
  }

  static getInstance() {
    if (!ConfigStore.instance) {
      ConfigStore.instance = new ConfigStore();
    }
    return ConfigStore.instance;
  }

  /**
   * Find the config file path based on APP_ENV
   */
  _findConfigPath(basePath, appEnv) {
    const potentialConfigs = [
      path.join(basePath, `server.${appEnv}.yaml`),
      path.join(basePath, "server.yaml"),
    ];

    for (const configPath of potentialConfigs) {
      if (existsSync(configPath)) {
        logger.debug(`Found config file: ${configPath}`);
        return configPath;
      }
    }

    throw new Error(
      `No config file found. Searched in: ${potentialConfigs.join(", ")}`
    );
  }

  /**
   * Load configuration from YAML file
   */
  async load(options) {
    const { configDir } = options;
    // Get APP_ENV and convert to lowercase for consistent file matching
    const rawAppEnv = options.appEnv || process.env.APP_ENV || "dev";
    const appEnv = rawAppEnv.toLowerCase();

    this.loadResult = new LoadResult();
    this.loadResult.appEnv = appEnv;

    logger.info(`Loading static config for APP_ENV=${appEnv}`);

    if (!existsSync(configDir)) {
      const errorMsg = `Config directory does not exist: ${configDir}`;
      logger.error(errorMsg);
      this.loadResult.errors.push({ path: configDir, error: errorMsg });
      this.initialized = true;
      return this.loadResult;
    }

    try {
      const configPath = this._findConfigPath(configDir, appEnv);
      this.loadResult.configFile = configPath;

      const content = await fs.readFile(configPath, "utf-8");
      this.data = yaml.load(content) || {};

      this.loadResult.filesLoaded.push(configPath);
      logger.info(`Successfully loaded config from: ${configPath}`);
    } catch (err) {
      logger.error(`Failed to load config: ${err.message}`);
      this.loadResult.errors.push({ path: configDir, error: err.message });
    }

    this.initialized = true;
    return this.loadResult;
  }

  /**
   * Get a top-level configuration value
   */
  get(key, defaultValue = null) {
    return this.data[key] ?? defaultValue;
  }

  /**
   * Get a nested configuration value
   */
  getNested(...args) {
    const keys = args.slice(0, -1);
    const defaultValue = args.length > 1 ? args[args.length - 1] : null;

    // Check if last arg is actually a key (not a default value)
    if (typeof defaultValue === "string" && !keys.length) {
      // Single key case
      return this.data[defaultValue] ?? null;
    }

    let current = this.data;
    for (const key of keys) {
      if (current && typeof current === "object" && key in current) {
        current = current[key];
      } else {
        return defaultValue;
      }
    }
    return current ?? defaultValue;
  }

  /**
   * Get all loaded configuration data
   */
  getAll() {
    return { ...this.data };
  }

  /**
   * Check if the store has been initialized
   */
  isInitialized() {
    return this.initialized;
  }

  /**
   * Get the result from the last load operation
   */
  getLoadResult() {
    return this.loadResult;
  }

  /**
   * Clear the store and reset to uninitialized state
   */
  reset() {
    this.data = {};
    this.initialized = false;
    this.loadResult = new LoadResult();
  }
}

/**
 * Get the default configuration path
 * Uses process.cwd() when import.meta.url is not available (e.g., in tests)
 */
export function getConfigPath() {
  // If we're in a test environment, use process.cwd()
  if (typeof jest !== "undefined" || process.env.NODE_ENV === "test") {
    return path.resolve(process.cwd(), "common", "config");
  }

  try {
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);
    // Go up from: packages_mjs/app-static-config-yaml/src
    // To: common/config
    return path.resolve(__dirname, "..", "..", "..", "common", "config");
  } catch (err) {
    // Fallback for environments that don't support import.meta
    return path.resolve(process.cwd(), "common", "config");
  }
}

/**
 * Load YAML configuration with sensible defaults.
 *
 * This function should be called AFTER vault secrets are loaded,
 * so that APP_ENV can be set from vault.
 *
 * @param {Object} options - Load options
 * @param {string} [options.configDir] - Path to config directory (default: common/config)
 * @param {string} [options.appEnv] - Environment name (default: from APP_ENV or 'dev')
 * @returns {Promise<LoadResult>} Load result
 */
export async function loadYamlConfig(options = {}) {
  const configDir = options.configDir || getConfigPath();
  // Get APP_ENV and convert to lowercase for consistent file matching
  const rawAppEnv = options.appEnv || process.env.APP_ENV || "dev";
  const appEnv = rawAppEnv.toLowerCase();

  const store = ConfigStore.getInstance();
  return store.load({ configDir, appEnv });
}

/**
 * Load configuration on startup.
 *
 * @param {Object} options - Load options
 * @param {string} [options.configDir] - Path to config directory
 * @param {string} [options.appEnv] - Environment name
 * @returns {Promise<ConfigStore>} The singleton ConfigStore instance
 */
export async function on_startup(options = {}) {
  await loadYamlConfig(options);
  return ConfigStore.getInstance();
}

/**
 * Singleton ConfigStore instance
 */
export const config = ConfigStore.getInstance();

export { ConfigStore };
