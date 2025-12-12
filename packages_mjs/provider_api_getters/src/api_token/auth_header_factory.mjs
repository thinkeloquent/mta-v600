/**
 * Auth Header Factory - RFC-compliant Authorization header construction.
 *
 * This module provides a factory pattern for creating HTTP Authorization headers
 * following RFC 7617 (Basic), RFC 6750 (Bearer), RFC 7616 (Digest), and AWS Signature v4.
 *
 * Supported auth schemes:
 * - Basic (user:password, email:token, user:token)
 * - Bearer (PAT, OAuth, JWT)
 * - X-Api-Key (custom header)
 * - Custom header (any header name/value)
 * - AWS Signature v4 (HMAC)
 * - Digest (RFC 7616)
 */

import { createHmac, createHash, randomBytes } from 'crypto';
import { encodeAuth } from '@internal/fetch-auth-encoding';

// Simple console logger for defensive programming
const logger = {
  debug: (msg) => console.debug(`[DEBUG] auth_header_factory: ${msg}`),
  info: (msg) => console.info(`[INFO] auth_header_factory: ${msg}`),
  warn: (msg) => console.warn(`[WARN] auth_header_factory: ${msg}`),
  error: (msg) => console.error(`[ERROR] auth_header_factory: ${msg}`),
};

/**
 * Auth scheme enumeration.
 * @readonly
 * @enum {string}
 */
export const AUTH_SCHEMES = Object.freeze({
  // Basic variants (RFC 7617)
  BASIC_USER_PASS: 'basic_user_pass',
  BASIC_EMAIL_TOKEN: 'basic_email_token',
  BASIC_USER_TOKEN: 'basic_user_token',

  // Bearer variants (RFC 6750)
  BEARER_PAT: 'bearer_pat',
  BEARER_OAUTH: 'bearer_oauth',
  BEARER_JWT: 'bearer_jwt',

  // API Key (custom header)
  X_API_KEY: 'x_api_key',

  // Custom header
  CUSTOM_HEADER: 'custom_header',

  // AWS Signature v4
  AWS_SIGNATURE: 'aws_signature',

  // Digest (RFC 7616)
  DIGEST: 'digest',
});

/**
 * Mapping from config auth types to factory methods.
 * Used to bridge existing config values to factory calls.
 */
export const CONFIG_AUTH_TYPE_MAP = Object.freeze({
  bearer: AUTH_SCHEMES.BEARER_PAT,
  basic: AUTH_SCHEMES.BASIC_USER_TOKEN,
  'x-api-key': AUTH_SCHEMES.X_API_KEY,
  custom: AUTH_SCHEMES.CUSTOM_HEADER,
  aws_signature: AUTH_SCHEMES.AWS_SIGNATURE,
  digest: AUTH_SCHEMES.DIGEST,
});

/**
 * Result of auth header construction.
 */
export class AuthHeader {
  /**
   * @param {string} headerName - HTTP header name
   * @param {string} headerValue - HTTP header value
   * @param {string} scheme - Auth scheme used
   */
  constructor(headerName, headerValue, scheme) {
    logger.debug(
      `AuthHeader.constructor: Creating header ` +
      `name='${headerName}', scheme='${scheme}', valueLength=${headerValue?.length || 0}`
    );

    this.headerName = headerName;
    this.headerValue = headerValue;
    this.scheme = scheme;

    logger.debug('AuthHeader.constructor: Header created successfully');
  }

  /**
   * Convert to object for use in fetch/axios headers.
   * @returns {Object}
   */
  toObject() {
    return { [this.headerName]: this.headerValue };
  }

  /**
   * Convert to string for logging (masked).
   * @returns {string}
   */
  toString() {
    const maskedValue = this.headerValue.length > 10
      ? this.headerValue.substring(0, 10) + '***'
      : '***';
    return `${this.headerName}: ${maskedValue}`;
  }
}

/**
 * Factory for creating RFC-compliant Authorization headers.
 */
