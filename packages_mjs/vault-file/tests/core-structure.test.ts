// packages_mjs/vault-file/tests/core-structure.test.ts
import {
  VaultHeader,
  VaultMetadata,
  VaultPayload,
  VaultFile,
  VaultValidationError,
  VaultSerializationError,
  logger,
  on_startup,
  env,
  OnStartupOptions,
} from "../src/core";
import { v4 as uuidv4, validate as uuidValidate } from "uuid";
import { promises as fs } from "fs";
import path from "path";
import os from "os";

// Remove the jest.mock block, as we're directly manipulating the exported logger

describe("VaultHeader", () => {
  it("should instantiate with default values", () => {
    const header = new VaultFile({ payload: { content: "test" } }).header;
    expect(uuidValidate(header.id)).toBe(true);
    expect(header.version).toBe("1.0.0");
    expect(header.createdAt).toBeDefined();
    expect(typeof header.createdAt).toBe("string");
    expect(new Date(header.createdAt).toISOString()).toEqual(header.createdAt); // Check if it's ISO 8601
  });

  it("should instantiate with custom values", () => {
    const customId = uuidv4();
    const customDate = new Date().toISOString();
    const vaultFile = new VaultFile({
      header: { id: customId, version: "2.0.0", createdAt: customDate },
      payload: { content: "test" },
    });
    expect(vaultFile.header.id).toBe(customId);
    expect(vaultFile.header.version).toBe("2.0.0");
    expect(vaultFile.header.createdAt).toBe(customDate);
  });
});

describe("VaultMetadata", () => {
  it("should instantiate with empty data by default", () => {
    const metadata = new VaultFile({ payload: { content: "test" } }).metadata;
    expect(metadata.data).toEqual({});
  });

  it("should instantiate with provided data", () => {
    const data = { tag: "test", owner: "user1" };
    const vaultFile = new VaultFile({
      metadata: { data },
      payload: { content: "test" },
    });
    expect(vaultFile.metadata.data).toEqual(data);
  });
});

describe("VaultPayload", () => {
  it("should instantiate with dictionary content", () => {
    const payload = new VaultFile({ payload: { content: { key: "value" } } })
      .payload;
    expect(payload.content).toEqual({ key: "value" });
  });

  it("should instantiate with list content", () => {
    const payload = new VaultFile({ payload: { content: [1, 2, 3] } }).payload;
    expect(payload.content).toEqual([1, 2, 3]);
  });

  it("should instantiate with string content", () => {
    const payload = new VaultFile({ payload: { content: "hello" } }).payload;
    expect(payload.content).toBe("hello");
  });

  it("should throw error for invalid content type", () => {
    // @ts-ignore - Intentionally passing invalid type for testing
    expect(() => new VaultFile({ payload: { content: 123 } })).toThrow(
      VaultSerializationError
    );
  });
});

