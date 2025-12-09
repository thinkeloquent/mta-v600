#!/usr/bin/env python3
"""
Gemini API (OpenAI Compatible) - httpx Connection Test

Authentication: Bearer Token
Base URL: https://generativelanguage.googleapis.com/v1beta/openai
Health Endpoint: GET /models

TLS/SSL Options:
  SSL_CERT_VERIFY=0              - Ignore all certificate errors
  REQUEST_CA_BUNDLE=/path/to/ca  - Custom CA bundle file
  SSL_CERT_FILE=/path/to/cert    - Custom SSL certificate file
  REQUESTS_CA_BUNDLE=/path/to/ca - Alternative CA bundle (requests compat)
"""

import asyncio
import json
import os
from typing import Any, AsyncGenerator, Union

import httpx

# ============================================================================
# Configuration - Override these values
# ============================================================================

CONFIG = {
    # Required
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", "your_gemini_api_key_here"),

    # Base URL
    "BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",

    # Optional: Proxy Configuration
    "HTTPS_PROXY": os.getenv("HTTPS_PROXY", ""),  # e.g., "http://proxy.example.com:8080"

    # Optional: TLS Configuration
    # Set to False to ignore certificate errors (default: False for testing)
    # SSL_CERT_VERIFY=0, REQUEST_CA_BUNDLE=null, SSL_CERT_FILE=null, REQUESTS_CA_BUNDLE=null
    "VERIFY_SSL": False,

    # Optional: Custom CA certificates (disabled by default for testing)
    "CA_BUNDLE": None,
}


# ============================================================================
# TLS Configuration Helper
# ============================================================================

def get_ssl_verify() -> Union[bool, str]:
    """Get SSL verification setting.

    Priority:
    1. Environment variables (NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0)
    2. Custom CA bundle from CONFIG
    3. CONFIG["VERIFY_SSL"] setting
    """
    # Check environment variables first
    node_tls = os.getenv("NODE_TLS_REJECT_UNAUTHORIZED", "")
    ssl_cert_verify = os.getenv("SSL_CERT_VERIFY", "")
    if node_tls == "0" or ssl_cert_verify == "0":
        print("SSL verification disabled via environment variable")
        return False

    if CONFIG["CA_BUNDLE"]:
        print(f"Using custom CA bundle: {CONFIG['CA_BUNDLE']}")
        return CONFIG["CA_BUNDLE"]
    return CONFIG["VERIFY_SSL"]


# ============================================================================
# Create HTTP Client
# ============================================================================

def create_client() -> httpx.AsyncClient:
    """Create httpx async client with optional proxy."""
    proxies = None
    if CONFIG["HTTPS_PROXY"]:
        print(f"Using proxy: {CONFIG['HTTPS_PROXY']}")
        proxies = {
            "http://": CONFIG["HTTPS_PROXY"],
            "https://": CONFIG["HTTPS_PROXY"],
        }

    return httpx.AsyncClient(
        proxies=proxies,
        verify=get_ssl_verify(),
        timeout=httpx.Timeout(60.0),
    )


# ============================================================================
# Health Check
# ============================================================================

async def health_check() -> dict[str, Any]:
    """Perform health check by listing models."""
    print("\n=== Gemini Health Check (List Models) ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/models",
                headers={
                    "Authorization": f"Bearer {CONFIG['GEMINI_API_KEY']}",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            models = data.get("data", [])
            print(f"Found {len(models)} models")
            for model in models[:5]:
                print(f"  - {model['id']}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Sample API Calls
# ============================================================================

async def chat_completion(messages: list[dict], model: str = "gemini-1.5-flash") -> dict[str, Any]:
    """Create a chat completion."""
    print(f"\n=== Chat Completion ({model}) ===\n")

    async with create_client() as client:
        try:
            response = await client.post(
                f"{CONFIG['BASE_URL']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {CONFIG['GEMINI_API_KEY']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")
                print(f"Response: {content}")
            else:
                print(f"Response: {json.dumps(data, indent=2)}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def stream_chat_completion(messages: list[dict], model: str = "gemini-1.5-flash") -> dict[str, Any]:
    """Create a streaming chat completion."""
    print(f"\n=== Streaming Chat Completion ({model}) ===\n")

    async with create_client() as client:
        try:
            async with client.stream(
                "POST",
                f"{CONFIG['BASE_URL']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {CONFIG['GEMINI_API_KEY']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                },
            ) as response:
                print(f"Status: {response.status_code}")
                print("Streaming response:")

                full_content = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            continue
                        try:
                            data = json.loads(data_str)
                            content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            full_content += content
                            print(content, end="", flush=True)
                        except json.JSONDecodeError:
                            pass

                print("\n")
                return {"success": response.status_code == 200, "content": full_content}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def create_embedding(input_text: str, model: str = "text-embedding-004") -> dict[str, Any]:
    """Create an embedding."""
    print(f"\n=== Create Embedding ({model}) ===\n")

    async with create_client() as client:
        try:
            response = await client.post(
                f"{CONFIG['BASE_URL']}/embeddings",
                headers={
                    "Authorization": f"Bearer {CONFIG['GEMINI_API_KEY']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": input_text,
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            if "data" in data and data["data"]:
                embedding = data["data"][0].get("embedding", [])
                print(f"Embedding dimensions: {len(embedding)}")
                print(f"First 5 values: {embedding[:5]}")
            else:
                print(f"Response: {json.dumps(data, indent=2)}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("Gemini API Connection Test (OpenAI Compatible)")
    print("==============================================")
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Proxy: {CONFIG['HTTPS_PROXY'] or 'None'}")
    print(f"API Key: {CONFIG['GEMINI_API_KEY'][:10]}...")
    print(f"SSL Verify: {CONFIG['VERIFY_SSL']}")
    print(f"CA Bundle: {CONFIG['CA_BUNDLE'] or 'System default'}")

    await health_check()

    # await chat_completion([
    #     {"role": "user", "content": "Hello, how are you?"}
    # ])

    # await stream_chat_completion([
    #     {"role": "user", "content": "Write a short poem about coding."}
    # ])

    # await create_embedding("The quick brown fox jumps over the lazy dog.")


if __name__ == "__main__":
    asyncio.run(main())
