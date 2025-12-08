/**
 * Gemini API (OpenAI Compatible) - undici Connection Test
 *
 * Authentication: Bearer Token
 * Base URL: https://generativelanguage.googleapis.com/v1beta/openai
 * Health Endpoint: GET /models
 */

import { request, ProxyAgent, Agent } from 'undici';

// ============================================================================
// Configuration - Override these values
// ============================================================================

const CONFIG = {
  // Required
  GEMINI_API_KEY: process.env.GEMINI_API_KEY || 'your_gemini_api_key_here',

  // Base URL
  BASE_URL: 'https://generativelanguage.googleapis.com/v1beta/openai',

  // Optional: Proxy Configuration
  HTTPS_PROXY: process.env.HTTPS_PROXY || '', // e.g., 'http://proxy.example.com:8080'

  // Optional: TLS Configuration
  REJECT_UNAUTHORIZED: true, // Set to false to skip TLS verification (testing only)
};

// ============================================================================
// Create Dispatcher (with or without proxy)
// ============================================================================

function createDispatcher() {
  if (CONFIG.HTTPS_PROXY) {
    console.log(`Using proxy: ${CONFIG.HTTPS_PROXY}`);
    return new ProxyAgent({
      uri: CONFIG.HTTPS_PROXY,
      connect: {
        rejectUnauthorized: CONFIG.REJECT_UNAUTHORIZED,
      },
    });
  }
  return new Agent({
    connect: {
      rejectUnauthorized: CONFIG.REJECT_UNAUTHORIZED,
    },
  });
}

// ============================================================================
// Health Check
// ============================================================================

async function healthCheck() {
  console.log('\n=== Gemini Health Check (List Models) ===\n');

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/models`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${CONFIG.GEMINI_API_KEY}`,
      },
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    console.log(`Found ${data.data?.length || 0} models`);
    data.data?.slice(0, 5).forEach((model) => {
      console.log(`  - ${model.id}`);
    });

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

// ============================================================================
// Sample API Calls
// ============================================================================

async function chatCompletion(messages, model = 'gemini-1.5-flash') {
  console.log(`\n=== Chat Completion (${model}) ===\n`);

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${CONFIG.GEMINI_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        messages,
      }),
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    if (data.choices?.[0]?.message?.content) {
      console.log('Response:', data.choices[0].message.content);
    } else {
      console.log('Response:', JSON.stringify(data, null, 2));
    }

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function streamChatCompletion(messages, model = 'gemini-1.5-flash') {
  console.log(`\n=== Streaming Chat Completion (${model}) ===\n`);

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${CONFIG.GEMINI_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        messages,
        stream: true,
      }),
      dispatcher,
    });

    console.log(`Status: ${response.statusCode}`);
    console.log('Streaming response:');

    let fullContent = '';
    for await (const chunk of response.body) {
      const text = chunk.toString();
      const lines = text.split('\n').filter((line) => line.startsWith('data: '));

      for (const line of lines) {
        const data = line.slice(6);
        if (data === '[DONE]') continue;

        try {
          const parsed = JSON.parse(data);
          const content = parsed.choices?.[0]?.delta?.content || '';
          fullContent += content;
          process.stdout.write(content);
        } catch {
          // Ignore parse errors
        }
      }
    }
    console.log('\n');

    return { success: response.statusCode === 200, content: fullContent };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

async function createEmbedding(input, model = 'text-embedding-004') {
  console.log(`\n=== Create Embedding (${model}) ===\n`);

  const dispatcher = createDispatcher();

  try {
    const response = await request(`${CONFIG.BASE_URL}/embeddings`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${CONFIG.GEMINI_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        input,
      }),
      dispatcher,
    });

    const data = await response.body.json();

    console.log(`Status: ${response.statusCode}`);
    if (data.data?.[0]?.embedding) {
      console.log(`Embedding dimensions: ${data.data[0].embedding.length}`);
      console.log(`First 5 values: ${data.data[0].embedding.slice(0, 5).join(', ')}`);
    } else {
      console.log('Response:', JSON.stringify(data, null, 2));
    }

    return { success: response.statusCode === 200, data };
  } catch (error) {
    console.error('Error:', error.message);
    return { success: false, error: error.message };
  } finally {
    await dispatcher.close();
  }
}

// ============================================================================
// Run Tests
// ============================================================================

async function main() {
  console.log('Gemini API Connection Test (OpenAI Compatible)');
  console.log('==============================================');
  console.log(`Base URL: ${CONFIG.BASE_URL}`);
  console.log(`Proxy: ${CONFIG.HTTPS_PROXY || 'None'}`);
  console.log(`API Key: ${CONFIG.GEMINI_API_KEY.slice(0, 10)}...`);

  await healthCheck();

  // await chatCompletion([
  //   { role: 'user', content: 'Hello, how are you?' }
  // ]);

  // await streamChatCompletion([
  //   { role: 'user', content: 'Write a short poem about coding.' }
  // ]);

  // await createEmbedding('The quick brown fox jumps over the lazy dog.');
}

main().catch(console.error);