describe("VaultFile", () => {
  let originalDebug: typeof logger.debug;
  let originalInfo: typeof logger.info;
  let originalError: typeof logger.error;

  beforeEach(() => {
    originalDebug = logger.debug;
    originalInfo = logger.info;
    originalError = logger.error;

    logger.debug = jest.fn();
    logger.info = jest.fn();
    logger.error = jest.fn();
  });

  afterEach(() => {
    logger.debug = originalDebug;
    logger.info = originalInfo;
    logger.error = originalError;
    jest.restoreAllMocks(); // Restore any other potential mocks/spies
  });

  it("should instantiate with minimal payload", () => {
    const payload = { content: { test: "data" } };
    const vaultFile = new VaultFile({ payload });
    expect(vaultFile.header).toBeDefined();
    expect(vaultFile.metadata).toBeDefined();
    expect(vaultFile.payload).toEqual(payload);
    expect(logger.debug).toHaveBeenCalledWith(
      expect.stringContaining("VaultFile initialized with id:")
    );
  });

  it("should instantiate with full custom components", () => {
    const customId = uuidv4();
    const customDate = new Date().toISOString();
    const header = { id: customId, version: "1.1.0", createdAt: customDate };
    const metadata = { data: { project: "mta" } };
    const payload = { content: "important info" };
    const vaultFile = new VaultFile({ header, metadata, payload });
    expect(vaultFile.header).toEqual(header);
    expect(vaultFile.metadata).toEqual(metadata);
    expect(vaultFile.payload).toEqual(payload);
  });

  it("should define VaultValidationError", () => {
    expect(() => {
      throw new VaultValidationError("Test validation error");
    }).toThrow(VaultValidationError);
  });

  it("should define VaultSerializationError", () => {
    expect(() => {
      throw new VaultSerializationError("Test serialization error");
    }).toThrow(VaultSerializationError);
  });

  it("should serialize to JSON", () => {
    const payload = { content: { test: "data" } };
    const vaultFile = new VaultFile({ payload });
    const jsonStr = vaultFile.toJSON();
    expect(typeof jsonStr).toBe("string");
    const parsed = JSON.parse(jsonStr);
    expect(parsed.payload).toEqual(payload);
    expect(parsed.header.id).toBe(vaultFile.header.id);
    expect(logger.debug).toHaveBeenCalledWith(
      expect.stringContaining("Serializing VaultFile id:")
    );
  });

  it("should deserialize from JSON", () => {
    const originalPayloadContent = { key: "value", number: 123 };
    const originalVaultFile = new VaultFile({
      payload: { content: originalPayloadContent },
    });
    const jsonStr = originalVaultFile.toJSON();

    const newVaultFile = VaultFile.fromJSON(jsonStr);

    expect(newVaultFile).toBeInstanceOf(VaultFile);
    expect(newVaultFile.header.id).toBe(originalVaultFile.header.id);
    expect(newVaultFile.header.version).toBe(originalVaultFile.header.version);
    expect(newVaultFile.header.createdAt).toBe(
      originalVaultFile.header.createdAt
    );
    expect(newVaultFile.metadata.data).toEqual(originalVaultFile.metadata.data);
    expect(newVaultFile.payload.content).toEqual(
      originalVaultFile.payload.content
    );
    expect(logger.debug).toHaveBeenCalledWith(
      "Attempting to deserialize VaultFile from JSON."
    );
  });

  it("should throw VaultSerializationError for invalid JSON during deserialization", () => {
    expect(() => VaultFile.fromJSON("invalid json string")).toThrow(
      VaultSerializationError
    );
    expect(logger.debug).toHaveBeenCalledWith(
      "Attempting to deserialize VaultFile from JSON."
    );
  });

  it("should throw VaultSerializationError for JSON with invalid schema during deserialization", () => {
    const invalidJson = JSON.stringify({
      header: { id: "not-a-uuid" },
      payload: { content: "test" },
    });
    expect(() => VaultFile.fromJSON(invalidJson)).toThrow(
      VaultSerializationError
    );
  });

  it("should validate state successfully", () => {
    const payload = { content: { data: "test" } };
    const vaultFile = new VaultFile({ payload });
    expect(() => vaultFile.validateState()).not.toThrow();
    expect(logger.debug).toHaveBeenCalledWith(
      expect.stringContaining("Validating state for VaultFile id:")
    );
  });

  it("should throw VaultValidationError if state is invalid", () => {
    const validPayload = { content: "valid" };
    const vaultFile = new VaultFile({ payload: validPayload });

    // Manually corrupt a property to make validateState fail
    // @ts-ignore
    vaultFile.header.id = "not-a-valid-uuid-after-creation";

    expect(() => vaultFile.validateState()).toThrow(VaultValidationError);
  });
});

