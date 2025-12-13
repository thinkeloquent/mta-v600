#!/usr/bin/env node
/**
 * {{APP_NAME_TITLE}} Health Check - Standalone debugging script
 */
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..', '..', '..');
const CONFIG_DIR = path.join(PROJECT_ROOT, 'common', 'config');

import { loadYamlConfig, config as staticConfig } from '@internal/app-static-config-yaml';
await loadYamlConfig({ configDir: CONFIG_DIR });

import { {{ APP_NAME_PASCAL }}ApiToken } from '../../api_token/index.mjs'; // Warning: Must be exported first!
import { createClientWithDispatcher } from '@internal/fetch-client';

export async function check{ { APP_NAME_PASCAL } } Health() {
    console.log('='.repeat(60));
    console.log('{{APP_NAME_UPPER_SNAKE}} HEALTH CHECK');
    console.log('='.repeat(60));

    const provider = new {{ APP_NAME_PASCAL }
} ApiToken(staticConfig);
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
    },
    headers: { 'Accept': 'application/json' },
    verify: networkConfig.certVerify,
    proxy: networkConfig.proxyUrl,
});

// TODO: Update with correct health endpoint
const healthEndpoint = '/health/status'; // REPLACE THIS

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
    const result = await check{{ APP_NAME_PASCAL }
} Health();
console.log(JSON.stringify(result, null, 2));
}
