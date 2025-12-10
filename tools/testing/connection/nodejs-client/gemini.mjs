#!/usr/bin/env node
/**
 * Gemini API (OpenAI Compatible) - Node.js Client Integration Test
 *
 * Authentication: Bearer Token
 * Base URL: https://generativelanguage.googleapis.com/v1beta/openai
 * Health Endpoint: GET /models
 *
 * Uses internal packages:
 *   - @internal/fetch-proxy-dispatcher: Environment-aware proxy configuration
 *   - @internal/fetch-client: HTTP client with auth support
 *   - @internal/provider_api_getters: API key resolution
 *   - @internal/app-static-config-yaml: YAML configuration loading
 */
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

// ============================================================================
// Project Setup
// ============================================================================
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..', '..');

// Load static config
const { loadYamlConfig, config: staticConfig } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'app-static-config-yaml', 'src', 'index.mjs')
);
const configDir = resolve(PROJECT_ROOT, 'common', 'config');
await loadYamlConfig({ configDir });

// Import internal packages
const { getProxyDispatcher } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'fetch-proxy-dispatcher', 'src', 'index.mts')
);
const { createClient } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'fetch-client', 'src', 'index.mts')
);
const { GeminiOpenAIApiToken, ProviderHealthChecker } = await import(
  resolve(PROJECT_ROOT, 'packages_mjs', 'provider_api_getters', 'src', 'index.mjs')
);

// ============================================================================
// Configuration - Exposed for debugging
// ============================================================================
const provider = new GeminiOpenAIApiToken(staticConfig);
const apiKeyResult = provider.getApiKey();

const CONFIG = {
  // From provider_api_getters
  GEMINI_API_KEY: apiKeyResult.apiKey,
  AUTH_TYPE: apiKeyResult.authType,

  // Base URL (from provider or override)
  BASE_URL: provider.getBaseUrl() || 'https://generativelanguage.googleapis.com/v1beta/openai',

  // Dispatcher (from fetch-proxy-dispatcher)
  DISPATCHER: getProxyDispatcher(),

  // Proxy Configuration (set to override YAML/environment config)
  PROXY: process.env.HTTPS_PROXY || process.env.HTTP_PROXY || undefined,

  // SSL/TLS Configuration (runtime override, or undefined to use YAML config)
  SSL_VERIFY: false,  // Set to undefined to use YAML config

  // Debug
  DEBUG: !['false', '0'].includes((process.env.DEBUG || '').toLowerCase()),
};

// ============================================================================
// Health Check
// ============================================================================
async function healthCheck() {
  console.log('\n=== Gemini Health Check (ProviderHealthChecker) ===\n');

  const checker = new ProviderHealthChecker(staticConfig);
  const result = await checker.check('gemini');

  console.log(`Status: ${result.status}`);
  if (result.latency_ms) console.log(`Latency: ${result.latency_ms.toFixed(2)}ms`);
  if (result.message) console.log(`Message: ${result.message}`);
  if (result.error) console.log(`Error: ${result.error}`);

  return { success: result.status === 'connected', result };
}

// ============================================================================
// Client Factory
// ============================================================================
function createGeminiClient() {
  return createClient({
    baseUrl: CONFIG.BASE_URL,
    dispatcher: CONFIG.DISPATCHER,
    auth: {
      type: 'bearer',
      rawApiKey: CONFIG.GEMINI_API_KEY,
    },
    proxy: CONFIG.PROXY,
    verify: CONFIG.SSL_VERIFY,
  });
}

// ============================================================================
// Sample API Calls using fetch-client
// ============================================================================
async function chatCompletion(messages, model = 'gemini-1.5-flash') {
  console.log(`\n=== Chat Completion (${model}) ===\n`);

  const client = createGeminiClient();

  try {
    const response = await client.post('/chat/completions', {
      json: { model, messages },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok && response.data?.choices?.[0]?.message?.content) {
      console.log('Response:', response.data.choices[0].message.content);
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

async function streamChatCompletion(messages, model = 'gemini-1.5-flash') {
  console.log(`\n=== Streaming Chat Completion (${model}) ===\n`);

  const client = createGeminiClient();

  let fullContent = '';
  try {
    for await (const event of client.stream('/chat/completions', {
      method: 'POST',
      json: { model, messages, stream: true },
    })) {
      if (event.data === '[DONE]') continue;
      try {
        const data = JSON.parse(event.data);
        const content = data.choices?.[0]?.delta?.content || '';
        fullContent += content;
        process.stdout.write(content);
      } catch {
        // Ignore parse errors
      }
    }
    console.log('\n');
    return { success: true, content: fullContent };
  } finally {
    await client.close();
  }
}

async function createEmbedding(input, model = 'text-embedding-004') {
  console.log(`\n=== Create Embedding (${model}) ===\n`);

  const client = createGeminiClient();

  try {
    const response = await client.post('/embeddings', {
      json: { model, input },
    });

    console.log(`Status: ${response.status}`);
    if (response.ok && response.data?.data?.[0]?.embedding) {
      const embedding = response.data.data[0].embedding;
      console.log(`Embedding dimensions: ${embedding.length}`);
      console.log(`First 5 values: ${embedding.slice(0, 5).join(', ')}`);
    } else {
      console.log('Response:', JSON.stringify(response.data, null, 2));
    }

    return { success: response.ok, data: response.data };
  } finally {
    await client.close();
  }
}

// ============================================================================
// Run Tests
// ============================================================================
async function main() {
  console.log('Gemini API Connection Test (Node.js Client Integration)');
  console.log('='.repeat(55));
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`API Key: ${CONFIG.GEMINI_API_KEY ? CONFIG.GEMINI_API_KEY.slice(0, 10) + '...' : 'Not set'}`);
  console.log(`Auth Type: ${CONFIG.AUTH_TYPE}`);
  console.log(`Debug: ${CONFIG.DEBUG}`);

  await healthCheck();

  // Uncomment to run additional tests:
  // await chatCompletion([{ role: 'user', content: 'Hello, how are you?' }]);
  // await streamChatCompletion([{ role: 'user', content: 'Write a short poem about coding.' }]);
  // await createEmbedding('The quick brown fox jumps over the lazy dog.');
}

main().catch(console.error);