export class AuthHeaderFactory {
  /**
   * Create an auth header using a scheme and credentials.
   *
   * @param {string} scheme - Auth scheme from AUTH_SCHEMES
   * @param {Object} credentials - Credentials object (scheme-specific)
   * @returns {AuthHeader}
   */
  static create(scheme, credentials = {}) {
    logger.debug(`AuthHeaderFactory.create: Creating header for scheme='${scheme}'`);

    switch (scheme) {
      case AUTH_SCHEMES.BASIC_USER_PASS:
      case AUTH_SCHEMES.BASIC_EMAIL_TOKEN:
      case AUTH_SCHEMES.BASIC_USER_TOKEN:
        return AuthHeaderFactory.createBasic(
          credentials.user || credentials.email || credentials.username,
          credentials.secret || credentials.password || credentials.token || credentials.apiKey
        );

      case AUTH_SCHEMES.BEARER_PAT:
      case AUTH_SCHEMES.BEARER_OAUTH:
      case AUTH_SCHEMES.BEARER_JWT:
        return AuthHeaderFactory.createBearer(
          credentials.token || credentials.apiKey
        );

      case AUTH_SCHEMES.X_API_KEY:
        return AuthHeaderFactory.createApiKey(
          credentials.key || credentials.apiKey,
          credentials.headerName
        );

      case AUTH_SCHEMES.CUSTOM_HEADER:
        return AuthHeaderFactory.createCustom(
          credentials.headerName,
          credentials.value || credentials.apiKey
        );

      case AUTH_SCHEMES.AWS_SIGNATURE:
        return AuthHeaderFactory.createAwsSignature(credentials);

      case AUTH_SCHEMES.DIGEST:
        return AuthHeaderFactory.createDigest(credentials);

      default:
        logger.warn(`AuthHeaderFactory.create: Unknown scheme '${scheme}', defaulting to Bearer`);
        return AuthHeaderFactory.createBearer(credentials.token || credentials.apiKey);
    }
  }

  /**
   * Create a Basic auth header (RFC 7617).
   *
   * Encodes credentials as Base64(user:secret).
   * Works for all Basic variants:
   * - username:password
   * - email:token (Atlassian products)
   * - username:token (Jenkins, GitHub Enterprise)
   *
   * @param {string} user - Username, email, or identifier
   * @param {string} secret - Password, token, or API key
   * @returns {AuthHeader}
   */
  static createBasic(user, secret) {
    logger.debug(
      `AuthHeaderFactory.createBasic: Creating Basic auth ` +
      `user='${user}', secretLength=${secret?.length || 0}`
    );

    if (!user || !secret) {
      logger.error('AuthHeaderFactory.createBasic: Missing user or secret');
      throw new Error('Basic auth requires both user and secret');
    }

    // Use fetch-auth-encoding package
    const headers = encodeAuth('basic', { username: user, password: secret });

    return new AuthHeader('Authorization', headers.Authorization, AUTH_SCHEMES.BASIC_USER_PASS);
  }

  /**
   * Create a Bearer auth header (RFC 6750).
   *
   * Used for:
   * - Personal Access Tokens (PAT)
   * - OAuth 2.0 tokens
   * - JWT tokens
   *
   * @param {string} token - Bearer token
   * @returns {AuthHeader}
   */
  static createBearer(token) {
    logger.debug(
      `AuthHeaderFactory.createBearer: Creating Bearer auth ` +
      `tokenLength=${token?.length || 0}`
    );

    if (!token) {
      logger.error('AuthHeaderFactory.createBearer: Missing token');
      throw new Error('Bearer auth requires a token');
    }

    return new AuthHeader('Authorization', `Bearer ${token}`, AUTH_SCHEMES.BEARER_PAT);
  }

  /**
   * Create a Bearer auth header with base64-encoded credentials (RFC 6750).
   *
   * Used for:
   * - bearer_email_token (Confluence with Bearer instead of Basic)
   * - bearer_username_token
   * - bearer_email_password
   * - bearer_username_password
   *
   * @param {string} identifier - Username or email
   * @param {string} secret - Password, token, or API key
   * @returns {AuthHeader}
   */
  static createBearerWithCredentials(identifier, secret) {
    logger.debug(
      `AuthHeaderFactory.createBearerWithCredentials: Creating Bearer auth with credentials ` +
      `identifier='${identifier}', secretLength=${secret?.length || 0}`
    );

    if (!identifier || !secret) {
      logger.error('AuthHeaderFactory.createBearerWithCredentials: Missing identifier or secret');
      throw new Error('Bearer with credentials requires both identifier and secret');
    }

    // Use fetch-auth-encoding package (bearer_username_password produces "Bearer base64(u:p)")
    const headers = encodeAuth('bearer_username_password', { username: identifier, password: secret });

    return new AuthHeader('Authorization', headers.Authorization, AUTH_SCHEMES.BEARER_PAT);
  }

  /**
   * Create an X-Api-Key header.
   *
   * Common in simpler public APIs (Google Maps, Weather APIs).
   *
   * @param {string} key - API key
   * @param {string} [headerName='X-Api-Key'] - Custom header name
   * @returns {AuthHeader}
   */
  static createApiKey(key, headerName = 'X-Api-Key') {
    logger.debug(
      `AuthHeaderFactory.createApiKey: Creating API key auth ` +
      `headerName='${headerName}', keyLength=${key?.length || 0}`
    );

    if (!key) {
      logger.error('AuthHeaderFactory.createApiKey: Missing API key');
      throw new Error('API key auth requires a key');
    }

    return new AuthHeader(headerName, key, AUTH_SCHEMES.X_API_KEY);
  }

