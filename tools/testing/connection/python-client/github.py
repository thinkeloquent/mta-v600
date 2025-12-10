#!/usr/bin/env python3
"""
GitHub API - Python Client Integration Test

Authentication: Bearer Token
Base URL: https://api.github.com
Health Endpoint: GET /user

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
from provider_api_getters import GithubApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = GithubApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters
    "GITHUB_TOKEN": api_key_result.api_key,
    "AUTH_TYPE": api_key_result.auth_type,

    # Base URL (from provider or override)
    "BASE_URL": provider.get_base_url() or "https://api.github.com",

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
    print("\n=== GitHub Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("github")

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
def create_github_client():
    """Create GitHub client with standard config."""
    return create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="bearer", raw_api_key=CONFIG["GITHUB_TOKEN"]),
        default_headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )


# ============================================================================
# Sample API Calls using fetch_client
# ============================================================================
async def get_user() -> dict[str, Any]:
    """Get authenticated user."""
    print("\n=== Get Authenticated User ===\n")

    client = create_github_client()

    async with client:
        response = await client.get("/user")

        print(f"Status: {response['status']}")
        print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def list_repositories() -> dict[str, Any]:
    """List user repositories."""
    print("\n=== List Repositories ===\n")

    client = create_github_client()

    async with client:
        response = await client.get("/user/repos")

        print(f"Status: {response['status']}")
        if response["ok"] and isinstance(response["data"], list):
            print(f"Found {len(response['data'])} repositories")
            for repo in response["data"][:5]:
                print(f"  - {repo['full_name']}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_repository(owner: str, repo: str) -> dict[str, Any]:
    """Get repository details."""
    print(f"\n=== Get Repository: {owner}/{repo} ===\n")

    client = create_github_client()

    async with client:
        response = await client.get(f"/repos/{owner}/{repo}")

        print(f"Status: {response['status']}")
        print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("GitHub API Connection Test (Python Client Integration)")
    print("=" * 55)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Token: {CONFIG['GITHUB_TOKEN'][:10]}..." if CONFIG['GITHUB_TOKEN'] else "Token: Not set")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await get_user()
    # await list_repositories()
    # await get_repository("owner", "repo")


if __name__ == "__main__":
    asyncio.run(main())
