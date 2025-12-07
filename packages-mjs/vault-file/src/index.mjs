/**
 * Vault File - Environment Variable Loader
 *
 * JavaScript module for loading environment variables from .env files.
 * Provides a singleton EnvStore for accessing loaded values.
 */

import { promises as fs, existsSync } from 'fs';
import path from 'path';
import * as dotenv from 'dotenv';

/**
 * Logger for vault operations
 */
export const logger = {
  debug: (message) => console.log(`[DEBUG] ${message}`),
  info: (message) => console.log(`[INFO] ${message}`),
  error: (message) => console.error(`[ERROR] ${message}`),
};

/**
 * Singleton store for environment variables loaded from .env files.
 */
class EnvStore {
  static instance = null;

  constructor() {
    if (EnvStore.instance) {
      return EnvStore.instance;
    }
    this.values = new Map();
    this.initialized = false;
    this.loadResult = { loaded: [], errors: [] };
    EnvStore.instance = this;
  }

  static getInstance() {
    if (!EnvStore.instance) {
      EnvStore.instance = new EnvStore();
    }
    return EnvStore.instance;
  }

  get(key) {
    return process.env[key] ?? this.values.get(key);
  }

  getOrThrow(key) {
    const value = this.get(key);
    if (value === undefined) {
      throw new Error(`Environment variable "${key}" is not defined`);
    }
    return value;
  }

  getAll() {
    const result = {};
    for (const [key, value] of this.values.entries()) {
      result[key] = value;
    }
    return result;
  }

  isInitialized() {
    return this.initialized;
  }

  getLoadResult() {
    return this.loadResult;
  }

  reset() {
    this.values.clear();
    this.initialized = false;
    this.loadResult = { loaded: [], errors: [] };
  }

  async _loadFromLocation(options) {
    const { location, pattern = '.env*', override = false } = options;

    logger.info(`Loading env files from: ${location}`);

    if (!existsSync(location)) {
      logger.error(`Location does not exist: ${location}`);
      this.loadResult.errors.push({ file: location, error: 'Location does not exist' });
      return;
    }

    try {
      const stats = await fs.stat(location);

      if (stats.isFile()) {
        try {
          const content = await fs.readFile(location, 'utf-8');
          const parsed = dotenv.parse(content);

          for (const [key, value] of Object.entries(parsed)) {
            if (override || process.env[key] === undefined) {
              process.env[key] = value;
              this.values.set(key, value);
            }
          }

          this.loadResult.loaded.push(location);
          logger.info(`Loaded env file: ${location}`);
        } catch (err) {
          this.loadResult.errors.push({ file: location, error: err.message });
          logger.error(`Failed to load env file ${location}: ${err.message}`);
        }
      } else if (stats.isDirectory()) {
        const files = await fs.readdir(location);
        const envFiles = files.filter((file) => {
          if (pattern.includes('*')) {
            const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$');
            return regex.test(file);
          }
          return file === pattern;
        });

        for (const file of envFiles) {
          const filePath = path.join(location, file);
          try {
            const content = await fs.readFile(filePath, 'utf-8');
            const parsed = dotenv.parse(content);

            for (const [key, value] of Object.entries(parsed)) {
              if (override || process.env[key] === undefined) {
                process.env[key] = value;
                this.values.set(key, value);
              }
            }

            this.loadResult.loaded.push(filePath);
            logger.info(`Loaded env file: ${filePath}`);
          } catch (err) {
            this.loadResult.errors.push({ file: filePath, error: err.message });
            logger.error(`Failed to load env file ${filePath}: ${err.message}`);
          }
        }
      }
    } catch (err) {
      this.loadResult.errors.push({ file: location, error: err.message });
      logger.error(`Failed to process location ${location}: ${err.message}`);
    }

    this.initialized = true;
    logger.info(`Loaded ${this.loadResult.loaded.length} env file(s)`);
  }
}

/**
 * Load environment files on startup.
 *
 * @param {Object} options - Load options
 * @param {string} options.location - Path to file or directory
 * @param {string} [options.pattern='.env*'] - Glob pattern for matching files
 * @param {boolean} [options.override=false] - Whether to override existing env vars
 * @returns {Promise<EnvStore>} The singleton EnvStore instance
 */
export async function on_startup(options) {
  const store = EnvStore.getInstance();
  await store._loadFromLocation(options);
  return store;
}

/**
 * Singleton EnvStore instance
 */
export const env = EnvStore.getInstance();

export { EnvStore };
