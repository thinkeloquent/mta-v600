#!/usr/bin/env python3
"""
Confluence API - Python Client Integration Test

Authentication: Bearer Token
Base URL: https://{company}.atlassian.net/wiki
Health Endpoint: GET /rest/api/user/current

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
from fetch_client import create_client_with_dispatcher, AuthConfig, print_proxy_config
from provider_api_getters import ConfluenceApiToken

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = ConfluenceApiToken(static_config)
api_key_result = provider.get_api_key()
network_config = provider.get_network_config()


CONFIG = {
    # From provider_api_getters
    "BEARER_TOKEN": api_key_result.api_key or os.getenv("CONFLUENCE_API_TOKEN"),
    "API_TOKEN": api_key_result.api_key,
    "CONFLUENCE_EMAIL": api_key_result.username or os.getenv("CONFLUENCE_EMAIL"),
    "AUTH_TYPE": "bearer",
    "BASE_URL": provider.get_base_url() or os.getenv("CONFLUENCE_BASE_URL", "https://your-company.atlassian.net/wiki"),
    "DEBUG": os.getenv("DEBUG", "true").lower() not in ("false", "0"),
    # Network/Proxy Configuration (from YAML config, with env var fallbacks)
    "PROXY": network_config["proxy_url"] or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"),
    # SSL/TLS Configuration (from YAML config, with env var fallbacks)
    "SSL_VERIFY": network_config["cert_verify"],  # From YAML config
    "CERT": network_config["cert"] or os.getenv("CERT"),  # Client certificate path
    "CA_BUNDLE": network_config["ca_bundle"] or os.getenv("CA_BUNDLE"),  # CA bundle path
}


# ============================================================================
# Health Check
# ============================================================================
async def health_check() -> dict[str, Any]:
    """Health check using /rest/api/user/current endpoint."""
    print("\n=== Confluence Health Check ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        # basic_email_token type: "Basic <base64(email:token)>" - Atlassian APIs
        auth=AuthConfig(
            type="basic_email_token",
            raw_api_key=api_key_result.raw_api_key,  # Raw API token (not pre-encoded)
            email=CONFIG["CONFLUENCE_EMAIL"],
        ),
        # Alternative: use custom type with pre-encoded token
        # auth=AuthConfig(type="custom", api_key=CONFIG["API_TOKEN"], header_name="Authorization"),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        # response = await client.get("/rest/api/user/current")
        response = await client.get("/rest/api/space")

        print(f"Status: {response['status']}")
        if response["ok"]:
            user = response["data"]
            print(f"User: {user.get('displayName', 'N/A')}")
            print(f"Username: {user.get('username', 'N/A')}")
            print(f"Email: {user.get('email', 'N/A')}")
        else:
            print(f"Error: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


# ============================================================================
# Sample API Calls using fetch_client
# ============================================================================
async def list_spaces() -> dict[str, Any]:
    """List all spaces."""
    print("\n=== List Spaces ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="bearer", raw_api_key=CONFIG["BEARER_TOKEN"]),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        response = await client.get("/rest/api/space")

        print(f"Status: {response['status']}")
        if response["ok"]:
            results = response["data"].get("results", [])
            print(f"Found {len(results)} spaces")
            for space in results[:10]:
                print(f"  - {space['key']}: {space['name']}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_space(space_key: str) -> dict[str, Any]:
    """Get space details."""
    print(f"\n=== Get Space: {space_key} ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="bearer", raw_api_key=CONFIG["BEARER_TOKEN"]),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        response = await client.get(f"/rest/api/space/{space_key}")

        print(f"Status: {response['status']}")
        print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def search_content(query: str) -> dict[str, Any]:
    """Search content using CQL."""
    print(f"\n=== Search Content: {query} ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="bearer", raw_api_key=CONFIG["BEARER_TOKEN"]),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        response = await client.get(
            "/rest/api/content/search",
            params={"cql": query, "limit": 10},
        )

        print(f"Status: {response['status']}")
        if response["ok"]:
            results = response["data"].get("results", [])
            print(f"Found {len(results)} results")
            for content in results[:5]:
                print(f"  - {content['title']}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_page(page_id: str) -> dict[str, Any]:
    """Get page details."""
    print(f"\n=== Get Page: {page_id} ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="bearer", raw_api_key=CONFIG["BEARER_TOKEN"]),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        response = await client.get(
            f"/rest/api/content/{page_id}",
            params={"expand": "body.storage,version"},
        )

        print(f"Status: {response['status']}")
        print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("Confluence API Connection Test (Python Client Integration)")
    print("=" * 58)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"SSL Verify: {CONFIG['SSL_VERIFY']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    # Print proxy/SSL configuration from YAML for debugging
    if CONFIG["DEBUG"]:
        print()
        print_proxy_config()

    await health_check()

    # Uncomment to run additional tests:
    # await list_spaces()
    # await get_space("MYSPACE")
    # await search_content("type=page AND space=MYSPACE")
    # await get_page("123456")


if __name__ == "__main__":
    asyncio.run(main())
