/**
 * Tests for dns-warmup.mts
 * Logic testing: Happy Path, Error Path, Path coverage
 */
import {
  warmupDns,
  warmupDnsMany,
  extractHostname,
  warmupDnsForUrl,
} from '../src/dns-warmup.mjs';

// Mock dns module
jest.mock('node:dns/promises', () => ({
  lookup: jest.fn(),
}));

import dns from 'node:dns/promises';
const mockedDns = dns as jest.Mocked<typeof dns>;

describe('dns-warmup', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('warmupDns', () => {
    // Happy Path: successful resolution
    it('should return success result with addresses', async () => {
      mockedDns.lookup.mockResolvedValue([
        { address: '192.168.1.1', family: 4 },
        { address: '192.168.1.2', family: 4 },
      ] as any);

      const result = await warmupDns('api.example.com');

      expect(result.success).toBe(true);
      expect(result.hostname).toBe('api.example.com');
      expect(result.addresses).toEqual(['192.168.1.1', '192.168.1.2']);
      expect(result.error).toBeUndefined();
    });

    // Path: measures duration
    it('should measure duration', async () => {
      mockedDns.lookup.mockResolvedValue([{ address: '127.0.0.1', family: 4 }] as any);

      const result = await warmupDns('localhost');

      expect(typeof result.duration).toBe('number');
      expect(result.duration).toBeGreaterThanOrEqual(0);
    });

    // Error Path: DNS resolution failure
    it('should return failure result on DNS error', async () => {
      mockedDns.lookup.mockRejectedValue(new Error('ENOTFOUND'));

      const result = await warmupDns('nonexistent.invalid');

      expect(result.success).toBe(false);
      expect(result.addresses).toEqual([]);
      expect(result.error).toBeInstanceOf(Error);
      expect(result.error?.message).toBe('ENOTFOUND');
    });

    // Error Path: non-Error thrown
    it('should wrap non-Error exceptions', async () => {
      mockedDns.lookup.mockRejectedValue('string error');

      const result = await warmupDns('api.example.com');

      expect(result.success).toBe(false);
      expect(result.error).toBeInstanceOf(Error);
      expect(result.error?.message).toBe('string error');
    });

    // Path: calls dns.lookup with all: true
    it('should request all addresses', async () => {
      mockedDns.lookup.mockResolvedValue([{ address: '127.0.0.1', family: 4 }] as any);

      await warmupDns('localhost');

      expect(mockedDns.lookup).toHaveBeenCalledWith('localhost', { all: true });
    });

    // Path: duration is measured on failure too
    it('should measure duration on failure', async () => {
      mockedDns.lookup.mockRejectedValue(new Error('timeout'));

      const result = await warmupDns('slow.example.com');

      expect(typeof result.duration).toBe('number');
      expect(result.duration).toBeGreaterThanOrEqual(0);
    });
  });

  describe('warmupDnsMany', () => {
    // Path: multiple hostnames resolved in parallel
    it('should resolve multiple hostnames', async () => {
      mockedDns.lookup
        .mockResolvedValueOnce([{ address: '1.1.1.1', family: 4 }] as any)
        .mockResolvedValueOnce([{ address: '2.2.2.2', family: 4 }] as any);

      const results = await warmupDnsMany(['host1.com', 'host2.com']);

      expect(results).toHaveLength(2);
      expect(results[0].hostname).toBe('host1.com');
      expect(results[1].hostname).toBe('host2.com');
    });

    // Error Path: partial failure
    it('should handle partial failures', async () => {
      mockedDns.lookup
        .mockResolvedValueOnce([{ address: '1.1.1.1', family: 4 }] as any)
        .mockRejectedValueOnce(new Error('ENOTFOUND'));

      const results = await warmupDnsMany(['good.com', 'bad.invalid']);

      expect(results[0].success).toBe(true);
      expect(results[1].success).toBe(false);
    });

    // Boundary: empty array
    it('should handle empty array', async () => {
      const results = await warmupDnsMany([]);

      expect(results).toEqual([]);
    });

    // Path: single hostname
    it('should handle single hostname', async () => {
      mockedDns.lookup.mockResolvedValue([{ address: '1.1.1.1', family: 4 }] as any);

      const results = await warmupDnsMany(['single.com']);

      expect(results).toHaveLength(1);
      expect(results[0].hostname).toBe('single.com');
    });
  });

  describe('extractHostname', () => {
    // Decision: string URL
    it('should extract hostname from string URL', () => {
      expect(extractHostname('https://api.example.com/path')).toBe('api.example.com');
    });

    // Decision: URL object
    it('should extract hostname from URL object', () => {
      const url = new URL('https://api.example.com/path');
      expect(extractHostname(url)).toBe('api.example.com');
    });

    // Path: URL with port
    it('should extract hostname without port', () => {
      expect(extractHostname('https://api.example.com:8080/path')).toBe('api.example.com');
    });

    // Path: URL with subdomain
    it('should handle subdomains', () => {
      expect(extractHostname('https://sub.api.example.com')).toBe('sub.api.example.com');
    });

    // Path: localhost
    it('should handle localhost', () => {
      expect(extractHostname('http://localhost:3000')).toBe('localhost');
    });

    // Error Path: invalid URL throws
    it('should throw for invalid URL', () => {
      expect(() => extractHostname('not-a-url')).toThrow();
    });
  });

  describe('warmupDnsForUrl', () => {
    // Path: integration of extract + warmup
    it('should warm up DNS for URL string', async () => {
      mockedDns.lookup.mockResolvedValue([{ address: '93.184.216.34', family: 4 }] as any);

      const result = await warmupDnsForUrl('https://example.com/api/users');

      expect(result.hostname).toBe('example.com');
      expect(result.success).toBe(true);
    });

    // Path: URL object input
    it('should warm up DNS for URL object', async () => {
      mockedDns.lookup.mockResolvedValue([{ address: '93.184.216.34', family: 4 }] as any);

      const url = new URL('https://example.com/api');
      const result = await warmupDnsForUrl(url);

      expect(result.hostname).toBe('example.com');
    });

    // Error Path: DNS failure propagates
    it('should propagate DNS errors', async () => {
      mockedDns.lookup.mockRejectedValue(new Error('ENOTFOUND'));

      const result = await warmupDnsForUrl('https://nonexistent.invalid');

      expect(result.success).toBe(false);
    });
  });
});