  /**
   * Create a custom header.
   *
   * Used for provider-specific headers like X-Figma-Token.
   *
   * @param {string} headerName - Header name
   * @param {string} value - Header value
   * @returns {AuthHeader}
   */
  static createCustom(headerName, value) {
    logger.debug(
      `AuthHeaderFactory.createCustom: Creating custom header ` +
      `name='${headerName}', valueLength=${value?.length || 0}`
    );

    if (!headerName || !value) {
      logger.error('AuthHeaderFactory.createCustom: Missing headerName or value');
      throw new Error('Custom header requires both headerName and value');
    }

    return new AuthHeader(headerName, value, AUTH_SCHEMES.CUSTOM_HEADER);
  }

  /**
   * Create an AWS Signature v4 header.
   *
   * Implements AWS4-HMAC-SHA256 signing for AWS services.
   *
   * @param {Object} options - AWS signature options
   * @param {string} options.accessKeyId - AWS Access Key ID
   * @param {string} options.secretAccessKey - AWS Secret Access Key
   * @param {string} options.region - AWS region (e.g., 'us-east-1')
   * @param {string} options.service - AWS service (e.g., 's3', 'execute-api')
   * @param {string} options.method - HTTP method (GET, POST, etc.)
   * @param {string} options.url - Full request URL
   * @param {string} [options.body=''] - Request body
   * @param {Object} [options.headers={}] - Additional headers to sign
   * @param {string} [options.sessionToken=null] - AWS session token (for temp credentials)
   * @returns {AuthHeader}
   */
  static createAwsSignature({
    accessKeyId,
    secretAccessKey,
    region,
    service,
    method,
    url,
    body = '',
    headers = {},
    sessionToken = null,
  }) {
    logger.debug(
      `AuthHeaderFactory.createAwsSignature: Creating AWS signature ` +
      `region='${region}', service='${service}', method='${method}'`
    );

    if (!accessKeyId || !secretAccessKey || !region || !service || !method || !url) {
      logger.error('AuthHeaderFactory.createAwsSignature: Missing required parameters');
      throw new Error('AWS signature requires accessKeyId, secretAccessKey, region, service, method, and url');
    }

    const parsedUrl = new URL(url);
    const host = parsedUrl.host;
    const path = parsedUrl.pathname + parsedUrl.search;
    const now = new Date();
    const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, '');
    const dateStamp = amzDate.substring(0, 8);

    // Hash function helper
    const sha256 = (data) => createHash('sha256').update(data, 'utf8').digest('hex');

    // HMAC function helper
    const hmac = (key, data) => createHmac('sha256', key).update(data, 'utf8').digest();

    // Step 1: Create canonical request
    const signedHeaders = 'host;x-amz-date';
    const payloadHash = sha256(body);

    const canonicalRequest = [
      method.toUpperCase(),
      path || '/',
      '', // canonical query string (empty for now)
      `host:${host}`,
      `x-amz-date:${amzDate}`,
      '', // blank line after headers
      signedHeaders,
      payloadHash,
    ].join('\n');

    logger.debug(
      `AuthHeaderFactory.createAwsSignature: Canonical request created ` +
      `(length=${canonicalRequest.length})`
    );

    // Step 2: Create string to sign
    const algorithm = 'AWS4-HMAC-SHA256';
    const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
    const stringToSign = [
      algorithm,
      amzDate,
      credentialScope,
      sha256(canonicalRequest),
    ].join('\n');

    // Step 3: Calculate signature
    const kDate = hmac(`AWS4${secretAccessKey}`, dateStamp);
    const kRegion = hmac(kDate, region);
    const kService = hmac(kRegion, service);
    const kSigning = hmac(kService, 'aws4_request');
    const signature = createHmac('sha256', kSigning).update(stringToSign, 'utf8').digest('hex');

    // Step 4: Build authorization header
    const authorizationHeader =
      `${algorithm} ` +
      `Credential=${accessKeyId}/${credentialScope}, ` +
      `SignedHeaders=${signedHeaders}, ` +
      `Signature=${signature}`;

    logger.debug('AuthHeaderFactory.createAwsSignature: AWS signature created successfully');

