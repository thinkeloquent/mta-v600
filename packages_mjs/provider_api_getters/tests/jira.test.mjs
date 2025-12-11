/**
 * Comprehensive tests for jira.mjs
 *
 * Coverage targets:
 * - Decision/Branch coverage: All 4 branches in getApiKey
 * - Boundary value testing: Edge cases
 * - Log verification: Console spy checks
 */
import {
  jest,
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
} from "@jest/globals";
import { JiraApiToken } from "../src/api_token/jira.mjs";

function setupConsoleSpy() {
  return {
    debug: jest.spyOn(console, "debug").mockImplementation(() => {}),
    warn: jest.spyOn(console, "warn").mockImplementation(() => {}),
    error: jest.spyOn(console, "error").mockImplementation(() => {}),
  };
}

function restoreConsoleSpy(spies) {
  Object.values(spies).forEach((spy) => spy.mockRestore());
}

function createMockStore(providers = {}) {
  return {
    providers,
    getNested: function (...keys) {
      let value = this;
      for (const key of keys) {
        if (value === null || value === undefined) return null;
        value = value[key];
      }
      return value ?? null;
    },
  };
}

describe("JiraApiToken", () => {
  let consoleSpy;
  let originalEnv;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
    originalEnv = { ...process.env };
    delete process.env.JIRA_EMAIL;
    delete process.env.JIRA_API_TOKEN;
    delete process.env.JIRA_BASE_URL;
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
    process.env = originalEnv;
  });

  describe("Provider Properties", () => {
    it("should return correct provider name", () => {
      const token = new JiraApiToken();
      expect(token.providerName).toBe("jira");
    });

    it("should return correct health endpoint", () => {
      const token = new JiraApiToken();
      expect(token.healthEndpoint).toBe("/myself");
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining("Returning /myself")
      );
    });
  });

  describe("_getEmail - Decision Coverage", () => {
    it("should return email from default env var", () => {
      const token = new JiraApiToken();
      process.env.JIRA_EMAIL = "test@example.com";

      const email = token._getEmail();

      expect(email).toBe("test@example.com");
    });

    it("should return email from configured env var", () => {
      const mockStore = createMockStore({
        jira: { env_email: "CUSTOM_JIRA_EMAIL" },
      });
      const token = new JiraApiToken(mockStore);
      process.env.CUSTOM_JIRA_EMAIL = "custom@example.com";

      const email = token._getEmail();

      expect(email).toBe("custom@example.com");
    });

    it("should return null when env var not set", () => {
      const token = new JiraApiToken();

      const email = token._getEmail();

      expect(email).toBeNull();
    });

    it("should mask email in log", () => {
      const token = new JiraApiToken();
      process.env.JIRA_EMAIL = "longemail@example.com";

      token._getEmail();

      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining("lon***@***")
      );
    });
  });

  describe("_encodeAuth", () => {
    it("should encode credentials with basic auth type correctly", () => {
      const token = new JiraApiToken();
      const encoded = token._encodeAuth(
        "user@test.com",
        "api-token",
        "basic_email_token"
      );

      // Base64 of 'user@test.com:api-token'
      const expected =
        "Basic " + Buffer.from("user@test.com:api-token").toString("base64");
      expect(encoded).toBe(expected);
    });

    it("should encode credentials with bearer auth type correctly", () => {
      const token = new JiraApiToken();
      const encoded = token._encodeAuth(
        "user@test.com",
        "api-token",
        "bearer_email_token"
      );

      // Base64 of 'user@test.com:api-token' with Bearer prefix
      const expected =
        "Bearer " + Buffer.from("user@test.com:api-token").toString("base64");
      expect(encoded).toBe(expected);
    });

    it("should throw when email is empty", () => {
      const token = new JiraApiToken();

      expect(() => token._encodeAuth("", "token", "basic_email_token")).toThrow(
        "Both email and token are required"
      );
    });

    it("should throw when token is empty", () => {
      const token = new JiraApiToken();

      expect(() =>
        token._encodeAuth("email@test.com", "", "basic_email_token")
      ).toThrow("Both email and token are required");
    });

    it("should log error on invalid input", () => {
      const token = new JiraApiToken();

      try {
        token._encodeAuth(null, "token", "basic_email_token");
      } catch (e) {
        // Expected
      }

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Invalid inputs")
      );
    });
  });

  describe("getApiKey - 4-Branch Coverage", () => {
    it("Branch 1: Both email and token present - should return encoded auth", () => {
      const mockStore = createMockStore({
        jira: {
          env_api_key: "JIRA_API_TOKEN",
          env_email: "JIRA_EMAIL",
          api_auth_type: "basic_email_token",
        },
      });
      const token = new JiraApiToken(mockStore);
      process.env.JIRA_EMAIL = "user@test.com";
      process.env.JIRA_API_TOKEN = "api-token-123";

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(true);
      expect(result.authType).toBe("basic_email_token");
      expect(result.headerName).toBe("Authorization");
      expect(result.username).toBe("user@test.com");
      expect(result.apiKey).toContain("Basic ");
      expect(consoleSpy.debug).toHaveBeenCalledWith(
        expect.stringContaining("Both email and token found")
      );
    });

    it("Branch 2: Token present, email missing - should return null apiKey", () => {
      const mockStore = createMockStore({
        jira: { env_api_key: "JIRA_API_TOKEN" },
      });
      const token = new JiraApiToken(mockStore);
      process.env.JIRA_API_TOKEN = "api-token-123";
      delete process.env.JIRA_EMAIL;

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(result.username).toBeNull();
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining("API token found but email is missing")
      );
    });

    it("Branch 3: Email present, token missing - should return null apiKey", () => {
      const token = new JiraApiToken();
      process.env.JIRA_EMAIL = "user@test.com";
      delete process.env.JIRA_API_TOKEN;

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(result.username).toBe("user@test.com");
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining("Email found but API token is missing")
      );
    });

    it("Branch 4: Neither email nor token - should return null apiKey", () => {
      const token = new JiraApiToken();

      const result = token.getApiKey();

      expect(result.hasCredentials).toBe(false);
      expect(result.apiKey).toBeNull();
      expect(result.username).toBeNull();
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining("Neither email nor token found")
      );
    });
  });

  describe("getBaseUrl - Decision Coverage", () => {
    it("should return base URL from config", () => {
      const mockStore = createMockStore({
        jira: { base_url: "https://jira.company.com" },
      });
      const token = new JiraApiToken(mockStore);

      const url = token.getBaseUrl();

      expect(url).toBe("https://jira.company.com");
    });

    it("should fall back to JIRA_BASE_URL env var", () => {
      const token = new JiraApiToken();
      process.env.JIRA_BASE_URL = "https://jira-env.company.com";

      const url = token.getBaseUrl();

      expect(url).toBe("https://jira-env.company.com");
    });

    it("should return null when no base URL configured", () => {
      const token = new JiraApiToken();

      const url = token.getBaseUrl();

      expect(url).toBeNull();
      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining("No base URL configured")
      );
    });
  });
});
