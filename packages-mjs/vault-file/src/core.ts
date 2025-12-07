// packages-mjs/vault-file/src/core.ts
import { z } from 'zod';
import { v4 as uuidv4 } from 'uuid';

// Setup logging (placeholder for actual logger implementation)
export let logger = {
  debug: (...args: any[]) => console.debug('[DEBUG]', ...args),
  info: (...args: any[]) => console.info('[INFO]', ...args),
  error: (...args: any[]) => console.error('[ERROR]', ...args),
};

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

// Zod Schemas for Validation
const VaultHeaderSchema = z.object({
  id: z.string().uuid().default(() => uuidv4()),
  version: z.string().default('1.0.0'),
  createdAt: z.string().datetime().default(() => new Date().toISOString()),
});

const VaultMetadataSchema = z.object({
  data: z.record(z.any()).default({}),
});

const VaultPayloadSchema = z.object({
  content: z.union([z.record(z.any()), z.array(z.any()), z.string()]),
});

// Types inferred from Zod schemas
export type VaultHeader = z.infer<typeof VaultHeaderSchema>;
export type VaultMetadata = z.infer<typeof VaultMetadataSchema>;
export type VaultPayload = z.infer<typeof VaultPayloadSchema>;

// Abstract Class/Interface
export interface IVaultFile {
  toJSON(): string;
  validateState(): void;
}

// Main VaultFile Class
export class VaultFile implements IVaultFile {
  header: VaultHeader;
  metadata: VaultMetadata;
  payload: VaultPayload;

  constructor(params: { header?: Partial<VaultHeader>; metadata?: Partial<VaultMetadata>; payload: VaultPayload }) {
    this.header = VaultHeaderSchema.parse(params.header || {});
    this.metadata = VaultMetadataSchema.parse(params.metadata || {});
    this.payload = VaultPayloadSchema.parse(params.payload);
    logger.debug(`VaultFile initialized with id: ${this.header.id}`);
  }

  toJSON(): string {
    logger.debug(`Serializing VaultFile id: ${this.header.id}`);
    try {
      return JSON.stringify({
        header: this.header,
        metadata: this.metadata,
        payload: this.payload,
      }, null, 2);
    } catch (e: any) {
      throw new VaultSerializationError(`Failed to serialize to JSON: ${e.message}`);
    }
  }

  static fromJSON(jsonStr: string): VaultFile {
    logger.debug('Attempting to deserialize VaultFile from JSON.');
    try {
      const parsed = JSON.parse(jsonStr);
      // Validate each part with Zod schemas
      const header = VaultHeaderSchema.parse(parsed.header);
      const metadata = VaultMetadataSchema.parse(parsed.metadata);
      const payload = VaultPayloadSchema.parse(parsed.payload);
      return new VaultFile({ header, metadata, payload });
    } catch (e: any) {
      if (e instanceof z.ZodError) {
        throw new VaultSerializationError(`Failed to deserialize from JSON due to schema validation: ${e.errors.map(err => err.message).join(', ')}`);
      }
      throw new VaultSerializationError(`Failed to deserialize from JSON: ${e.message}`);
    }
  }

  validateState(): void {
    logger.debug(`Validating state for VaultFile id: ${this.header.id}`);
    try {
      // Re-validate against the full structure for consistency
      VaultHeaderSchema.parse(this.header);
      VaultMetadataSchema.parse(this.metadata);
      VaultPayloadSchema.parse(this.payload);
    } catch (e: any) {
      if (e instanceof z.ZodError) {
        throw new VaultValidationError(`VaultFile state is invalid due to schema validation: ${e.errors.map(err => err.message).join(', ')}`);
      }
      throw new VaultValidationError(`VaultFile state is invalid: ${e.message}`);
    }
  }
}
