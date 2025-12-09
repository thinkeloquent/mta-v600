#!/usr/bin/env python3
"""
SauceLabs API - httpx Connection Test

Authentication: Basic (username:access_key)
Base URL: https://api.us-west-1.saucelabs.com
Health Endpoint: GET /rest/v1/users/{username}

TLS/SSL Options:
  SSL_CERT_VERIFY=0              - Ignore all certificate errors
  REQUEST_CA_BUNDLE=/path/to/ca  - Custom CA bundle file
  SSL_CERT_FILE=/path/to/cert    - Custom SSL certificate file
  REQUESTS_CA_BUNDLE=/path/to/ca - Alternative CA bundle (requests compat)
"""

import asyncio
import base64
import json
import os
from typing import Any, Union

import httpx

# ============================================================================
# Configuration - Override these values
# ============================================================================

CONFIG = {
    # Required
    "SAUCE_USERNAME": os.getenv("SAUCE_USERNAME", "your_saucelabs_username"),
    "SAUCE_ACCESS_KEY": os.getenv("SAUCE_ACCESS_KEY", "your_saucelabs_access_key"),

    # Base URL (choose your region)
    "BASE_URL": os.getenv("SAUCE_BASE_URL", "https://api.us-west-1.saucelabs.com"),
    # Other regions:
    # - US East: https://api.us-east-4.saucelabs.com
    # - EU Central: https://api.eu-central-1.saucelabs.com

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
    """Get SSL verification setting."""
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
        timeout=httpx.Timeout(30.0),
    )


def create_basic_auth_header() -> str:
    """Create Basic auth header."""
    credentials = f"{CONFIG['SAUCE_USERNAME']}:{CONFIG['SAUCE_ACCESS_KEY']}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


# ============================================================================
# Health Check
# ============================================================================

async def health_check() -> dict[str, Any]:
    """Perform health check against SauceLabs API."""
    print("\n=== SauceLabs Health Check ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/rest/v1/users/{CONFIG['SAUCE_USERNAME']}",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(data, indent=2)}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Sample API Calls
# ============================================================================

async def list_jobs(limit: int = 10) -> dict[str, Any]:
    """List recent jobs."""
    print(f"\n=== List Jobs (limit: {limit}) ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/rest/v1/{CONFIG['SAUCE_USERNAME']}/jobs",
                params={"limit": limit},
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Found {len(data)} jobs")
            for job in data[:5]:
                print(f"  - {job['id']}: {job.get('name', 'Unnamed')} ({job['status']})")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def get_job(job_id: str) -> dict[str, Any]:
    """Get job details."""
    print(f"\n=== Get Job: {job_id} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/rest/v1/{CONFIG['SAUCE_USERNAME']}/jobs/{job_id}",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(data, indent=2)}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def get_usage() -> dict[str, Any]:
    """Get account usage."""
    print("\n=== Get Account Usage ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/rest/v1/users/{CONFIG['SAUCE_USERNAME']}/usage",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(data, indent=2)}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def list_platforms() -> dict[str, Any]:
    """List available platforms."""
    print("\n=== List Available Platforms ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/rest/v1/info/platforms/webdriver",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Found {len(data)} platforms")
            for platform in data[:10]:
                print(f"  - {platform['long_name']} ({platform['short_version']})")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("SauceLabs API Connection Test")
    print("=============================")
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Proxy: {CONFIG['HTTPS_PROXY'] or 'None'}")
    print(f"Username: {CONFIG['SAUCE_USERNAME']}")
    print(f"SSL Verify: {CONFIG['VERIFY_SSL']}")
    print(f"CA Bundle: {CONFIG['CA_BUNDLE'] or 'System default'}")

    await health_check()
    # await list_jobs()
    # await get_job("job_id_here")
    # await get_usage()
    # await list_platforms()


if __name__ == "__main__":
    asyncio.run(main())
