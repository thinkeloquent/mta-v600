#!/usr/bin/env python3
"""
GitHub API - httpx Connection Test

Authentication: Bearer Token
Base URL: https://api.github.com
Health Endpoint: GET /user

TLS/SSL Options:
  SSL_CERT_VERIFY=0              - Ignore all certificate errors
  REQUEST_CA_BUNDLE=/path/to/ca  - Custom CA bundle file
  SSL_CERT_FILE=/path/to/cert    - Custom SSL certificate file
  REQUESTS_CA_BUNDLE=/path/to/ca - Alternative CA bundle (requests compat)
"""

import asyncio
import json
import os
from typing import Any, Union

import httpx

# ============================================================================
# Configuration - Override these values
# ============================================================================

CONFIG = {
    # Required
    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", "your_github_token_here"),

    # Base URL
    "BASE_URL": "https://api.github.com",

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
        timeout=httpx.Timeout(30.0),
    )


# ============================================================================
# Health Check
# ============================================================================

async def health_check() -> dict[str, Any]:
    """Perform health check against GitHub API."""
    print("\n=== GitHub Health Check ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/user",
                headers={
                    "Authorization": f"Bearer {CONFIG['GITHUB_TOKEN']}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
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

async def list_repositories() -> dict[str, Any]:
    """List user repositories."""
    print("\n=== List Repositories ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/user/repos",
                headers={
                    "Authorization": f"Bearer {CONFIG['GITHUB_TOKEN']}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Found {len(data)} repositories")
            for repo in data[:5]:
                print(f"  - {repo['full_name']}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def get_repository(owner: str, repo: str) -> dict[str, Any]:
    """Get repository details."""
    print(f"\n=== Get Repository: {owner}/{repo} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/repos/{owner}/{repo}",
                headers={
                    "Authorization": f"Bearer {CONFIG['GITHUB_TOKEN']}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
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
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("GitHub API Connection Test")
    print("==========================")
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Proxy: {CONFIG['HTTPS_PROXY'] or 'None'}")
    print(f"Token: {CONFIG['GITHUB_TOKEN'][:10]}...")
    print(f"SSL Verify: {CONFIG['VERIFY_SSL']}")
    print(f"CA Bundle: {CONFIG['CA_BUNDLE'] or 'System default'}")

    await health_check()
    # await list_repositories()
    # await get_repository("owner", "repo")


if __name__ == "__main__":
    asyncio.run(main())
