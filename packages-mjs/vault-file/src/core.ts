import { v4 as uuidv4, validate as uuidValidate } from 'uuid';
import { promises as fs } from 'fs';
import path from 'path';
import { z } from 'zod';

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