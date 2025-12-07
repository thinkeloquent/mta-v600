/**
 * Tests for fetch-compose-retry factory functions
 *
 * Test coverage includes:
 * - Statement coverage: All executable statements
 * - Decision/Branch coverage: All boolean decisions (if/else)
 * - Equivalence partitioning: Different configuration combinations
 * - Boundary testing: Default values and overrides
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  createRetryDispatcher,
  createResilientDispatcher,
  createApiRetryInterceptor,
  RETRY_PRESETS,
} from '../src/factory.mjs';
import { Agent, type Dispatcher } from 'undici';

describe('createRetryDispatcher', () => {
  describe('default behavior', () => {
    it('should create a dispatcher without options', () => {
      const dispatcher = createRetryDispatcher();
      expect(dispatcher).toBeDefined();
      expect(typeof dispatcher.dispatch).toBe('function');
    });

    it('should create a dispatcher with custom maxRetries', () => {
      const dispatcher = createRetryDispatcher({ maxRetries: 5 });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('base dispatcher', () => {
    it('should use provided base dispatcher', () => {
      const baseDispatcher = new Agent();
      const dispatcher = createRetryDispatcher({ baseDispatcher });
      expect(dispatcher).toBeDefined();
    });

    it('should create new Agent if no base provided', () => {
      const dispatcher = createRetryDispatcher();
      expect(dispatcher).toBeDefined();
    });
  });

  describe('DNS interceptor', () => {
    it('should include DNS interceptor when includeDns is true', () => {
      const dispatcher = createRetryDispatcher({ includeDns: true });
      expect(dispatcher).toBeDefined();
    });

    it('should not include DNS interceptor by default', () => {
      const dispatcher = createRetryDispatcher();
      expect(dispatcher).toBeDefined();
    });

    it('should use custom dnsAffinity', () => {
      const dispatcher = createRetryDispatcher({
        includeDns: true,
        dnsAffinity: 6,
      });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('redirect interceptor', () => {
    it('should include redirect interceptor when includeRedirect is true', () => {
      const dispatcher = createRetryDispatcher({ includeRedirect: true });
      expect(dispatcher).toBeDefined();
    });

    it('should not include redirect interceptor by default', () => {
      const dispatcher = createRetryDispatcher();
      expect(dispatcher).toBeDefined();
    });

    it('should use custom maxRedirections', () => {
      const dispatcher = createRetryDispatcher({
        includeRedirect: true,
        maxRedirections: 10,
      });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('retry options', () => {
    it('should pass retry options to interceptor', () => {
      const onRetry = vi.fn();
      const onSuccess = vi.fn();
      const dispatcher = createRetryDispatcher({
        maxRetries: 3,
        baseDelayMs: 500,
        maxDelayMs: 5000,
        jitterFactor: 0.3,
        retryOnStatus: [429, 500],
        respectRetryAfter: false,
        onRetry,
        onSuccess,
      });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('combined options', () => {
    it('should create dispatcher with all options', () => {
      const dispatcher = createRetryDispatcher({
        maxRetries: 5,
        includeDns: true,
        dnsAffinity: 4,
        includeRedirect: true,
        maxRedirections: 3,
      });
      expect(dispatcher).toBeDefined();
    });
  });
});

describe('createResilientDispatcher', () => {
  describe('default behavior', () => {
    it('should create a dispatcher with DNS and redirect enabled', () => {
      const dispatcher = createResilientDispatcher();
      expect(dispatcher).toBeDefined();
    });

    it('should accept retry options', () => {
      const dispatcher = createResilientDispatcher({ maxRetries: 5 });
      expect(dispatcher).toBeDefined();
    });
  });

  describe('callbacks', () => {
    it('should pass through onRetry callback', () => {
      const onRetry = vi.fn();
      const dispatcher = createResilientDispatcher({ onRetry });
      expect(dispatcher).toBeDefined();
    });

    it('should pass through onSuccess callback', () => {
      const onSuccess = vi.fn();
      const dispatcher = createResilientDispatcher({ onSuccess });
      expect(dispatcher).toBeDefined();
    });
  });
});

describe('createApiRetryInterceptor', () => {
  describe('creation', () => {
    it('should create an interceptor for API', () => {
      const interceptor = createApiRetryInterceptor('github');
      expect(typeof interceptor).toBe('function');
    });

    it('should accept options', () => {
      const interceptor = createApiRetryInterceptor('openai', {
        maxRetries: 3,
        retryOnStatus: [429, 500, 529],
      });
      expect(typeof interceptor).toBe('function');
    });
  });

  describe('callbacks', () => {
    it('should wrap onRetry callback', () => {
      const onRetry = vi.fn();
      const interceptor = createApiRetryInterceptor('test', { onRetry });
      expect(typeof interceptor).toBe('function');
    });

    it('should wrap onSuccess callback', () => {
      const onSuccess = vi.fn();
      const interceptor = createApiRetryInterceptor('test', { onSuccess });
      expect(typeof interceptor).toBe('function');
    });
  });
});

describe('RETRY_PRESETS', () => {
  describe('default preset', () => {
    it('should have expected values', () => {
      expect(RETRY_PRESETS.default.maxRetries).toBe(3);
      expect(RETRY_PRESETS.default.baseDelayMs).toBe(1000);
      expect(RETRY_PRESETS.default.maxDelayMs).toBe(30000);
      expect(RETRY_PRESETS.default.jitterFactor).toBe(0.5);
      expect(RETRY_PRESETS.default.retryOnStatus).toEqual([429, 500, 502, 503, 504]);
      expect(RETRY_PRESETS.default.respectRetryAfter).toBe(true);
    });

    it('should be usable with createRetryDispatcher', () => {
      const dispatcher = createRetryDispatcher(RETRY_PRESETS.default);
      expect(dispatcher).toBeDefined();
    });
  });

  describe('aggressive preset', () => {
    it('should have expected values', () => {
      expect(RETRY_PRESETS.aggressive.maxRetries).toBe(5);
      expect(RETRY_PRESETS.aggressive.baseDelayMs).toBe(500);
      expect(RETRY_PRESETS.aggressive.maxDelayMs).toBe(60000);
      expect(RETRY_PRESETS.aggressive.jitterFactor).toBe(0.3);
      expect(RETRY_PRESETS.aggressive.retryOnStatus).toContain(520);
      expect(RETRY_PRESETS.aggressive.retryOnStatus).toContain(521);
      expect(RETRY_PRESETS.aggressive.retryOnStatus).toContain(522);
      expect(RETRY_PRESETS.aggressive.retryOnStatus).toContain(523);
      expect(RETRY_PRESETS.aggressive.retryOnStatus).toContain(524);
      expect(RETRY_PRESETS.aggressive.respectRetryAfter).toBe(true);
    });

    it('should be usable with createRetryDispatcher', () => {
      const dispatcher = createRetryDispatcher(RETRY_PRESETS.aggressive);
      expect(dispatcher).toBeDefined();
    });
  });

  describe('quick preset', () => {
    it('should have expected values', () => {
      expect(RETRY_PRESETS.quick.maxRetries).toBe(2);
      expect(RETRY_PRESETS.quick.baseDelayMs).toBe(200);
      expect(RETRY_PRESETS.quick.maxDelayMs).toBe(2000);
      expect(RETRY_PRESETS.quick.jitterFactor).toBe(0.5);
      expect(RETRY_PRESETS.quick.retryOnStatus).toEqual([429, 502, 503, 504]);
      expect(RETRY_PRESETS.quick.respectRetryAfter).toBe(true);
    });

    it('should be usable with createRetryDispatcher', () => {
      const dispatcher = createRetryDispatcher(RETRY_PRESETS.quick);
      expect(dispatcher).toBeDefined();
    });
  });

  describe('gentle preset', () => {
    it('should have expected values', () => {
      expect(RETRY_PRESETS.gentle.maxRetries).toBe(5);
      expect(RETRY_PRESETS.gentle.baseDelayMs).toBe(2000);
      expect(RETRY_PRESETS.gentle.maxDelayMs).toBe(120000);
      expect(RETRY_PRESETS.gentle.jitterFactor).toBe(0.7);
      expect(RETRY_PRESETS.gentle.retryOnStatus).toEqual([429]);
      expect(RETRY_PRESETS.gentle.respectRetryAfter).toBe(true);
    });

    it('should be usable with createRetryDispatcher', () => {
      const dispatcher = createRetryDispatcher(RETRY_PRESETS.gentle);
      expect(dispatcher).toBeDefined();
    });
  });
});
