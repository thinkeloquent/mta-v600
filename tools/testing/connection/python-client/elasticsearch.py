#!/usr/bin/env python3
"""
Elasticsearch API - Python Client Integration Test

Authentication: Basic (username:password) or API Key
Base URL: https://{host}:{port}
Health Endpoint: GET /

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
from provider_api_getters import ElasticsearchApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = ElasticsearchApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters
    "ES_API_KEY": api_key_result.api_key,
    "ES_USERNAME": api_key_result.username,
    "AUTH_TYPE": api_key_result.auth_type,

    # Base URL (from provider or override)
    "BASE_URL": provider.get_base_url() or os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),

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
    print("\n=== Elasticsearch Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("elasticsearch")

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
def get_auth_config() -> AuthConfig:
    """Get auth config based on auth type."""
    if CONFIG["AUTH_TYPE"] == "bearer":
        return AuthConfig(type="bearer", raw_api_key=CONFIG["ES_API_KEY"])
    else:
        return AuthConfig(type="basic", raw_api_key=CONFIG["ES_API_KEY"], username=CONFIG["ES_USERNAME"])


def create_es_client(headers: dict[str, str] | None = None):
    """Create Elasticsearch client with standard config."""
    return create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=get_auth_config(),
        default_headers=headers or {"Accept": "application/json"},
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )


# ============================================================================
# Sample API Calls using fetch_client
# ============================================================================
async def get_cluster_info() -> dict[str, Any]:
    """Get cluster info (root endpoint)."""
    print("\n=== Get Cluster Info ===\n")

    client = create_es_client()

    async with client:
        response = await client.get("/")

        print(f"Status: {response['status']}")
        if response["ok"]:
            print(f"Name: {response['data'].get('name')}")
            print(f"Cluster: {response['data'].get('cluster_name')}")
            print(f"Version: {response['data'].get('version', {}).get('number')}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_cluster_health() -> dict[str, Any]:
    """Get cluster health."""
    print("\n=== Get Cluster Health ===\n")

    client = create_es_client()

    async with client:
        response = await client.get("/_cluster/health")

        print(f"Status: {response['status']}")
        if response["ok"]:
            print(f"Cluster: {response['data'].get('cluster_name')}")
            print(f"Health: {response['data'].get('status')}")
            print(f"Nodes: {response['data'].get('number_of_nodes')}")
            print(f"Data Nodes: {response['data'].get('number_of_data_nodes')}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def list_indices() -> dict[str, Any]:
    """List all indices."""
    print("\n=== List Indices ===\n")

    client = create_es_client()

    async with client:
        response = await client.get("/_cat/indices", params={"format": "json"})

        print(f"Status: {response['status']}")
        if response["ok"] and isinstance(response["data"], list):
            print(f"Found {len(response['data'])} indices")
            for idx in response["data"][:10]:
                print(f"  - {idx.get('index')}: {idx.get('docs.count')} docs ({idx.get('store.size')})")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def search_index(index: str, query: dict) -> dict[str, Any]:
    """Search an index."""
    print(f"\n=== Search Index: {index} ===\n")

    client = create_es_client({
        "Accept": "application/json",
        "Content-Type": "application/json",
    })

    async with client:
        response = await client.post(f"/{index}/_search", json=query)

        print(f"Status: {response['status']}")
        if response["ok"]:
            hits = response["data"].get("hits", {})
            print(f"Total hits: {hits.get('total', {}).get('value', 0)}")
            for hit in hits.get("hits", [])[:5]:
                print(f"  - {hit.get('_id')}: {hit.get('_source', {})}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("Elasticsearch API Connection Test (Python Client Integration)")
    print("=" * 61)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Username: {CONFIG['ES_USERNAME']}")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await get_cluster_info()
    # await get_cluster_health()
    # await list_indices()
    # await search_index("my-index", {"query": {"match_all": {}}})


if __name__ == "__main__":
    asyncio.run(main())
