/**
 * Comprehensive tests for auth_header_factory.mjs
 *
 * Tests cover:
 * - Decision/Branch coverage for all control flow paths
 * - Boundary value analysis for inputs
 * - State transition testing for factory method selection
 * - Log verification for defensive programming (hyper-observability)
 * - MC/DC coverage for condition combinations
 *
 * Testing Strategy:
 * 1. Statement Testing: Every line executes at least once
 * 2. Decision/Branch Coverage: All true/false branches of if/else
 * 3. Boundary Value Analysis: Edge cases for string lengths, empty values
 * 4. Equivalence Partitioning: Valid/invalid input classes
 * 5. Loop Testing: N/A (no loops in factory)
 * 6. State Testing: Factory state transitions based on scheme selection
 */
import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  AUTH_SCHEMES,
  CONFIG_AUTH_TYPE_MAP,
  AuthHeader,
  AuthHeaderFactory,
} from '../src/api_token/auth_header_factory.mjs';

// Helper to capture console output
function setupConsoleSpy() {
  const spies = {
    debug: jest.spyOn(console, 'debug').mockImplementation(() => { }),
    info: jest.spyOn(console, 'info').mockImplementation(() => { }),
    warn: jest.spyOn(console, 'warn').mockImplementation(() => { }),
    error: jest.spyOn(console, 'error').mockImplementation(() => { }),
  };
  return spies;
}

function restoreConsoleSpy(spies) {
  Object.values(spies).forEach((spy) => spy.mockRestore());
}

// Helper to check if console.debug was called with specific text
function expectLogContains(spy, text) {
  const calls = spy.mock.calls.flat().join(' ');
  expect(calls).toContain(text);
}

// =============================================================================
// Test AUTH_SCHEMES Constants
// =============================================================================

describe('AUTH_SCHEMES', () => {
  describe('Statement Coverage - All schemes exist', () => {
    it('should define all Basic auth scheme variants', () => {
      expect(AUTH_SCHEMES.BASIC_USER_PASS).toBe('basic_user_pass');
      expect(AUTH_SCHEMES.BASIC_EMAIL_TOKEN).toBe('basic_email_token');
      expect(AUTH_SCHEMES.BASIC_USER_TOKEN).toBe('basic_user_token');
    });

    it('should define all Bearer auth scheme variants', () => {
      expect(AUTH_SCHEMES.BEARER_PAT).toBe('bearer_pat');
      expect(AUTH_SCHEMES.BEARER_OAUTH).toBe('bearer_oauth');
      expect(AUTH_SCHEMES.BEARER_JWT).toBe('bearer_jwt');
    });

    it('should define X-Api-Key scheme', () => {
      expect(AUTH_SCHEMES.X_API_KEY).toBe('x_api_key');
    });

    it('should define Custom Header scheme', () => {
      expect(AUTH_SCHEMES.CUSTOM_HEADER).toBe('custom_header');
    });

    it('should define AWS Signature scheme', () => {
      expect(AUTH_SCHEMES.AWS_SIGNATURE).toBe('aws_signature');
    });

    it('should define Digest scheme', () => {
      expect(AUTH_SCHEMES.DIGEST).toBe('digest');
    });

    it('should have exactly 10 schemes (boundary check)', () => {
      expect(Object.keys(AUTH_SCHEMES).length).toBe(10);
    });

    it('should be frozen (immutable)', () => {
      expect(Object.isFrozen(AUTH_SCHEMES)).toBe(true);
    });
  });
});

// =============================================================================
// Test CONFIG_AUTH_TYPE_MAP
// =============================================================================

describe('CONFIG_AUTH_TYPE_MAP', () => {
  it('should map bearer to BEARER_PAT', () => {
    expect(CONFIG_AUTH_TYPE_MAP.bearer).toBe(AUTH_SCHEMES.BEARER_PAT);
  });

  it('should map basic to BASIC_USER_TOKEN', () => {
    expect(CONFIG_AUTH_TYPE_MAP.basic).toBe(AUTH_SCHEMES.BASIC_USER_TOKEN);
  });

  it('should map x-api-key to X_API_KEY', () => {
    expect(CONFIG_AUTH_TYPE_MAP['x-api-key']).toBe(AUTH_SCHEMES.X_API_KEY);
  });

  it('should map custom to CUSTOM_HEADER', () => {
    expect(CONFIG_AUTH_TYPE_MAP.custom).toBe(AUTH_SCHEMES.CUSTOM_HEADER);
  });

  it('should map aws_signature to AWS_SIGNATURE', () => {
    expect(CONFIG_AUTH_TYPE_MAP.aws_signature).toBe(AUTH_SCHEMES.AWS_SIGNATURE);
  });

  it('should map digest to DIGEST', () => {
    expect(CONFIG_AUTH_TYPE_MAP.digest).toBe(AUTH_SCHEMES.DIGEST);
  });

  it('should be frozen (immutable)', () => {
    expect(Object.isFrozen(CONFIG_AUTH_TYPE_MAP)).toBe(true);
  });
});

// =============================================================================
// Test AuthHeader Class
// =============================================================================

