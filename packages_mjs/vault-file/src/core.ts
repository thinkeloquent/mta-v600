import { v4 as uuidv4, validate as uuidValidate } from 'uuid';
import { promises as fs, existsSync } from 'fs';
import path from 'path';
import { z } from 'zod';
import * as dotenv from 'dotenv';

// Zod schemas for validation
const VaultHeaderSchema = z.object({
  id: z.string().uuid(),
  version: z.string().regex(/^\d+\.\d+\.\d+$/),
  createdAt: z.string().datetime(),
});

const VaultMetadataSchema = z.object({
  data: z.record(z.any()),
});

const VaultPayloadSchema = z.object({
  content: z.any(),
});

const VaultFileSchema = z.object({
  header: VaultHeaderSchema,
  metadata: VaultMetadataSchema,
  payload: VaultPayloadSchema,
});


// Custom Errors
export class VaultValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'VaultValidationError';
  }
}

export class VaultSerializationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'VaultSerializationError';
  }
}

// Logger - making it mockable for tests
export const logger = {
  debug: (message: string) => console.log(`[DEBUG] ${message}`),
  info: (message: string) => console.log(`[INFO] ${message}`),
  error: (message: string) => console.error(`[ERROR] ${message}`),
};

export class VaultHeader {
  id: string;
  version: string;
  createdAt: string;

  constructor(header?: { id?: string; version?: string; createdAt?: string }) {
    this.id = header?.id || uuidv4();
    this.version = header?.version || '1.0.0';
    this.createdAt = header?.createdAt || new Date().toISOString();
  }
}

export class VaultMetadata {
  data: Record<string, any>;

  constructor(metadata?: { data?: Record<string, any> }) {
    this.data = metadata?.data || {};
  }
}

export class VaultPayload {
  content: any;

  constructor(payload?: { content?: any }) {
    if (payload && typeof payload.content === 'number') {
        throw new VaultSerializationError('Payload content cannot be a number.');
    }
    this.content = payload?.content;
  }
}

export class VaultFile {
  header: VaultHeader;
  metadata: VaultMetadata;
  payload: VaultPayload;

  constructor({ header, metadata, payload }: { header?: any; metadata?: any; payload: any }) {
    logger.debug(`VaultFile initialized with id: ${header?.id || 'new'}`);
    this.header = new VaultHeader(header);
    this.metadata = new VaultMetadata(metadata);
    this.payload = new VaultPayload(payload);
    this.validateState();
  }

  validateState() {
    logger.debug(`Validating state for VaultFile id: ${this.header.id}`);
    try {
      VaultHeaderSchema.parse(this.header);
      VaultMetadataSchema.parse(this.metadata);
      VaultPayloadSchema.parse(this.payload);
    } catch (error: any) {
      throw new VaultValidationError(`Invalid vault file state: ${error.message}`);
    }
  }

  toJSON(): string {
    logger.debug(`Serializing VaultFile id: ${this.header.id}`);
    this.validateState();
    return JSON.stringify({
      header: this.header,
      metadata: this.metadata,
      payload: this.payload,
    }, null, 2);
  }

  static fromJSON(jsonStr: string): VaultFile {
    logger.debug('Attempting to deserialize VaultFile from JSON.');
    let parsed;
    try {
      parsed = JSON.parse(jsonStr);
    } catch (error) {
      throw new VaultSerializationError('Invalid JSON string provided.');
    }
    
    try {
        VaultFileSchema.parse(parsed);
    } catch (error: any) {
        throw new VaultSerializationError(`JSON does not match VaultFile schema: ${error.message}`);
    }

    return new VaultFile(parsed);
  }
}

export interface OnStartupOptions {
  location: string;
  pattern?: string;
  override?: boolean;
}

export interface OnStartupResult {
  loaded: string[];
  errors: Array<{ file: string; error: string }>;
}

class EnvStore {
  private static instance: EnvStore;
  private values: Map<string, string> = new Map();
  private initialized: boolean = false;
  private loadResult: OnStartupResult = { loaded: [], errors: [] };

  private constructor() {}

  static getInstance(): EnvStore {
    if (!EnvStore.instance) {
      EnvStore.instance = new EnvStore();
    }
    return EnvStore.instance;
  }

  get(key: string): string | undefined {
    return process.env[key] ?? this.values.get(key);
  }

  getOrThrow(key: string): string {
    const value = this.get(key);
    if (value === undefined) {
      throw new Error(`Environment variable "${key}" is not defined`);
    }
    return value;
  }

  getAll(): Record<string, string> {
    const result: Record<string, string> = {};
    for (const [key, value] of this.values.entries()) {
      result[key] = value;
    }
    return result;
  }

  isInitialized(): boolean {
    return this.initialized;
  }

  getLoadResult(): OnStartupResult {
    return this.loadResult;
  }

  reset(): void {
    this.values.clear();
    this.initialized = false;
    this.loadResult = { loaded: [], errors: [] };
  }

  async _loadFromLocation(options: OnStartupOptions): Promise<void> {
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
        } catch (err: any) {
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
          } catch (err: any) {
            this.loadResult.errors.push({ file: filePath, error: err.message });
            logger.error(`Failed to load env file ${filePath}: ${err.message}`);
          }
        }
      }
    } catch (err: any) {
      this.loadResult.errors.push({ file: location, error: err.message });
      logger.error(`Failed to process location ${location}: ${err.message}`);
    }

    this.initialized = true;
    logger.info(`Loaded ${this.loadResult.loaded.length} env file(s)`);
  }
}

export async function on_startup(options: OnStartupOptions): Promise<EnvStore> {
  const store = EnvStore.getInstance();
  await store._loadFromLocation(options);
  return store;
}

export const env = EnvStore.getInstance();