#!/usr/bin/env python3
"""
Gemini/OpenAI Health Check - Standalone debugging script

Run directly: python gemini_openai_health_check.py

This checks the Gemini API using OpenAI-compatible endpoints.

Uses:
- static_config for YAML configuration
- GeminiOpenAIApiToken for API token resolution
- fetch_client for HTTP requests with proxy/auth support
"""
import asyncio
import json
from pathlib import Path

# ============================================================
# Load static config FIRST
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "common" / "config"

from static_config import load_yaml_config, config as static_config
load_yaml_config(config_dir=str(CONFIG_DIR))

# ============================================================
# Provider API getter
# ============================================================
from provider_api_getters import GeminiOpenAIApiToken

# ============================================================
# Fetch client with dispatcher
# ============================================================
from fetch_client import create_client_with_dispatcher, AuthConfig


async def check_gemini_openai_health() -> dict:
    """
    Check Gemini/OpenAI API connectivity and return status.

    Returns:
        dict: Health check result with success status and data/error
    """
    print("=" * 60)
    print("GEMINI/OPENAI HEALTH CHECK")
    print("=" * 60)

    # Initialize provider from static config
    provider = GeminiOpenAIApiToken(static_config)
    api_key_result = provider.get_api_key()
    network_config = provider.get_network_config()
    base_url = provider.get_base_url()

    # Debug output
    print(f"\n[Config]")
    print(f"  Base URL: {base_url}")
    print(f"  Has credentials: {api_key_result.has_credentials}")
    print(f"  Is placeholder: {api_key_result.is_placeholder}")
    print(f"  Auth type: {api_key_result.auth_type}")
    print(f"  Header name: {api_key_result.header_name}")
    print(f"\n[Network Config]")
    print(f"  Proxy URL: {network_config.get('proxy_url') or 'None'}")
    print(f"  Cert verify: {network_config.get('cert_verify')}")

    if not api_key_result.has_credentials or api_key_result.is_placeholder:
        print("\n[ERROR] Missing or placeholder credentials")
        return {"success": False, "error": "Missing credentials"}

    if not base_url:
        print("\n[ERROR] No base URL configured")
        return {"success": False, "error": "No base URL"}

    # Create client with dispatcher (handles proxy, SSL, auth)
    print(f"\n[Creating Client]")
    print(f"  Auth type: {api_key_result.auth_type}")

    client = create_client_with_dispatcher(
        base_url=base_url,
        auth=AuthConfig(
            type=api_key_result.auth_type,
            raw_api_key=api_key_result.api_key,
            header_name=api_key_result.header_name,
        ),
        default_headers={
            "Accept": "application/json",
        },
        verify=network_config.get("cert_verify"),
        proxy=network_config.get("proxy_url"),
    )

    # Make health check request - list models
    health_endpoint = "/models"
    print(f"\n[Request]")
    print(f"  GET {base_url}{health_endpoint}")

    async with client:
        response = await client.get(health_endpoint)

        print(f"\n[Response]")
        print(f"  Status: {response['status']}")
        print(f"  OK: {response['ok']}")

        if response["ok"]:
            data = response["data"]
            models = data.get("data", data.get("models", []))
            model_count = len(models)

            print(f"\n[Models Info]")
            print(f"  Total models: {model_count}")

            # List first 5 models
            if models:
                print(f"  First 5 models:")
                for i, model in enumerate(models[:5]):
                    model_id = model.get("id", model.get("name", "N/A"))
                    print(f"    - {model_id}")

            return {
                "success": True,
                "message": f"Connected, {model_count} models available",
                "data": {
                    "model_count": model_count,
                    "sample_models": [
                        m.get("id", m.get("name", "N/A")) for m in models[:5]
                    ],
                },
            }
        else:
            print(f"\n[Error Response]")
            print(json.dumps(response["data"], indent=2))
            return {
                "success": False,
                "status_code": response["status"],
                "error": response["data"],
            }


if __name__ == "__main__":
    print("\n")
    result = asyncio.run(check_gemini_openai_health())
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
