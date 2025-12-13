/**
 * ServiceNow API token getter.
 */
import { BaseApiToken, ApiKeyResult, maskSensitive } from './base.mjs';

// Simple logger
const logger = {
    debug: (msg) => console.debug(`[DEBUG] provider_api_getters.servicenow: ${msg}`),
    warn: (msg) => console.warn(`[WARN] provider_api_getters.servicenow: ${msg}`),
};

// Default environment variables
const DEFAULT_SERVICENOW_PASSWORD_ENV = 'SERVICENOW_PASSWORD';
const DEFAULT_SERVICENOW_USERNAME_ENV = 'SERVICENOW_USERNAME';
const DEFAULT_SERVICENOW_INSTANCE_ENV = 'SERVICENOW_INSTANCE';

export class ServicenowApiToken extends BaseApiToken {
    get providerName() {
        return 'servicenow';
    }

    get healthEndpoint() {
        // Standard table API check
        return '/api/now/table/sys_user?sysparm_limit=1';
    }

    getBaseUrl() {
        logger.debug('ServicenowApiToken.getBaseUrl: Getting base URL');

        // Try config first
        let baseUrl = super.getBaseUrl();

        // If not in config, try constructing from instance name env var
        if (!baseUrl) {
            const instance = process.env[DEFAULT_SERVICENOW_INSTANCE_ENV];
            if (instance) {
                baseUrl = `https://${instance}.service-now.com`;
                logger.debug(`Constructed base URL from instance: ${baseUrl}`);
            }
        }

        return baseUrl;
    }

    getApiKey() {
        logger.debug('ServicenowApiToken.getApiKey: Starting resolution');

        // Get password (api key)
        let password = this._lookupEnvApiKey();
        if (!password) {
            password = process.env[DEFAULT_SERVICENOW_PASSWORD_ENV];
        }

        // Get username from config or env
        const providerConfig = this._getProviderConfig();
        const username = providerConfig?.username || process.env[DEFAULT_SERVICENOW_USERNAME_ENV];

        if (password && username) {
            const result = new ApiKeyResult({
                apiKey: password,
                authType: 'basic',
                headerName: 'Authorization',
                email: username, // storing username in email field for basic auth
                rawApiKey: password,
            });
            return result;
        }

        logger.warn('ServiceNow credentials incomplete (need username and password)');
        return new ApiKeyResult({
            apiKey: null,
            authType: 'basic',
            headerName: 'Authorization',
            email: null,
            rawApiKey: null,
        });
    }
}
