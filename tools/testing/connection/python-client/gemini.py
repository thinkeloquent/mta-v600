#!/usr/bin/env python3
"""
Gemini API (OpenAI Compatible) - Python Client Integration Test

Authentication: Bearer Token
Base URL: https://generativelanguage.googleapis.com/v1beta/openai
Health Endpoint: GET /models

Uses internal packages:
  - fetch_proxy_dispatcher: Environment-aware proxy configuration
  - fetch_client: HTTP client with auth support
  - provider_api_getters: API key resolution
  - app_static_config_yaml: YAML configuration loading
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# ============================================================================
# Project Setup - Add packages to path
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "app_static_config_yaml" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "provider_api_getters" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "fetch_client" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "fetch_proxy_dispatcher" / "src"))

# Load static config
from static_config import load_yaml_config, config as static_config
CONFIG_DIR = PROJECT_ROOT / "common" / "config"
load_yaml_config(config_dir=str(CONFIG_DIR))

# Import internal packages
from fetch_proxy_dispatcher import get_proxy_dispatcher
from fetch_client import create_client_with_dispatcher, AuthConfig
from provider_api_getters import GeminiOpenAIApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = GeminiOpenAIApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters
    "GEMINI_API_KEY": api_key_result.api_key,
    "AUTH_TYPE": api_key_result.auth_type,

    # Base URL (from provider or override)
    "BASE_URL": provider.get_base_url() or "https://generativelanguage.googleapis.com/v1beta/openai",

    # SSL/TLS Configuration (runtime override, or use YAML config)
    "SSL_VERIFY": False,  # Set to None to use YAML config
    "CERT": os.getenv("CERT"),  # Client certificate path
    "CA_BUNDLE": os.getenv("CA_BUNDLE"),  # CA bundle path

    # Proxy Configuration
    "PROXY": os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"),

    # Debug
    "DEBUG": os.getenv("DEBUG", "true").lower() not in ("false", "0"),
}


# ============================================================================
# Health Check
# ============================================================================
async def health_check() -> dict[str, Any]:
    """Health check using ProviderHealthChecker."""
    print("\n=== Gemini Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("gemini")

    print(f"Status: {result.status}")
    if result.latency_ms:
        print(f"Latency: {result.latency_ms:.2f}ms")
    if result.message:
        print(f"Message: {result.message}")
    if result.error:
        print(f"Error: {result.error}")

    return {"success": result.status == "connected", "result": result}


# ============================================================================
# Client Factory
# ============================================================================
def create_gemini_client():
    """Create Gemini client with standard config."""
    return create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="bearer", raw_api_key=CONFIG["GEMINI_API_KEY"]),
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )


# ============================================================================
# Sample API Calls using fetch_client
# ============================================================================
async def chat_completion(messages: list[dict], model: str = "gemini-1.5-flash") -> dict[str, Any]:
    """Chat completion using fetch_client."""
    print(f"\n=== Chat Completion ({model}) ===\n")

    client = create_gemini_client()

    async with client:
        response = await client.post(
            "/chat/completions",
            json={"model": model, "messages": messages},
        )

        print(f"Status: {response['status']}")
        if response["ok"] and "choices" in response["data"]:
            content = response["data"]["choices"][0].get("message", {}).get("content", "")
            print(f"Response: {content}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def stream_chat_completion(messages: list[dict], model: str = "gemini-1.5-flash") -> dict[str, Any]:
    """Streaming chat completion using fetch_client SSE support."""
    print(f"\n=== Streaming Chat Completion ({model}) ===\n")

    client = create_gemini_client()

    full_content = ""
    async with client:
        async for event in client.stream(
            "/chat/completions",
            method="POST",
            json={"model": model, "messages": messages, "stream": True},
        ):
            if event.data == "[DONE]":
                continue
            try:
                data = json.loads(event.data)
                content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                full_content += content
                print(content, end="", flush=True)
            except json.JSONDecodeError:
                pass

    print("\n")
    return {"success": True, "content": full_content}


async def create_embedding(input_text: str, model: str = "text-embedding-004") -> dict[str, Any]:
    """Create embedding using fetch_client."""
    print(f"\n=== Create Embedding ({model}) ===\n")

    client = create_gemini_client()

    async with client:
        response = await client.post(
            "/embeddings",
            json={"model": model, "input": input_text},
        )

        print(f"Status: {response['status']}")
        if response["ok"] and "data" in response["data"]:
            embedding = response["data"]["data"][0].get("embedding", [])
            print(f"Embedding dimensions: {len(embedding)}")
            print(f"First 5 values: {embedding[:5]}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("Gemini API Connection Test (Python Client Integration)")
    print("=" * 55)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"API Key: {CONFIG['GEMINI_API_KEY'][:10]}..." if CONFIG['GEMINI_API_KEY'] else "API Key: Not set")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await chat_completion([{"role": "user", "content": "Hello, how are you?"}])
    # await stream_chat_completion([{"role": "user", "content": "Write a short poem about coding."}])
    # await create_embedding("The quick brown fox jumps over the lazy dog.")


if __name__ == "__main__":
    asyncio.run(main())
