#!/usr/bin/env python3
"""
Elasticsearch Health Check - Standalone debugging script

Run directly: python elasticsearch_health_check.py

Uses:
- static_config for YAML configuration
- ElasticsearchApiToken for API token resolution
- fetch_client for HTTP requests to cluster health endpoint
"""
import asyncio
import json
from pathlib import Path

# ============================================================
# Provider API getter (relative import to avoid circular dependency)
# ============================================================
from ...api_token import ElasticsearchApiToken

# ============================================================
# Fetch client with dispatcher
# ============================================================
from fetch_client import create_client_with_dispatcher, AuthConfig


async def check_elasticsearch_health(config: dict = None) -> dict:
    """
    Check Elasticsearch connectivity and cluster health.

    Args:
        config: Configuration dict (if None, loads from static_config)

    Returns:
        dict: Health check result with success status and data/error
    """
    # Load config if not provided
    if config is None:
        from static_config import config as static_config
        config = static_config

    print("=" * 60)
    print("ELASTICSEARCH HEALTH CHECK")
    print("=" * 60)

    # Initialize provider from config
    provider = ElasticsearchApiToken(config)
    api_key_result = provider.get_api_key()
    network_config = provider.get_network_config()
    base_url = provider.get_base_url()

    # Debug output
    print(f"\n[Config]")
    print(f"  Base URL: {base_url}")
    print(f"  Has credentials: {api_key_result.has_credentials}")
    print(f"  Is placeholder: {api_key_result.is_placeholder}")
    print(f"  Auth type: {api_key_result.auth_type}")
    print(f"  Header name: {api_key_result.header_name}")
    print(f"\n[Network Config]")
    print(f"  Proxy URL: {network_config.get('proxy_url') or 'None'}")
    print(f"  Cert verify: {network_config.get('cert_verify')}")

    if not base_url:
        print("\n[ERROR] No base URL configured")
        return {"success": False, "error": "No base URL"}

    # Create client with dispatcher (handles proxy, SSL, auth)
    print(f"\n[Creating Client]")
    print(f"  Auth type: {api_key_result.auth_type}")

    # Auth may be optional for some Elasticsearch setups
    auth = None
    if api_key_result.has_credentials and not api_key_result.is_placeholder:
        auth = AuthConfig(
            type=api_key_result.auth_type,
            raw_api_key=api_key_result.api_key,
            username=api_key_result.username,
            header_name=api_key_result.header_name,
        )

    client = create_client_with_dispatcher(
        base_url=base_url,
        auth=auth,
        default_headers={
            "Accept": "application/json",
        },
        verify=network_config.get("cert_verify"),
        proxy=network_config.get("proxy_url"),
    )

    # Make health check request - cluster health endpoint
    health_endpoint = "/_cluster/health"
    print(f"\n[Request]")
    print(f"  GET {base_url}{health_endpoint}")

    async with client:
        response = await client.get(health_endpoint)

        print(f"\n[Response]")
        print(f"  Status: {response['status']}")
        print(f"  OK: {response['ok']}")

        if response["ok"]:
            data = response["data"]
            cluster_name = data.get("cluster_name", "N/A")
            status = data.get("status", "N/A")
            number_of_nodes = data.get("number_of_nodes", 0)
            number_of_data_nodes = data.get("number_of_data_nodes", 0)
            active_shards = data.get("active_shards", 0)

            print(f"\n[Cluster Info]")
            print(f"  Cluster name: {cluster_name}")
            print(f"  Status: {status}")
            print(f"  Nodes: {number_of_nodes} ({number_of_data_nodes} data)")
            print(f"  Active shards: {active_shards}")

            # Status color indicates health
            is_healthy = status in ("green", "yellow")

            return {
                "success": is_healthy,
                "message": f"Cluster '{cluster_name}' is {status}",
                "data": {
                    "cluster_name": cluster_name,
                    "status": status,
                    "number_of_nodes": number_of_nodes,
                    "number_of_data_nodes": number_of_data_nodes,
                    "active_shards": active_shards,
                },
            }
        else:
            print(f"\n[Error Response]")
            print(json.dumps(response["data"], indent=2))
            return {
                "success": False,
                "status_code": response["status"],
                "error": response["data"],
            }


if __name__ == "__main__":
    # Load config when run directly as standalone script
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
    CONFIG_DIR = PROJECT_ROOT / "common" / "config"

    from static_config import load_yaml_config, config as static_config
    load_yaml_config(config_dir=str(CONFIG_DIR))

    print("\n")
    result = asyncio.run(check_elasticsearch_health(static_config))
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
