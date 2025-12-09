#!/usr/bin/env python3
"""
SauceLabs API - Python Client Integration Test

Authentication: Basic (username:access_key)
Base URL: https://api.{region}.saucelabs.com
Health Endpoint: GET /rest/v1.2/users/{username}

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
from provider_api_getters import SaucelabsApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = SaucelabsApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters
    "SAUCELABS_ACCESS_KEY": api_key_result.api_key,
    "SAUCELABS_USERNAME": api_key_result.username or os.getenv("SAUCE_USERNAME", ""),
    "AUTH_TYPE": api_key_result.auth_type,

    # Base URL (from provider or override)
    "BASE_URL": provider.get_base_url() or os.getenv("SAUCELABS_BASE_URL", "https://api.us-west-1.saucelabs.com"),

    # Debug
    "DEBUG": os.getenv("DEBUG", "true").lower() not in ("false", "0"),
}


# ============================================================================
# Health Check
# ============================================================================
async def health_check() -> dict[str, Any]:
    """Health check using ProviderHealthChecker."""
    print("\n=== SauceLabs Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("saucelabs")

    print(f"Status: {result.status}")
    if result.latency_ms:
        print(f"Latency: {result.latency_ms:.2f}ms")
    if result.message:
        print(f"Message: {result.message}")
    if result.error:
        print(f"Error: {result.error}")

    return {"success": result.status == "connected", "result": result}


# ============================================================================
# Sample API Calls using fetch_client
# ============================================================================
async def get_user() -> dict[str, Any]:
    """Get current user information."""
    print("\n=== Get User Info ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="basic", api_key=CONFIG["SAUCELABS_ACCESS_KEY"], username=CONFIG["SAUCELABS_USERNAME"]),
        default_headers={
            "Accept": "application/json",
        },
    )

    async with client:
        response = await client.get(f"/rest/v1.2/users/{CONFIG['SAUCELABS_USERNAME']}")

        print(f"Status: {response.status}")
        print(f"Response: {json.dumps(response.data, indent=2)}")

        return {"success": response.ok, "data": response.data}


async def list_jobs(limit: int = 10) -> dict[str, Any]:
    """List recent jobs."""
    print(f"\n=== List Jobs (limit: {limit}) ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="basic", api_key=CONFIG["SAUCELABS_ACCESS_KEY"], username=CONFIG["SAUCELABS_USERNAME"]),
        default_headers={
            "Accept": "application/json",
        },
    )

    async with client:
        response = await client.get(
            f"/rest/v1.1/{CONFIG['SAUCELABS_USERNAME']}/jobs",
            params={"limit": limit},
        )

        print(f"Status: {response.status}")
        if response.ok and isinstance(response.data, list):
            print(f"Found {len(response.data)} jobs")
            for job in response.data[:5]:
                print(f"  - {job.get('id')}: {job.get('name')} ({job.get('status')})")
        else:
            print(f"Response: {json.dumps(response.data, indent=2)}")

        return {"success": response.ok, "data": response.data}


async def get_job(job_id: str) -> dict[str, Any]:
    """Get job details."""
    print(f"\n=== Get Job: {job_id} ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="basic", api_key=CONFIG["SAUCELABS_ACCESS_KEY"], username=CONFIG["SAUCELABS_USERNAME"]),
        default_headers={
            "Accept": "application/json",
        },
    )

    async with client:
        response = await client.get(f"/rest/v1.1/{CONFIG['SAUCELABS_USERNAME']}/jobs/{job_id}")

        print(f"Status: {response.status}")
        print(f"Response: {json.dumps(response.data, indent=2)}")

        return {"success": response.ok, "data": response.data}


async def get_usage() -> dict[str, Any]:
    """Get usage statistics."""
    print("\n=== Get Usage Statistics ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(type="basic", api_key=CONFIG["SAUCELABS_ACCESS_KEY"], username=CONFIG["SAUCELABS_USERNAME"]),
        default_headers={
            "Accept": "application/json",
        },
    )

    async with client:
        response = await client.get(f"/rest/v1.2/users/{CONFIG['SAUCELABS_USERNAME']}/concurrency")

        print(f"Status: {response.status}")
        print(f"Response: {json.dumps(response.data, indent=2)}")

        return {"success": response.ok, "data": response.data}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("SauceLabs API Connection Test (Python Client Integration)")
    print("=" * 57)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Username: {CONFIG['SAUCELABS_USERNAME']}")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await get_user()
    # await list_jobs(limit=5)
    # await get_job("your_job_id")
    # await get_usage()


if __name__ == "__main__":
    asyncio.run(main())
