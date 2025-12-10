#!/usr/bin/env python3
"""
Figma API - Python Client Integration Test

Authentication: X-Figma-Token header
Base URL: https://api.figma.com
Health Endpoint: GET /v1/me

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
from provider_api_getters import FigmaApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = FigmaApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters
    "FIGMA_TOKEN": api_key_result.api_key,
    "AUTH_TYPE": api_key_result.auth_type,
    "HEADER_NAME": api_key_result.header_name or "X-Figma-Token",

    # Base URL (from provider or override)
    "BASE_URL": provider.get_base_url() or "https://api.figma.com",

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
    print("\n=== Figma Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("figma")

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
def create_figma_client():
    """Create Figma client with standard config."""
    return create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(
            type="custom_header",
            raw_api_key=CONFIG["FIGMA_TOKEN"],
            header_name=CONFIG["HEADER_NAME"],
        ),
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )


# ============================================================================
# Sample API Calls using fetch_client
# ============================================================================
async def get_me() -> dict[str, Any]:
    """Get current user."""
    print("\n=== Get Current User ===\n")

    client = create_figma_client()

    async with client:
        response = await client.get("/v1/me")

        print(f"Status: {response['status']}")
        print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_file(file_key: str) -> dict[str, Any]:
    """Get file details."""
    print(f"\n=== Get File: {file_key} ===\n")

    client = create_figma_client()

    async with client:
        response = await client.get(f"/v1/files/{file_key}")

        print(f"Status: {response['status']}")
        if response["ok"]:
            print(f"File name: {response['data'].get('name')}")
            print(f"Last modified: {response['data'].get('lastModified')}")
            print(f"Version: {response['data'].get('version')}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_file_nodes(file_key: str, node_ids: list[str]) -> dict[str, Any]:
    """Get specific nodes from a file."""
    print(f"\n=== Get File Nodes: {file_key} ===\n")

    client = create_figma_client()

    async with client:
        response = await client.get(
            f"/v1/files/{file_key}/nodes",
            params={"ids": ",".join(node_ids)},
        )

        print(f"Status: {response['status']}")
        print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_team_projects(team_id: str) -> dict[str, Any]:
    """Get team projects."""
    print(f"\n=== Get Team Projects: {team_id} ===\n")

    client = create_figma_client()

    async with client:
        response = await client.get(f"/v1/teams/{team_id}/projects")

        print(f"Status: {response['status']}")
        if response["ok"]:
            projects = response["data"].get("projects", [])
            print(f"Found {len(projects)} projects")
            for project in projects[:10]:
                print(f"  - {project['name']} (id: {project['id']})")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("Figma API Connection Test (Python Client Integration)")
    print("=" * 53)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Token: {CONFIG['FIGMA_TOKEN'][:10]}..." if CONFIG['FIGMA_TOKEN'] else "Token: Not set")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Header: {CONFIG['HEADER_NAME']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await get_me()
    # await get_file("your_file_key")
    # await get_file_nodes("your_file_key", ["0:1", "0:2"])
    # await get_team_projects("your_team_id")


if __name__ == "__main__":
    asyncio.run(main())
