import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
    debug: (msg) => console.debug(`[DEBUG] provider_api_getters.statsig: ${msg} `),
    warn: (msg) => console.warn(`[WARN] provider_api_getters.statsig: ${msg} `),
};

// Default environment variable for Statsig API key
const DEFAULT_STATSIG_API_KEY_ENV = 'STATSIG_API_KEY';

export class StatsigApiToken extends BaseApiToken {
    get providerName() {
        return 'statsig';
    }

    get healthEndpoint() {
        // Using /gates to verify connectivity and auth
        return '/gates';
    }

    getBaseUrl() {
        logger.debug('StatsigApiToken.getBaseUrl: Getting base URL');

        // Try config first
        let baseUrl = super.getBaseUrl();

        // Default if not configured
        if (!baseUrl) {
            baseUrl = 'https://statsigapi.net/console/v1';
            logger.debug(`Using default base URL: ${baseUrl} `);
        }

        return baseUrl;
    }

    getApiKey() {
        logger.debug('StatsigApiToken.getApiKey: Starting resolution');

        // Get API key from env
        let apiKey = this._lookupEnvApiKey();
        if (!apiKey) {
            apiKey = process.env[DEFAULT_STATSIG_API_KEY_ENV];
        }

        if (apiKey) {
            logger.debug(
                `StatsigApiToken.getApiKey: Found API key(length = ${apiKey.length}, masked = ${maskSensitive(apiKey)})`
            );
            return new ApiKeyResult({
                apiKey: apiKey,
                authType: 'custom_header',
                headerName: 'statsig-api-key',
                rawApiKey: apiKey,
            });
        }

        logger.warn('No API key found for Statsig');
        return new ApiKeyResult({
            apiKey: null,
            authType: 'custom_header',
            headerName: 'statsig-api-key',
            rawApiKey: null,
            isPlaceholder: false,
        });
    }
}
