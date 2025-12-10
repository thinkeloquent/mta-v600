#!/usr/bin/env python3
"""
Figma Health Check - Standalone debugging script

Run directly: python figma_health_check.py

Uses:
- static_config for YAML configuration
- FigmaApiToken for API token resolution
- fetch_client for HTTP requests with proxy/auth support
"""
import asyncio
import json
from pathlib import Path

# ============================================================
# Provider API getter (relative import to avoid circular dependency)
# ============================================================
from ...api_token import FigmaApiToken

# ============================================================
# Fetch client with dispatcher
# ============================================================
from fetch_client import create_client_with_dispatcher, AuthConfig


async def check_figma_health(config: dict = None) -> dict:
    """
    Check Figma connectivity and return status.

    Args:
        config: Configuration dict (if None, loads from static_config)

    Returns:
        dict: Health check result with success status and data/error
    """
    # Load config if not provided
    if config is None:
        from static_config import config as static_config
        config = static_config

    print("=" * 60)
    print("FIGMA HEALTH CHECK")
    print("=" * 60)

    # Initialize provider from config
    provider = FigmaApiToken(config)
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

    # Make health check request
    health_endpoint = "/v1/me"
    print(f"\n[Request]")
    print(f"  GET {base_url}{health_endpoint}")

    async with client:
        response = await client.get(health_endpoint)

        print(f"\n[Response]")
        print(f"  Status: {response['status']}")
        print(f"  OK: {response['ok']}")

        if response["ok"]:
            data = response["data"]
            user_id = data.get("id", "N/A")
            handle = data.get("handle", "N/A")
            email = data.get("email", "N/A")
            img_url = data.get("img_url", "N/A")

            print(f"\n[User Info]")
            print(f"  User ID: {user_id}")
            print(f"  Handle: {handle}")
            print(f"  Email: {email}")
            print(f"  Avatar: {img_url}")

            return {
                "success": True,
                "message": f"Connected as {handle}",
                "data": {
                    "id": user_id,
                    "handle": handle,
                    "email": email,
                    "img_url": img_url,
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
    # Load config when run directly as standalone script
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
    CONFIG_DIR = PROJECT_ROOT / "common" / "config"

    from static_config import load_yaml_config, config as static_config
    load_yaml_config(config_dir=str(CONFIG_DIR))

    print("\n")
    result = asyncio.run(check_figma_health(static_config))
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
