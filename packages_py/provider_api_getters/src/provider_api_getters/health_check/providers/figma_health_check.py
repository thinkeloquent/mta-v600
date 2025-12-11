#!/usr/bin/env python3
"""
Figma Health Check - Standalone debugging script with explicit 7-step pattern.

Flow: YamlConfig -> ProviderConfig -> ProxyConfig -> AuthConfig -> RequestConfig -> Fetch -> Response

Run directly: python -m provider_api_getters.health_check.providers.figma_health_check
Or from project root: python packages_py/provider_api_getters/src/provider_api_getters/health_check/providers/figma_health_check.py

Uses:
- static_config for YAML configuration
- FigmaApiToken for API token resolution
- fetch_client for HTTP requests with proxy/auth support
- auth_resolver for consistent auth config (SINGLE SOURCE OF TRUTH)
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# ============================================================
# Handle both direct execution and module import
# ============================================================
if __name__ == "__main__":
    # Add src directory to path for direct execution
    _src_dir = Path(__file__).parent.parent.parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from provider_api_getters.api_token import FigmaApiToken
    from provider_api_getters.utils.auth_resolver import (
        create_auth_config,
        get_auth_type_category,
    )
else:
    # Relative import when used as module
    from ...api_token import FigmaApiToken
    from ...utils.auth_resolver import create_auth_config, get_auth_type_category

# ============================================================
# Fetch client with dispatcher
# ============================================================
from fetch_client import create_client_with_dispatcher


def _print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"Step: {title}")
    print("=" * 60)


def _print_json(data: Dict[str, Any]) -> None:
    """Print JSON data with indentation."""
    print(json.dumps(data, indent=2, default=str))


def _mask_sensitive(value: str, show_chars: int = 10) -> str:
    """Mask sensitive values for logging."""
    if not value:
        return "<none>"
    if len(value) <= show_chars:
        return "*" * len(value)
    return value[:show_chars] + "***"


async def check_figma_health(config: Optional[Any] = None) -> Dict[str, Any]:
    """
    Figma Health Check - Explicit 7-step building block pattern.

    Flow: YamlConfig -> ProviderConfig -> ProxyConfig -> AuthConfig -> RequestConfig -> Fetch -> Response

    This pattern is identical across:
    - FastAPI endpoints
    - Fastify endpoints
    - Standalone scripts (this file)
    - CLI tools
    - SDKs

    Args:
        config: Configuration store (if None, loads from static_config)

    Returns:
        dict: Health check result with success status, data/error, and config_used metadata
    """
    # ============================================================
    # Step 1: YAML CONFIG LOADING
    # ============================================================
    _print_section("1. YAML CONFIG LOADING")

    if config is None:
        from static_config import config as static_config
        config = static_config

    config_source = getattr(config, "_source", "unknown")
    print(f"  Loaded from: {config_source}")

    # ============================================================
    # Step 2: PROVIDER CONFIG EXTRACTION
    # ============================================================
    _print_section("2. PROVIDER CONFIG EXTRACTION")

    provider = FigmaApiToken(config)

    provider_config = {
        "provider_name": provider.provider_name,
        "base_url": provider.get_base_url(),
        "health_endpoint": provider.health_endpoint,
        "auth_type": provider.get_auth_type(),
        "header_name": provider.get_header_name(),
    }
    _print_json(provider_config)

    # Early exit if missing critical config
    if not provider_config["base_url"]:
        return {
            "success": False,
            "error": "No base URL configured",
            "config_used": {"provider": provider_config},
        }

    # ============================================================
    # Step 3: PROXY CONFIG RESOLUTION
    # ============================================================
    _print_section("3. PROXY CONFIG RESOLUTION")

    network_config = provider.get_network_config()

    proxy_config = {
        "proxy_url": network_config.get("proxy_url"),
        "cert_verify": network_config.get("cert_verify"),
        "ca_bundle": network_config.get("ca_bundle"),
        "agent_proxy": network_config.get("agent_proxy"),
    }
    _print_json(proxy_config)

    # ============================================================
    # Step 4: AUTH CONFIG RESOLUTION (uses shared utility)
    # ============================================================
    _print_section("4. AUTH CONFIG RESOLUTION")

    api_key_result = provider.get_api_key()

    print(f"  Has credentials: {api_key_result.has_credentials}")
    print(f"  Is placeholder: {api_key_result.is_placeholder}")

    if not api_key_result.has_credentials or api_key_result.is_placeholder:
        return {
            "success": False,
            "error": "Missing or placeholder credentials",
            "config_used": {
                "provider": provider_config,
                "proxy": proxy_config,
            },
        }

    # Use shared auth resolver (SINGLE SOURCE OF TRUTH)
    auth_type = provider.get_auth_type()
    header_name = provider.get_header_name()
    auth_config = create_auth_config(auth_type, api_key_result, header_name)
    auth_category = get_auth_type_category(auth_type)

    print(f"  Provider auth_type: {auth_type}")
    print(f"  Auth category: {auth_category}")
    print(f"  Resolved to: type={auth_config.type}")
    print(f"  Header: {auth_config.header_name or 'Authorization'}")
    print(f"  API key: {_mask_sensitive(auth_config.raw_api_key)}")

    # ============================================================
    # Step 5: REQUEST CONFIG
    # ============================================================
    _print_section("5. REQUEST CONFIG")

    request_config = {
        "method": "GET",
        "url": f"{provider_config['base_url']}{provider_config['health_endpoint']}",
        "headers": provider.get_headers_config() or {},
        "timeout": 30,
    }

    # Figma-specific headers
    request_config["headers"].update({
        "Accept": "application/json",
    })

    _print_json(request_config)

    # ============================================================
    # Step 6: FETCH (with all configs applied)
    # ============================================================
    _print_section("6. FETCH")

    print(f"  Creating client with dispatcher...")
    print(f"  Base URL: {provider_config['base_url']}")
    print(f"  Auth type: {auth_config.type}")
    print(f"  Proxy: {proxy_config['proxy_url'] or 'None'}")
    print(f"  Verify SSL: {proxy_config['cert_verify']}")

    client = create_client_with_dispatcher(
        base_url=provider_config["base_url"],
        auth=auth_config,
        default_headers=request_config["headers"],
        verify=proxy_config["cert_verify"],
        proxy=proxy_config["proxy_url"],
    )

    start_time = time.perf_counter()

    async with client:
        print(f"\n  Sending request...")
        print(f"  GET {request_config['url']}")
        response = await client.get(provider_config["health_endpoint"])

    latency_ms = (time.perf_counter() - start_time) * 1000

    # ============================================================
    # Step 7: RESPONSE HANDLING
    # ============================================================
    _print_section("7. RESPONSE HANDLING")

    print(f"  Status: {response['status']}")
    print(f"  OK: {response['ok']}")
    print(f"  Latency: {latency_ms:.2f}ms")

    # Build config_used for debugging
    config_used = {
        "provider": provider_config,
        "proxy": proxy_config,
        "auth_type": auth_type,
        "auth_category": auth_category,
    }

    if response["ok"]:
        data = response["data"]
        user_id = data.get("id", "N/A")
        handle = data.get("handle", "N/A")
        email = data.get("email", "N/A")
        img_url = data.get("img_url", "N/A")

        print(f"\n  [User Info]")
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
            "latency_ms": latency_ms,
            "config_used": config_used,
        }
    else:
        print(f"\n  [Error Response]")
        _print_json(response["data"])

        return {
            "success": False,
            "status_code": response["status"],
            "error": response["data"],
            "latency_ms": latency_ms,
            "config_used": config_used,
        }


if __name__ == "__main__":
    # Load config when run directly as standalone script
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
    CONFIG_DIR = PROJECT_ROOT / "common" / "config"

    from static_config import load_yaml_config, config as static_config
    load_yaml_config(config_dir=str(CONFIG_DIR))

    print("\n")
    print("=" * 60)
    print("FIGMA HEALTH CHECK - Explicit 7-Step Pattern")
    print("=" * 60)
    print("Flow: YamlConfig -> Provider -> Proxy -> Auth -> Request -> Fetch -> Response")

    result = asyncio.run(check_figma_health(static_config))

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
