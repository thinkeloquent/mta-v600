#!/usr/bin/env node
/**
 * Servicenow Health Check - Standalone debugging script
 */
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..');
const CONFIG_DIR = path.join(PROJECT_ROOT, 'common', 'config');

import { loadYamlConfig, config as staticConfig } from '@internal/app-static-config-yaml';
await loadYamlConfig({ configDir: CONFIG_DIR });

import { ServicenowApiToken } from '../../api_token/index.mjs'; // Warning: Must be exported first!
import { createClientWithDispatcher } from '@internal/fetch-client';

export async function checkServicenowHealth() {
    console.log('='.repeat(60));
    console.log('SERVICENOW HEALTH CHECK');
    console.log('='.repeat(60));

    const provider = new ServicenowApiToken(staticConfig);
    const apiKeyResult = provider.getApiKey();
    const networkConfig = provider.getNetworkConfig();
    const baseUrl = provider.getBaseUrl();

    console.log(`\n[Config]`);
    console.log(`  Base URL: ${baseUrl}`);
    console.log(`  Auth type: ${apiKeyResult.authType}`);

    if (!apiKeyResult.hasCredentials) {
        return { success: false, error: 'Missing credentials' };
    }

    const client = await createClientWithDispatcher({
        baseUrl,
        auth: {
            type: apiKeyResult.authType,
            rawApiKey: apiKeyResult.rawApiKey,
            headerName: apiKeyResult.headerName,
            username: apiKeyResult.email, // For basic auth,
        },
        headers: { 'Accept': 'application/json' },
        verify: networkConfig.certVerify,
        proxy: networkConfig.proxyUrl,
    });

    // Standard table API check
    const healthEndpoint = '/api/now/table/sys_user?sysparm_limit=1';

    try {
        const response = await client.get(healthEndpoint);
        return {
            success: response.ok,
            statusCode: response.status,
            data: response.data,
        };
    } catch (e) {
        return { success: false, error: e.message };
    } finally {
        if (client.close) await client.close();
    }
}

if (process.argv[1] === __filename) {
    const result = await checkServicenowHealth();
    console.log(JSON.stringify(result, null, 2));
}
