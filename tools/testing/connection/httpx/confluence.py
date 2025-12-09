#!/usr/bin/env python3
"""
Confluence API - httpx Connection Test

Authentication: Basic (email:api_token)
Base URL: https://{company}.atlassian.net
Health Endpoint: GET /wiki/rest/api/user/current

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
    # Required (falls back to Jira credentials)
    "CONFLUENCE_BASE_URL": os.getenv("CONFLUENCE_BASE_URL", os.getenv("JIRA_BASE_URL", "https://your-company.atlassian.net")),
    "CONFLUENCE_EMAIL": os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_EMAIL", "your.email@example.com")),
    "CONFLUENCE_API_TOKEN": os.getenv("CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", "your_api_token_here")),

    # Optional: Proxy Configuration
    "HTTPS_PROXY": os.getenv("HTTPS_PROXY", ""),  # e.g., "http://proxy.example.com:8080"

    # Optional: TLS Configuration
    # Set SSL_CERT_VERIFY=0 to ignore certificate errors
    "VERIFY_SSL": os.getenv("SSL_CERT_VERIFY", "1") != "0",

    # Optional: Custom CA certificates
    # REQUEST_CA_BUNDLE, SSL_CERT_FILE, or REQUESTS_CA_BUNDLE - path to custom CA bundle
    "CA_BUNDLE": os.getenv("REQUEST_CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or "",
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
    credentials = f"{CONFIG['CONFLUENCE_EMAIL']}:{CONFIG['CONFLUENCE_API_TOKEN']}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


# ============================================================================
# Health Check
# ============================================================================

async def health_check() -> dict[str, Any]:
    """Perform health check against Confluence API."""
    print("\n=== Confluence Health Check ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['CONFLUENCE_BASE_URL']}/wiki/rest/api/user/current",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                    "Content-Type": "application/json",
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

async def list_spaces() -> dict[str, Any]:
    """List all spaces."""
    print("\n=== List Spaces ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['CONFLUENCE_BASE_URL']}/wiki/rest/api/space",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            results = data.get("results", [])
            print(f"Found {len(results)} spaces")
            for space in results[:10]:
                print(f"  - {space['key']}: {space['name']}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def search_content(cql: str) -> dict[str, Any]:
    """Search content using CQL."""
    print(f"\n=== Search Content: {cql} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['CONFLUENCE_BASE_URL']}/wiki/rest/api/content/search",
                params={"cql": cql, "limit": 10},
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            results = data.get("results", [])
            print(f"Found {len(results)} results")
            for content in results[:5]:
                print(f"  - {content['title']} ({content['type']})")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def get_page(page_id: str) -> dict[str, Any]:
    """Get page details."""
    print(f"\n=== Get Page: {page_id} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['CONFLUENCE_BASE_URL']}/wiki/rest/api/content/{page_id}",
                params={"expand": "body.storage,version"},
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
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("Confluence API Connection Test")
    print("==============================")
    print(f"Base URL: {CONFIG['CONFLUENCE_BASE_URL']}")
    print(f"Proxy: {CONFIG['HTTPS_PROXY'] or 'None'}")
    print(f"Email: {CONFIG['CONFLUENCE_EMAIL']}")
    print(f"SSL Verify: {CONFIG['VERIFY_SSL']}")
    print(f"CA Bundle: {CONFIG['CA_BUNDLE'] or 'System default'}")

    await health_check()
    # await list_spaces()
    # await search_content("type=page")
    # await get_page("123456")


if __name__ == "__main__":
    asyncio.run(main())