describe("on_startup and env singleton", () => {
  let tempDir: string;
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(async () => {
    // Save original process.env
    originalEnv = { ...process.env };

    // Create temp directory for test files
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "vault-file-test-"));

    // Reset the env singleton
    env.reset();
  });

  afterEach(async () => {
    // Restore original process.env
    process.env = originalEnv;

    // Clean up temp directory
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it("should load env from a single file", async () => {
    const envFile = path.join(tempDir, ".env");
    await fs.writeFile(envFile, "TEST_VAR=hello\nANOTHER_VAR=world");

    const store = await on_startup({ location: envFile });

    expect(store).toBe(env); // Should return singleton
    expect(store.isInitialized()).toBe(true);
    expect(store.get("TEST_VAR")).toBe("hello");
    expect(store.get("ANOTHER_VAR")).toBe("world");
    expect(store.getLoadResult().loaded).toContain(envFile);
  });

  it("should load env files from a directory", async () => {
    await fs.writeFile(path.join(tempDir, ".env"), "DIR_VAR=from_dir");
    await fs.writeFile(
      path.join(tempDir, ".env.local"),
      "LOCAL_VAR=from_local"
    );

    const store = await on_startup({ location: tempDir });

    expect(store.get("DIR_VAR")).toBe("from_dir");
    expect(store.get("LOCAL_VAR")).toBe("from_local");
    expect(store.getLoadResult().loaded.length).toBe(2);
  });

  it("should respect pattern option", async () => {
    await fs.writeFile(path.join(tempDir, ".env"), "ENV_VAR=env");
    await fs.writeFile(path.join(tempDir, ".env.prod"), "PROD_VAR=prod");
    await fs.writeFile(path.join(tempDir, "config.txt"), "CONFIG_VAR=config");

    const store = await on_startup({ location: tempDir, pattern: ".env.prod" });

    expect(store.get("PROD_VAR")).toBe("prod");
    expect(store.get("ENV_VAR")).toBeUndefined();
    expect(store.getLoadResult().loaded.length).toBe(1);
  });

  it("should not override existing env vars by default", async () => {
    process.env.EXISTING_VAR = "original";
    await fs.writeFile(path.join(tempDir, ".env"), "EXISTING_VAR=new_value");

    await on_startup({ location: tempDir });

    expect(env.get("EXISTING_VAR")).toBe("original");
  });

  it("should override existing env vars when override is true", async () => {
    process.env.OVERRIDE_VAR = "original";
    await fs.writeFile(path.join(tempDir, ".env"), "OVERRIDE_VAR=overridden");

    await on_startup({ location: tempDir, override: true });

    expect(env.get("OVERRIDE_VAR")).toBe("overridden");
  });

  it("should return error for non-existent location", async () => {
    const store = await on_startup({ location: "/non/existent/path" });

    expect(store.getLoadResult().errors.length).toBe(1);
    expect(store.getLoadResult().errors[0].error).toBe(
      "Location does not exist"
    );
  });

  it("getOrThrow should throw for undefined keys", async () => {
    await fs.writeFile(path.join(tempDir, ".env"), "DEFINED_VAR=value");
    await on_startup({ location: tempDir });

    expect(env.getOrThrow("DEFINED_VAR")).toBe("value");
    expect(() => env.getOrThrow("UNDEFINED_VAR")).toThrow(
      'Environment variable "UNDEFINED_VAR" is not defined'
    );
  });

  it("getAll should return all loaded values", async () => {
    await fs.writeFile(path.join(tempDir, ".env"), "VAR_A=a\nVAR_B=b");
    await on_startup({ location: tempDir });

    const all = env.getAll();
    expect(all["VAR_A"]).toBe("a");
    expect(all["VAR_B"]).toBe("b");
  });

  it("reset should clear the singleton state", async () => {
    await fs.writeFile(path.join(tempDir, ".env"), "RESET_VAR=value");
    await on_startup({ location: tempDir });

    expect(env.isInitialized()).toBe(true);
    expect(env.getAll()["RESET_VAR"]).toBe("value");

    env.reset();

    expect(env.isInitialized()).toBe(false);
    expect(env.getAll()).toEqual({});
  });

  it("should return the same singleton instance", async () => {
    const store1 = await on_startup({ location: tempDir });
    const store2 = await on_startup({ location: tempDir });

    expect(store1).toBe(store2);
    expect(store1).toBe(env);
  });
});