    return new AuthHeader('Authorization', authorizationHeader, AUTH_SCHEMES.AWS_SIGNATURE);
  }

  /**
   * Create a Digest auth header (RFC 7616).
   *
   * Used for challenge-response authentication.
   * Note: This generates the response to a server challenge.
   *
   * @param {Object} options - Digest auth options
   * @param {string} options.username - Username
   * @param {string} options.password - Password
   * @param {string} options.realm - Server realm from challenge
   * @param {string} options.nonce - Server nonce from challenge
   * @param {string} options.uri - Request URI
   * @param {string} options.method - HTTP method
   * @param {string} [options.qop='auth'] - Quality of protection
   * @param {string} [options.nc='00000001'] - Nonce count
   * @param {string} [options.cnonce=null] - Client nonce (generated if not provided)
   * @param {string} [options.opaque=null] - Opaque value from server
   * @param {string} [options.algorithm='MD5'] - Hash algorithm (MD5 or SHA-256)
   * @returns {AuthHeader}
   */
  static createDigest({
    username,
    password,
    realm,
    nonce,
    uri,
    method,
    qop = 'auth',
    nc = '00000001',
    cnonce = null,
    opaque = null,
    algorithm = 'MD5',
  }) {
    logger.debug(
      `AuthHeaderFactory.createDigest: Creating Digest auth ` +
      `username='${username}', realm='${realm}', uri='${uri}', method='${method}'`
    );

    if (!username || !password || !realm || !nonce || !uri || !method) {
      logger.error('AuthHeaderFactory.createDigest: Missing required parameters');
      throw new Error('Digest auth requires username, password, realm, nonce, uri, and method');
    }

    // Generate client nonce if not provided
    const clientNonce = cnonce || randomBytes(8).toString('hex');

    // Hash function based on algorithm
    const hash = (data) => {
      const algo = algorithm.toLowerCase() === 'sha-256' ? 'sha256' : 'md5';
      return createHash(algo).update(data).digest('hex');
    };

    // Calculate HA1 = hash(username:realm:password)
    const ha1 = hash(`${username}:${realm}:${password}`);

    // Calculate HA2 = hash(method:uri)
    const ha2 = hash(`${method}:${uri}`);

    // Calculate response
    let response;
    if (qop) {
      // RFC 2617 with qop
      response = hash(`${ha1}:${nonce}:${nc}:${clientNonce}:${qop}:${ha2}`);
    } else {
      // RFC 2069 (legacy, no qop)
      response = hash(`${ha1}:${nonce}:${ha2}`);
    }

    // Build Digest header value
    const parts = [
      `username="${username}"`,
      `realm="${realm}"`,
      `nonce="${nonce}"`,
      `uri="${uri}"`,
      `response="${response}"`,
    ];

    if (qop) {
      parts.push(`qop=${qop}`);
      parts.push(`nc=${nc}`);
      parts.push(`cnonce="${clientNonce}"`);
    }

    if (opaque) {
      parts.push(`opaque="${opaque}"`);
    }

    if (algorithm && algorithm !== 'MD5') {
      parts.push(`algorithm=${algorithm}`);
    }

    const headerValue = `Digest ${parts.join(', ')}`;

    logger.debug('AuthHeaderFactory.createDigest: Digest auth header created successfully');

    return new AuthHeader('Authorization', headerValue, AUTH_SCHEMES.DIGEST);
  }

  /**
   * Create an auth header from an existing ApiKeyResult.
   *
   * Bridge method for integrating with existing provider implementations.
   *
   * @param {Object} apiKeyResult - ApiKeyResult instance
   * @param {string} apiKeyResult.apiKey - The API key/token
   * @param {string} apiKeyResult.authType - Auth type (bearer, basic, x-api-key, custom)
   * @param {string} [apiKeyResult.headerName] - Header name for custom auth
   * @param {string} [apiKeyResult.username] - Username for basic auth
   * @returns {AuthHeader}
   */
  static fromApiKeyResult(apiKeyResult) {
    logger.debug(
      `AuthHeaderFactory.fromApiKeyResult: Creating header from ApiKeyResult ` +
      `authType='${apiKeyResult.authType}', hasApiKey=${!!apiKeyResult.apiKey}`
    );

    const { apiKey, authType, headerName, username } = apiKeyResult;

    switch (authType) {
      case 'bearer':
        return AuthHeaderFactory.createBearer(apiKey);

      case 'basic':
        if (!username) {
          logger.warn(
            'AuthHeaderFactory.fromApiKeyResult: Basic auth without username, ' +
            'falling back to Bearer'
          );
          return AuthHeaderFactory.createBearer(apiKey);
        }
        return AuthHeaderFactory.createBasic(username, apiKey);

      case 'x-api-key':
        return AuthHeaderFactory.createApiKey(apiKey, headerName || 'X-Api-Key');

      case 'custom':
        if (!headerName) {
          logger.warn(
            'AuthHeaderFactory.fromApiKeyResult: Custom auth without headerName, ' +
            'using X-Custom-Token'
          );
          return AuthHeaderFactory.createCustom('X-Custom-Token', apiKey);
        }
        return AuthHeaderFactory.createCustom(headerName, apiKey);

      default:
        logger.warn(
          `AuthHeaderFactory.fromApiKeyResult: Unknown authType '${authType}', ` +
          'defaulting to Bearer'
        );
        return AuthHeaderFactory.createBearer(apiKey);
    }
  }
}