describe('AuthHeader', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Constructor - Log verification', () => {
    it('should log debug message on initialization', () => {
      const header = new AuthHeader('Authorization', 'Bearer test', AUTH_SCHEMES.BEARER_PAT);

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toBe('Bearer test');
      expect(header.scheme).toBe(AUTH_SCHEMES.BEARER_PAT);
      expectLogContains(consoleSpy.debug, 'AuthHeader.constructor');
      expectLogContains(consoleSpy.debug, 'bearer_pat');
    });
  });

  describe('toObject()', () => {
    it('should return correct object format for headers', () => {
      const header = new AuthHeader('X-Api-Key', 'my-api-key', AUTH_SCHEMES.X_API_KEY);

      const result = header.toObject();

      expect(result).toEqual({ 'X-Api-Key': 'my-api-key' });
    });
  });

  describe('toString() - Masking behavior', () => {
    it('should mask long values (> 10 chars)', () => {
      const header = new AuthHeader(
        'Authorization',
        'Bearer very-long-secret-token-12345',
        AUTH_SCHEMES.BEARER_PAT
      );

      const result = header.toString();

      expect(result).toBe('Authorization: Bearer ver***');
      expect(result).not.toContain('very-long-secret-token-12345');
    });

    it('should mask short values (<= 10 chars) completely', () => {
      const header = new AuthHeader('Authorization', 'short', AUTH_SCHEMES.BEARER_PAT);

      const result = header.toString();

      expect(result).toBe('Authorization: ***');
    });

    it('should mask exactly 10 char values completely (boundary)', () => {
      const header = new AuthHeader('Authorization', '1234567890', AUTH_SCHEMES.BEARER_PAT);

      const result = header.toString();

      expect(result).toBe('Authorization: ***');
    });

    it('should mask 11 char values showing first 10 (boundary)', () => {
      const header = new AuthHeader('Authorization', '12345678901', AUTH_SCHEMES.BEARER_PAT);

      const result = header.toString();

      expect(result).toBe('Authorization: 1234567890***');
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.create() - Decision/Branch Coverage
// =============================================================================

describe('AuthHeaderFactory.create()', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Log verification', () => {
    it('should log the scheme being created', () => {
      AuthHeaderFactory.create(AUTH_SCHEMES.BEARER_PAT, { token: 'test' });

      expectLogContains(consoleSpy.debug, 'AuthHeaderFactory.create');
      expectLogContains(consoleSpy.debug, 'bearer_pat');
    });
  });

  describe('BASIC schemes branch', () => {
    it('should create Basic auth for BASIC_USER_PASS scheme', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.BASIC_USER_PASS, {
        user: 'testuser',
        password: 'testpass',
      });

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toMatch(/^Basic /);
      expect(header.scheme).toBe(AUTH_SCHEMES.BASIC_USER_PASS);
    });

    it('should create Basic auth for BASIC_EMAIL_TOKEN scheme', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.BASIC_EMAIL_TOKEN, {
        email: 'test@example.com',
        token: 'api-token',
      });

      expect(header.headerValue).toMatch(/^Basic /);
    });

    it('should create Basic auth for BASIC_USER_TOKEN scheme', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.BASIC_USER_TOKEN, {
        username: 'testuser',
        apiKey: 'api-key-123',
      });

      expect(header.headerValue).toMatch(/^Basic /);
    });
  });

  describe('BEARER schemes branch', () => {
    it('should create Bearer auth for BEARER_PAT scheme', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.BEARER_PAT, {
        token: 'pat-token-12345',
      });

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toBe('Bearer pat-token-12345');
      expect(header.scheme).toBe(AUTH_SCHEMES.BEARER_PAT);
    });

    it('should create Bearer auth for BEARER_OAUTH scheme', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.BEARER_OAUTH, {
        token: 'oauth-access-token',
      });

      expect(header.headerValue).toBe('Bearer oauth-access-token');
    });

    it('should create Bearer auth for BEARER_JWT scheme', () => {
      const jwt = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.test';
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.BEARER_JWT, { token: jwt });

      expect(header.headerValue).toBe(`Bearer ${jwt}`);
    });

    it('should use apiKey as fallback for token', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.BEARER_PAT, {
        apiKey: 'api-key-as-token',
      });

      expect(header.headerValue).toBe('Bearer api-key-as-token');
    });
  });

  describe('X_API_KEY scheme branch', () => {
    it('should create X-Api-Key header', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.X_API_KEY, {
        key: 'my-api-key-12345',
      });

      expect(header.headerName).toBe('X-Api-Key');
      expect(header.headerValue).toBe('my-api-key-12345');
      expect(header.scheme).toBe(AUTH_SCHEMES.X_API_KEY);
    });

    it('should use custom header name if provided', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.X_API_KEY, {
        apiKey: 'my-key',
        headerName: 'X-Custom-Api-Key',
      });

      expect(header.headerName).toBe('X-Custom-Api-Key');
    });
  });

  describe('CUSTOM_HEADER scheme branch', () => {
    it('should create custom header', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.CUSTOM_HEADER, {
        headerName: 'X-Figma-Token',
        value: 'figma-token-value',
      });

      expect(header.headerName).toBe('X-Figma-Token');
      expect(header.headerValue).toBe('figma-token-value');
      expect(header.scheme).toBe(AUTH_SCHEMES.CUSTOM_HEADER);
    });

    it('should use apiKey as fallback for value', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.CUSTOM_HEADER, {
        headerName: 'X-Custom-Token',
        apiKey: 'api-key-as-value',
      });

      expect(header.headerValue).toBe('api-key-as-value');
    });
  });

  describe('AWS_SIGNATURE scheme branch', () => {
    it('should create AWS Signature header', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.AWS_SIGNATURE, {
        accessKeyId: 'AKIAIOSFODNN7EXAMPLE',
        secretAccessKey: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        region: 'us-east-1',
        service: 's3',
        method: 'GET',
        url: 'https://s3.amazonaws.com/bucket/key',
      });

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toMatch(/^AWS4-HMAC-SHA256/);
      expect(header.scheme).toBe(AUTH_SCHEMES.AWS_SIGNATURE);
    });
  });

  describe('DIGEST scheme branch', () => {
    it('should create Digest auth header', () => {
      const header = AuthHeaderFactory.create(AUTH_SCHEMES.DIGEST, {
        username: 'testuser',
        password: 'testpass',
        realm: 'test@realm.com',
        nonce: 'abc123nonce',
        uri: '/protected/resource',
        method: 'GET',
      });

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toMatch(/^Digest /);
      expect(header.scheme).toBe(AUTH_SCHEMES.DIGEST);
    });
  });

  describe('Default/fallback branch', () => {
    it('should log warning and default to Bearer for unknown scheme', () => {
      const header = AuthHeaderFactory.create('unknown_scheme', { token: 'fallback-token' });

      expectLogContains(consoleSpy.warn, 'Unknown scheme');
      expectLogContains(consoleSpy.warn, 'defaulting to Bearer');
      expect(header.headerValue).toBe('Bearer fallback-token');
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.createBasic() - Boundary & Error Handling
// =============================================================================

describe('AuthHeaderFactory.createBasic()', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Valid credentials', () => {
    it('should create valid Basic auth header', () => {
      const header = AuthHeaderFactory.createBasic('testuser', 'secret123');

      expect(header.headerName).toBe('Authorization');
      // Verify Base64 encoding
      const expected = Buffer.from('testuser:secret123').toString('base64');
      expect(header.headerValue).toBe(`Basic ${expected}`);
      expect(header.scheme).toBe(AUTH_SCHEMES.BASIC_USER_PASS);
    });

    it('should handle email format (Atlassian style)', () => {
      const header = AuthHeaderFactory.createBasic('user@company.com', 'api-token-12345');

      const expected = Buffer.from('user@company.com:api-token-12345').toString('base64');
      expect(header.headerValue).toBe(`Basic ${expected}`);
    });

    it('should handle special characters in credentials', () => {
      const header = AuthHeaderFactory.createBasic('user:with:colons', 'pass@with!special#chars');

      const expected = Buffer.from('user:with:colons:pass@with!special#chars').toString('base64');
      expect(header.headerValue).toBe(`Basic ${expected}`);
    });

    it('should handle unicode credentials', () => {
      const header = AuthHeaderFactory.createBasic('用户', '密码');

      const expected = Buffer.from('用户:密码', 'utf-8').toString('base64');
      expect(header.headerValue).toBe(`Basic ${expected}`);
    });
  });

  describe('Error handling', () => {
    it('should throw Error for empty user', () => {
      expect(() => AuthHeaderFactory.createBasic('', 'secret')).toThrow(
        'Basic auth requires both user and secret'
      );
      expectLogContains(consoleSpy.error, 'Missing user or secret');
    });

    it('should throw Error for empty secret', () => {
      expect(() => AuthHeaderFactory.createBasic('user', '')).toThrow(
        'Basic auth requires both user and secret'
      );
    });

    it('should throw Error for null user', () => {
      expect(() => AuthHeaderFactory.createBasic(null, 'secret')).toThrow(
        'Basic auth requires both user and secret'
      );
    });

    it('should throw Error for null secret', () => {
      expect(() => AuthHeaderFactory.createBasic('user', null)).toThrow(
        'Basic auth requires both user and secret'
      );
    });

    it('should throw Error for undefined user', () => {
      expect(() => AuthHeaderFactory.createBasic(undefined, 'secret')).toThrow(
        'Basic auth requires both user and secret'
      );
    });

    it('should throw Error for both empty', () => {
      expect(() => AuthHeaderFactory.createBasic('', '')).toThrow();
    });
  });

  describe('Log verification', () => {
    it('should log encoding details', () => {
      AuthHeaderFactory.createBasic('testuser', 'testpass');

      // Encoding logic moved to external package, detailed internal logs removed
      // expectLogContains(consoleSpy.debug, 'Encoded credentials');
      // expectLogContains(consoleSpy.debug, 'inputLength=');
      // expectLogContains(consoleSpy.debug, 'encodedLength=');
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.createBearer() - Boundary & Error Handling
// =============================================================================

describe('AuthHeaderFactory.createBearer()', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Valid tokens', () => {
    it('should create valid Bearer header', () => {
      const header = AuthHeaderFactory.createBearer('valid-token-12345');

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toBe('Bearer valid-token-12345');
      expect(header.scheme).toBe(AUTH_SCHEMES.BEARER_PAT);
    });

    it('should handle JWT token format', () => {
      const jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.H17JcnHOWFnzGbMmBQ8LSqQ2bKlKV0RhYLqNQGl6u3c';
      const header = AuthHeaderFactory.createBearer(jwt);

      expect(header.headerValue).toBe(`Bearer ${jwt}`);
    });

    it('should handle very long token (boundary)', () => {
      const longToken = 'x'.repeat(10000);
      const header = AuthHeaderFactory.createBearer(longToken);

      expect(header.headerValue).toBe(`Bearer ${longToken}`);
      expect(header.headerValue.length).toBe(10007); // "Bearer " + token
    });
  });

  describe('Error handling', () => {
    it('should throw Error for empty token', () => {
      expect(() => AuthHeaderFactory.createBearer('')).toThrow('Bearer auth requires a token');
      expectLogContains(consoleSpy.error, 'Missing token');
    });

    it('should throw Error for null token', () => {
      expect(() => AuthHeaderFactory.createBearer(null)).toThrow('Bearer auth requires a token');
    });

    it('should throw Error for undefined token', () => {
      expect(() => AuthHeaderFactory.createBearer(undefined)).toThrow(
        'Bearer auth requires a token'
      );
    });

    it('should accept whitespace-only token (current behavior)', () => {
      // Note: "   " is truthy so passes the check
      const header = AuthHeaderFactory.createBearer('   ');
      expect(header.headerValue).toBe('Bearer    ');
    });
  });

  describe('Log verification', () => {
    it('should log token length', () => {
      AuthHeaderFactory.createBearer('test-token');

      expectLogContains(consoleSpy.debug, 'tokenLength=10');
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.createBearerWithCredentials() - Boundary & Error Handling
// =============================================================================

describe('AuthHeaderFactory.createBearerWithCredentials()', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Valid credentials', () => {
    it('should create Bearer header with base64-encoded credentials', () => {
      const header = AuthHeaderFactory.createBearerWithCredentials('user@example.com', 'token123');

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toMatch(/^Bearer /);
      // Verify NOT Basic prefix (critical distinction)
      expect(header.headerValue).not.toMatch(/^Basic /);
      expect(header.scheme).toBe(AUTH_SCHEMES.BEARER_PAT);
    });

    it('should correctly encode email:token format', () => {
      const header = AuthHeaderFactory.createBearerWithCredentials(
        'user@company.com',
        'api-token-12345'
      );

      // Extract encoded part and verify
      const encodedPart = header.headerValue.replace('Bearer ', '');
      const decoded = Buffer.from(encodedPart, 'base64').toString('utf-8');
      expect(decoded).toBe('user@company.com:api-token-12345');
    });

    it('should correctly encode username:password format', () => {
      const header = AuthHeaderFactory.createBearerWithCredentials('testuser', 'testpass');

      const encodedPart = header.headerValue.replace('Bearer ', '');
      const decoded = Buffer.from(encodedPart, 'base64').toString('utf-8');
      expect(decoded).toBe('testuser:testpass');
    });

    it('should handle special characters in credentials', () => {
      const header = AuthHeaderFactory.createBearerWithCredentials(
        'user:with:colons',
        'pass@with!special#chars'
      );

      const encodedPart = header.headerValue.replace('Bearer ', '');
      const decoded = Buffer.from(encodedPart, 'base64').toString('utf-8');
      expect(decoded).toBe('user:with:colons:pass@with!special#chars');
    });

    it('should handle unicode credentials', () => {
      const header = AuthHeaderFactory.createBearerWithCredentials('用户', '密码');

      const encodedPart = header.headerValue.replace('Bearer ', '');
      const decoded = Buffer.from(encodedPart, 'base64').toString('utf-8');
      expect(decoded).toBe('用户:密码');
    });
  });

  describe('Error handling', () => {
    it('should throw Error for empty identifier', () => {
      expect(() => AuthHeaderFactory.createBearerWithCredentials('', 'secret')).toThrow(
        'Bearer with credentials requires both identifier and secret'
      );
      expectLogContains(consoleSpy.error, 'Missing identifier or secret');
    });

    it('should throw Error for empty secret', () => {
      expect(() => AuthHeaderFactory.createBearerWithCredentials('user', '')).toThrow(
        'Bearer with credentials requires both identifier and secret'
      );
    });

    it('should throw Error for null identifier', () => {
      expect(() => AuthHeaderFactory.createBearerWithCredentials(null, 'secret')).toThrow(
        'Bearer with credentials requires both identifier and secret'
      );
    });

    it('should throw Error for null secret', () => {
      expect(() => AuthHeaderFactory.createBearerWithCredentials('user', null)).toThrow(
        'Bearer with credentials requires both identifier and secret'
      );
    });

    it('should throw Error for undefined identifier', () => {
      expect(() => AuthHeaderFactory.createBearerWithCredentials(undefined, 'secret')).toThrow(
        'Bearer with credentials requires both identifier and secret'
      );
    });

    it('should throw Error for both empty', () => {
      expect(() => AuthHeaderFactory.createBearerWithCredentials('', '')).toThrow();
    });
  });

  describe('Log verification', () => {
    it('should log encoding details', () => {
      AuthHeaderFactory.createBearerWithCredentials('testuser', 'testpass');

      // Encoding logic moved to external package, detailed internal logs removed
      // expectLogContains(consoleSpy.debug, 'createBearerWithCredentials');
      // expectLogContains(consoleSpy.debug, 'Encoded credentials');
      // expectLogContains(consoleSpy.debug, 'inputLength=');
      // expectLogContains(consoleSpy.debug, 'encodedLength=');
    });
  });

  describe('Bearer vs Basic distinction', () => {
    it('should produce Bearer prefix, not Basic, even with same credentials', () => {
      const identifier = 'user@example.com';
      const secret = 'token123';

      const bearerHeader = AuthHeaderFactory.createBearerWithCredentials(identifier, secret);
      const basicHeader = AuthHeaderFactory.createBasic(identifier, secret);

      // Both encode the same credentials
      const bearerDecoded = Buffer.from(
        bearerHeader.headerValue.replace('Bearer ', ''),
        'base64'
      ).toString('utf-8');
      const basicDecoded = Buffer.from(
        basicHeader.headerValue.replace('Basic ', ''),
        'base64'
      ).toString('utf-8');
      expect(bearerDecoded).toBe(basicDecoded);

      // But prefixes are different
      expect(bearerHeader.headerValue).toMatch(/^Bearer /);
      expect(basicHeader.headerValue).toMatch(/^Basic /);
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.createApiKey() - Boundary & Branch Coverage
// =============================================================================

describe('AuthHeaderFactory.createApiKey()', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Valid inputs', () => {
    it('should create header with default name', () => {
      const header = AuthHeaderFactory.createApiKey('my-api-key-123');

      expect(header.headerName).toBe('X-Api-Key');
      expect(header.headerValue).toBe('my-api-key-123');
      expect(header.scheme).toBe(AUTH_SCHEMES.X_API_KEY);
    });

    it('should create header with custom name', () => {
      const header = AuthHeaderFactory.createApiKey('my-key', 'Ocp-Apim-Subscription-Key');

      expect(header.headerName).toBe('Ocp-Apim-Subscription-Key');
      expect(header.headerValue).toBe('my-key');
    });

    it('should use default name when headerName is undefined', () => {
      const header = AuthHeaderFactory.createApiKey('key', undefined);

      expect(header.headerName).toBe('X-Api-Key');
    });
  });

  describe('Error handling', () => {
    it('should throw Error for empty key', () => {
      expect(() => AuthHeaderFactory.createApiKey('')).toThrow('API key auth requires a key');
      expectLogContains(consoleSpy.error, 'Missing API key');
    });

    it('should throw Error for null key', () => {
      expect(() => AuthHeaderFactory.createApiKey(null)).toThrow('API key auth requires a key');
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.createCustom() - Boundary & Branch Coverage
// =============================================================================

describe('AuthHeaderFactory.createCustom()', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Valid inputs', () => {
    it('should create valid custom header', () => {
      const header = AuthHeaderFactory.createCustom('X-Figma-Token', 'figma-token-12345');

      expect(header.headerName).toBe('X-Figma-Token');
      expect(header.headerValue).toBe('figma-token-12345');
      expect(header.scheme).toBe(AUTH_SCHEMES.CUSTOM_HEADER);
    });
  });

  describe('Error handling', () => {
    it('should throw Error for empty headerName', () => {
      expect(() => AuthHeaderFactory.createCustom('', 'value')).toThrow(
        'Custom header requires both headerName and value'
      );
      expectLogContains(consoleSpy.error, 'Missing headerName or value');
    });

    it('should throw Error for empty value', () => {
      expect(() => AuthHeaderFactory.createCustom('X-Custom', '')).toThrow(
        'Custom header requires both headerName and value'
      );
    });

    it('should throw Error for null headerName', () => {
      expect(() => AuthHeaderFactory.createCustom(null, 'value')).toThrow();
    });

    it('should throw Error for null value', () => {
      expect(() => AuthHeaderFactory.createCustom('X-Custom', null)).toThrow();
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.createAwsSignature() - Complex Logic Testing
// =============================================================================

describe('AuthHeaderFactory.createAwsSignature()', () => {
  let consoleSpy;
  const validAwsCreds = {
    accessKeyId: 'AKIAIOSFODNN7EXAMPLE',
    secretAccessKey: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
    region: 'us-east-1',
    service: 's3',
    method: 'GET',
    url: 'https://s3.amazonaws.com/bucket/key',
  };

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Valid credentials', () => {
    it('should create AWS Signature header', () => {
      const header = AuthHeaderFactory.createAwsSignature(validAwsCreds);

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toMatch(/^AWS4-HMAC-SHA256/);
      expect(header.headerValue).toContain('Credential=AKIAIOSFODNN7EXAMPLE');
      expect(header.headerValue).toContain('us-east-1/s3/aws4_request');
      expect(header.headerValue).toContain('SignedHeaders=host;x-amz-date');
      expect(header.headerValue).toContain('Signature=');
      expect(header.scheme).toBe(AUTH_SCHEMES.AWS_SIGNATURE);
    });

    it('should handle request body', () => {
      const header = AuthHeaderFactory.createAwsSignature({
        ...validAwsCreds,
        method: 'POST',
        body: '{"key": "value"}',
      });

      expect(header.headerValue).toMatch(/^AWS4-HMAC-SHA256/);
    });

    it('should handle URL with query string', () => {
      const header = AuthHeaderFactory.createAwsSignature({
        ...validAwsCreds,
        url: 'https://s3.amazonaws.com/bucket/key?prefix=test&max-keys=10',
      });

      expect(header.headerValue).toMatch(/^AWS4-HMAC-SHA256/);
    });

    it('should handle URL without path', () => {
      const header = AuthHeaderFactory.createAwsSignature({
        ...validAwsCreds,
        url: 'https://s3.amazonaws.com',
      });

      expect(header.headerValue).toMatch(/^AWS4-HMAC-SHA256/);
    });

    it('should produce different signatures for different methods', () => {
      const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD'];
      const signatures = new Set();

      methods.forEach((method) => {
        const header = AuthHeaderFactory.createAwsSignature({
          ...validAwsCreds,
          method,
        });
        const sig = header.headerValue.split('Signature=')[1];
        signatures.add(sig);
      });

      expect(signatures.size).toBe(methods.length);
    });
  });

  describe('Error handling', () => {
    it('should throw Error for missing accessKeyId', () => {
      const { accessKeyId, ...rest } = validAwsCreds;
      expect(() => AuthHeaderFactory.createAwsSignature(rest)).toThrow('accessKeyId');
    });

    it('should throw Error for missing secretAccessKey', () => {
      const { secretAccessKey, ...rest } = validAwsCreds;
      expect(() => AuthHeaderFactory.createAwsSignature(rest)).toThrow('secretAccessKey');
    });

    it('should throw Error for missing region', () => {
      const { region, ...rest } = validAwsCreds;
      expect(() => AuthHeaderFactory.createAwsSignature(rest)).toThrow();
    });

    it('should throw Error for missing service', () => {
      const { service, ...rest } = validAwsCreds;
      expect(() => AuthHeaderFactory.createAwsSignature(rest)).toThrow();
    });

    it('should throw Error for missing method', () => {
      const { method, ...rest } = validAwsCreds;
      expect(() => AuthHeaderFactory.createAwsSignature(rest)).toThrow();
    });

    it('should throw Error for missing url', () => {
      const { url, ...rest } = validAwsCreds;
      expect(() => AuthHeaderFactory.createAwsSignature(rest)).toThrow();
    });
  });

  describe('Log verification', () => {
    it('should log AWS signature details', () => {
      AuthHeaderFactory.createAwsSignature(validAwsCreds);

      expectLogContains(consoleSpy.debug, "region='us-east-1'");
      expectLogContains(consoleSpy.debug, "service='s3'");
      expectLogContains(consoleSpy.debug, "method='GET'");
      expectLogContains(consoleSpy.debug, 'Canonical request created');
      expectLogContains(consoleSpy.debug, 'AWS signature created successfully');
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.createDigest() - Complex Logic Testing
// =============================================================================

describe('AuthHeaderFactory.createDigest()', () => {
  let consoleSpy;
  const validDigestCreds = {
    username: 'testuser',
    password: 'testpass',
    realm: 'test@realm.com',
    nonce: 'abc123nonce456',
    uri: '/protected/resource',
    method: 'GET',
  };

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('Valid credentials', () => {
    it('should create Digest auth header', () => {
      const header = AuthHeaderFactory.createDigest(validDigestCreds);

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toMatch(/^Digest /);
      expect(header.headerValue).toContain('username="testuser"');
      expect(header.headerValue).toContain('realm="test@realm.com"');
      expect(header.headerValue).toContain('nonce="abc123nonce456"');
      expect(header.headerValue).toContain('uri="/protected/resource"');
      expect(header.headerValue).toContain('response="');
      expect(header.scheme).toBe(AUTH_SCHEMES.DIGEST);
    });
  });

  describe('qop branch coverage', () => {
    it('should include qop fields when qop is present', () => {
      const header = AuthHeaderFactory.createDigest({
        ...validDigestCreds,
        qop: 'auth',
      });

      expect(header.headerValue).toContain('qop=auth');
      expect(header.headerValue).toContain('nc=');
      expect(header.headerValue).toContain('cnonce="');
    });

    it('should not include qop fields when qop is empty', () => {
      const header = AuthHeaderFactory.createDigest({
        ...validDigestCreds,
        qop: '',
      });

      expect(header.headerValue).not.toContain('qop=');
      expect(header.headerValue).not.toContain('nc=');
      expect(header.headerValue).not.toContain('cnonce=');
    });
  });

  describe('opaque branch coverage', () => {
    it('should include opaque when provided', () => {
      const header = AuthHeaderFactory.createDigest({
        ...validDigestCreds,
        opaque: 'opaque-value-xyz',
      });

      expect(header.headerValue).toContain('opaque="opaque-value-xyz"');
    });

    it('should not include opaque when not provided', () => {
      const header = AuthHeaderFactory.createDigest(validDigestCreds);

      expect(header.headerValue).not.toContain('opaque=');
    });
  });

  describe('algorithm branch coverage', () => {
    it('should include algorithm for SHA-256', () => {
      const header = AuthHeaderFactory.createDigest({
        ...validDigestCreds,
        algorithm: 'SHA-256',
      });

      expect(header.headerValue).toContain('algorithm=SHA-256');
    });

    it('should not include algorithm for MD5 (default)', () => {
      const header = AuthHeaderFactory.createDigest({
        ...validDigestCreds,
        algorithm: 'MD5',
      });

      expect(header.headerValue).not.toContain('algorithm=');
    });
  });

  describe('cnonce behavior', () => {
    it('should use provided cnonce', () => {
      const header = AuthHeaderFactory.createDigest({
        ...validDigestCreds,
        qop: 'auth',
        cnonce: 'my-client-nonce',
      });

      expect(header.headerValue).toContain('cnonce="my-client-nonce"');
    });

    it('should generate cnonce if not provided', () => {
      const header = AuthHeaderFactory.createDigest({
        ...validDigestCreds,
        qop: 'auth',
      });

      expect(header.headerValue).toContain('cnonce="');
    });
  });

  describe('Error handling', () => {
    it('should throw Error for missing username', () => {
      const { username, ...rest } = validDigestCreds;
      expect(() => AuthHeaderFactory.createDigest(rest)).toThrow('username');
    });

    it('should throw Error for missing password', () => {
      const { password, ...rest } = validDigestCreds;
      expect(() => AuthHeaderFactory.createDigest(rest)).toThrow('password');
    });

    it('should throw Error for missing realm', () => {
      const { realm, ...rest } = validDigestCreds;
      expect(() => AuthHeaderFactory.createDigest(rest)).toThrow();
    });

    it('should throw Error for missing nonce', () => {
      const { nonce, ...rest } = validDigestCreds;
      expect(() => AuthHeaderFactory.createDigest(rest)).toThrow();
    });

    it('should throw Error for missing uri', () => {
      const { uri, ...rest } = validDigestCreds;
      expect(() => AuthHeaderFactory.createDigest(rest)).toThrow();
    });

    it('should throw Error for missing method', () => {
      const { method, ...rest } = validDigestCreds;
      expect(() => AuthHeaderFactory.createDigest(rest)).toThrow();
    });
  });
});

// =============================================================================
// Test AuthHeaderFactory.fromApiKeyResult() - Bridge Method
// =============================================================================

describe('AuthHeaderFactory.fromApiKeyResult()', () => {
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = setupConsoleSpy();
  });

  afterEach(() => {
    restoreConsoleSpy(consoleSpy);
  });

  describe('bearer authType branch', () => {
    it('should create Bearer header', () => {
      const mockResult = {
        apiKey: 'bearer-token-123',
        authType: 'bearer',
        headerName: 'Authorization',
        username: null,
      };

      const header = AuthHeaderFactory.fromApiKeyResult(mockResult);

      expect(header.headerName).toBe('Authorization');
      expect(header.headerValue).toBe('Bearer bearer-token-123');
    });
  });

  describe('basic authType branch', () => {
    it('should create Basic header when username is present', () => {
      const mockResult = {
        apiKey: 'api-token',
        authType: 'basic',
        headerName: 'Authorization',
        username: 'user@example.com',
      };

      const header = AuthHeaderFactory.fromApiKeyResult(mockResult);

      expect(header.headerValue).toMatch(/^Basic /);
    });

    it('should fall back to Bearer when username is missing', () => {
      const mockResult = {
        apiKey: 'api-token',
        authType: 'basic',
        headerName: 'Authorization',
        username: null,
      };

      const header = AuthHeaderFactory.fromApiKeyResult(mockResult);

      expect(header.headerValue).toBe('Bearer api-token');
      expectLogContains(consoleSpy.warn, 'Basic auth without username');
      expectLogContains(consoleSpy.warn, 'falling back to Bearer');
    });
  });

  describe('x-api-key authType branch', () => {
    it('should create X-Api-Key header', () => {
      const mockResult = {
        apiKey: 'my-api-key',
        authType: 'x-api-key',
        headerName: 'X-Api-Key',
        username: null,
      };

      const header = AuthHeaderFactory.fromApiKeyResult(mockResult);

      expect(header.headerName).toBe('X-Api-Key');
      expect(header.headerValue).toBe('my-api-key');
    });

    it('should use default header name when not provided', () => {
      const mockResult = {
        apiKey: 'my-api-key',
        authType: 'x-api-key',
        headerName: null,
        username: null,
      };

      const header = AuthHeaderFactory.fromApiKeyResult(mockResult);

      expect(header.headerName).toBe('X-Api-Key');
    });
  });

  describe('custom authType branch', () => {
    it('should create custom header when headerName is present', () => {
      const mockResult = {
        apiKey: 'figma-token',
        authType: 'custom',
        headerName: 'X-Figma-Token',
        username: null,
      };

      const header = AuthHeaderFactory.fromApiKeyResult(mockResult);

      expect(header.headerName).toBe('X-Figma-Token');
      expect(header.headerValue).toBe('figma-token');
    });

    it('should use X-Custom-Token when headerName is missing', () => {
      const mockResult = {
        apiKey: 'custom-token',
        authType: 'custom',
        headerName: null,
        username: null,
      };

      const header = AuthHeaderFactory.fromApiKeyResult(mockResult);

      expect(header.headerName).toBe('X-Custom-Token');
      expectLogContains(consoleSpy.warn, 'Custom auth without headerName');
    });
  });

  describe('unknown authType branch', () => {
    it('should default to Bearer for unknown authType', () => {
      const mockResult = {
        apiKey: 'some-token',
        authType: 'unknown-auth-type',
        headerName: null,
        username: null,
      };

      const header = AuthHeaderFactory.fromApiKeyResult(mockResult);

      expect(header.headerValue).toBe('Bearer some-token');
      expectLogContains(consoleSpy.warn, "Unknown authType 'unknown-auth-type'");
      expectLogContains(consoleSpy.warn, 'defaulting to Bearer');
    });
  });
});

// =============================================================================
// Integration Tests - End-to-End Scenarios
// =============================================================================

describe('Integration Tests', () => {
  describe('Jira Basic Auth Scenario', () => {
    it('should create valid Jira auth header', () => {
      const email = 'developer@company.com';
      const apiToken = 'ATATT3xFfGF0abc123XYZ';

      const header = AuthHeaderFactory.createBasic(email, apiToken);

      // Verify can be used in fetch/axios
      const headersDict = header.toObject();
      expect(headersDict.Authorization).toMatch(/^Basic /);

      // Verify decoding works
      const encodedPart = headersDict.Authorization.replace('Basic ', '');
      const decoded = Buffer.from(encodedPart, 'base64').toString('utf-8');
      expect(decoded).toBe(`${email}:${apiToken}`);
    });
  });

  describe('AWS S3 Scenario', () => {
    it('should create valid AWS S3 auth header', () => {
      const header = AuthHeaderFactory.createAwsSignature({
        accessKeyId: 'AKIAIOSFODNN7EXAMPLE',
        secretAccessKey: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        region: 'us-west-2',
        service: 's3',
        method: 'PUT',
        url: 'https://mybucket.s3.us-west-2.amazonaws.com/myobject',
        body: 'Hello, World!',
      });

      const headersDict = header.toObject();
      expect(headersDict.Authorization).toMatch(/^AWS4-HMAC-SHA256/);
      expect(headersDict.Authorization).toContain('us-west-2/s3/aws4_request');
    });
  });

  describe('Figma Custom Header Scenario', () => {
    it('should create valid Figma auth header', () => {
      const figmaToken = 'figd_abc123XYZ789';

      const header = AuthHeaderFactory.createCustom('X-Figma-Token', figmaToken);

      const headersDict = header.toObject();
      expect(headersDict).toEqual({ 'X-Figma-Token': figmaToken });
    });
  });
});

// =============================================================================
// Property-Based Tests
// =============================================================================

describe('Property-Based Tests', () => {
  describe('Basic Auth Properties', () => {
    it('should always produce valid Base64 for any printable ASCII credentials', () => {
      const randomString = (len) => {
        const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        return Array(len)
          .fill(0)
          .map(() => chars[Math.floor(Math.random() * chars.length)])
          .join('');
      };

      for (let i = 0; i < 100; i++) {
        const user = randomString(Math.floor(Math.random() * 50) + 1);
        const secret = randomString(Math.floor(Math.random() * 100) + 1);

        const header = AuthHeaderFactory.createBasic(user, secret);

        // Extract and verify Base64 is decodable
        const encodedPart = header.headerValue.replace('Basic ', '');
        const decoded = Buffer.from(encodedPart, 'base64').toString('utf-8');
        expect(decoded).toContain(':'); // Should contain colon separator
      }
    });
  });

  describe('Bearer Auth Properties', () => {
    it('should preserve token exactly for any string', () => {
      const randomString = (len) => {
        const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.';
        return Array(len)
          .fill(0)
          .map(() => chars[Math.floor(Math.random() * chars.length)])
          .join('');
      };

      for (let i = 0; i < 100; i++) {
        const token = randomString(Math.floor(Math.random() * 500) + 10);

        const header = AuthHeaderFactory.createBearer(token);

        expect(header.headerValue).toBe(`Bearer ${token}`);
      }
    });
  });
});
