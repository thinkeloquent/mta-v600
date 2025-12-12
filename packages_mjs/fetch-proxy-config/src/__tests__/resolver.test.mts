
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { resolveProxyUrl } from '../resolver.mjs';

describe('resolveProxyUrl', () => {
    const originalEnv = process.env;

    beforeEach(() => {
        vi.resetModules();
        process.env = { ...originalEnv };
    });

    afterEach(() => {
        process.env = originalEnv;
    });

    it('prioritizes direct override', () => {
        const config = {};
        const result = resolveProxyUrl(config, 'http://override:8080');
        expect(result).toBe('http://override:8080');
    });

    it('uses config for default environment', () => {
        const config = {
            default_environment: 'QA',
            proxy_urls: { QA: 'http://qa-proxy:8080' }
        };
        const result = resolveProxyUrl(config);
        expect(result).toBe('http://qa-proxy:8080');
    });

    it('prioritizes specific env var if config missing', () => {
        process.env.PROXY_URL = 'http://env-proxy:8080';
        const config = {};
        const result = resolveProxyUrl(config);
        expect(result).toBe('http://env-proxy:8080');
    });

    it('fallbacks to generic env vars', () => {
        process.env.HTTPS_PROXY = 'http://https-proxy:8080';
        const config = {};
        const result = resolveProxyUrl(config);
        expect(result).toBe('http://https-proxy:8080');
    });
});
