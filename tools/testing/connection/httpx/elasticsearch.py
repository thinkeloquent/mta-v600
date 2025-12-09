#!/usr/bin/env python3
"""
Elasticsearch API - httpx Connection Test

Authentication: Basic (username:password)
Base URL: https://{host}:9200
Health Endpoint: GET /_cluster/health

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
    "ELASTICSEARCH_HOST": os.getenv("ELASTICSEARCH_HOST", "localhost"),
    "ELASTICSEARCH_PORT": os.getenv("ELASTICSEARCH_PORT", "9200"),
    "ELASTICSEARCH_USER": os.getenv("ELASTICSEARCH_USER", "elastic"),
    "ELASTICSEARCH_PASSWORD": os.getenv("ELASTICSEARCH_PASSWORD", "your_password_here"),

    # Optional: Use HTTPS
    "ELASTICSEARCH_USE_SSL": os.getenv("ELASTICSEARCH_USE_SSL", "true").lower() == "true",

    # Optional: Proxy Configuration
    "HTTPS_PROXY": os.getenv("HTTPS_PROXY", ""),  # e.g., "http://proxy.example.com:8080"

    # Optional: TLS Configuration
    # Set SSL_CERT_VERIFY=0 to ignore certificate errors (default for Elasticsearch)
    "VERIFY_SSL": os.getenv("SSL_CERT_VERIFY", "0") != "0",  # Elasticsearch often uses self-signed certs

    # Optional: Custom CA certificates
    # REQUEST_CA_BUNDLE, SSL_CERT_FILE, or REQUESTS_CA_BUNDLE - path to custom CA bundle
    "CA_BUNDLE": os.getenv("REQUEST_CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or "",
}

# Build base URL
PROTOCOL = "https" if CONFIG["ELASTICSEARCH_USE_SSL"] else "http"
BASE_URL = f"{PROTOCOL}://{CONFIG['ELASTICSEARCH_HOST']}:{CONFIG['ELASTICSEARCH_PORT']}"


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
    credentials = f"{CONFIG['ELASTICSEARCH_USER']}:{CONFIG['ELASTICSEARCH_PASSWORD']}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


# ============================================================================
# Health Check
# ============================================================================

async def health_check() -> dict[str, Any]:
    """Perform health check against Elasticsearch."""
    print("\n=== Elasticsearch Health Check ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/_cluster/health",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Cluster: {data.get('cluster_name')}")
            print(f"Health: {data.get('status')}")
            print(f"Nodes: {data.get('number_of_nodes')}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Sample API Calls
# ============================================================================

async def get_cluster_info() -> dict[str, Any]:
    """Get cluster information."""
    print("\n=== Get Cluster Info ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                BASE_URL,
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


async def list_indices() -> dict[str, Any]:
    """List all indices."""
    print("\n=== List Indices ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/_cat/indices",
                params={"format": "json"},
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Found {len(data)} indices")
            for index in data[:10]:
                print(f"  - {index['index']} ({index.get('docs.count', 0)} docs)")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def search_index(index: str, query: dict) -> dict[str, Any]:
    """Search an index."""
    print(f"\n=== Search Index: {index} ===\n")

    async with create_client() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/{index}/_search",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=query,
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            hits = data.get("hits", {})
            print(f"Total hits: {hits.get('total', {}).get('value', 0)}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("Elasticsearch API Connection Test")
    print("==================================")
    print(f"Base URL: {BASE_URL}")
    print(f"Proxy: {CONFIG['HTTPS_PROXY'] or 'None'}")
    print(f"User: {CONFIG['ELASTICSEARCH_USER']}")
    print(f"SSL Verify: {CONFIG['VERIFY_SSL']}")
    print(f"CA Bundle: {CONFIG['CA_BUNDLE'] or 'System default'}")

    await health_check()
    # await get_cluster_info()
    # await list_indices()
    # await search_index("my-index", {"query": {"match_all": {}}})


if __name__ == "__main__":
    asyncio.run(main())
