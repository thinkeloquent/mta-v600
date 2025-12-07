/**
 * DNS warmup utilities for @internal/fetch-client
 *
 * Pre-resolves hostnames to populate DNS cache and reduce first-request latency.
 */
import dns from 'node:dns/promises';

/**
 * DNS warmup result
 */
export interface DnsWarmupResult {
  hostname: string;
  addresses: string[];
  duration: number;
  success: boolean;
  error?: Error;
}

/**
 * Warm up DNS for a single hostname
 *
 * @param hostname - The hostname to resolve
 * @returns Promise resolving to warmup result
 */
export async function warmupDns(hostname: string): Promise<DnsWarmupResult> {
  const start = Date.now();

  try {
    const addresses = await dns.lookup(hostname, { all: true });
    const duration = Date.now() - start;

    return {
      hostname,
      addresses: addresses.map((a) => a.address),
      duration,
      success: true,
    };
  } catch (error) {
    const duration = Date.now() - start;

    return {
      hostname,
      addresses: [],
      duration,
      success: false,
      error: error instanceof Error ? error : new Error(String(error)),
    };
  }
}

/**
 * Warm up DNS for multiple hostnames in parallel
 *
 * @param hostnames - Array of hostnames to resolve
 * @returns Promise resolving to array of warmup results
 */
export async function warmupDnsMany(hostnames: string[]): Promise<DnsWarmupResult[]> {
  return Promise.all(hostnames.map(warmupDns));
}

/**
 * Extract hostname from URL
 *
 * @param url - URL string or URL object
 * @returns Hostname string
 */
export function extractHostname(url: string | URL): string {
  const urlObj = typeof url === 'string' ? new URL(url) : url;
  return urlObj.hostname;
}

/**
 * Warm up DNS for a URL
 *
 * @param url - URL string or URL object
 * @returns Promise resolving to warmup result
 */
export async function warmupDnsForUrl(url: string | URL): Promise<DnsWarmupResult> {
  const hostname = extractHostname(url);
  return warmupDns(hostname);
}
