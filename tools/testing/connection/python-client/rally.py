#!/usr/bin/env python3
"""
Rally API - Python Client Integration Test

Authentication: Bearer Token (ZSESSIONID)
Base URL: https://rally1.rallydev.com/slm/webservice/v2.0
Health Endpoint: GET /subscription

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
from provider_api_getters import RallyApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = RallyApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters
    "RALLY_API_KEY": api_key_result.api_key,
    "AUTH_TYPE": api_key_result.auth_type,
    "HEADER_NAME": api_key_result.header_name or "ZSESSIONID",

    # Base URL (from provider or override)
    "BASE_URL": provider.get_base_url() or "https://rally1.rallydev.com/slm/webservice/v2.0",

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
    print("\n=== Rally Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("rally")

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
def create_rally_client():
    """Create Rally client with standard config."""
    return create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(
            type="custom_header",
            raw_api_key=CONFIG["RALLY_API_KEY"],
            header_name=CONFIG["HEADER_NAME"],
        ),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )


# ============================================================================
# Sample API Calls using fetch_client
# ============================================================================
async def get_subscription() -> dict[str, Any]:
    """Get subscription info."""
    print("\n=== Get Subscription ===\n")

    client = create_rally_client()

    async with client:
        response = await client.get("/subscription")

        print(f"Status: {response['status']}")
        if response["ok"]:
            subscription = response["data"].get("Subscription", {})
            print(f"Name: {subscription.get('_refObjectName')}")
            print(f"ID: {subscription.get('SubscriptionID')}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_current_user() -> dict[str, Any]:
    """Get current user info."""
    print("\n=== Get Current User ===\n")

    client = create_rally_client()

    async with client:
        response = await client.get("/user")

        print(f"Status: {response['status']}")
        if response["ok"]:
            user = response["data"].get("User", {})
            print(f"Name: {user.get('_refObjectName')}")
            print(f"Email: {user.get('EmailAddress')}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def list_projects() -> dict[str, Any]:
    """List projects."""
    print("\n=== List Projects ===\n")

    client = create_rally_client()

    async with client:
        response = await client.get(
            "/project",
            params={"pagesize": 10, "fetch": "Name,ObjectID,State"},
        )

        print(f"Status: {response['status']}")
        if response["ok"]:
            query_result = response["data"].get("QueryResult", {})
            results = query_result.get("Results", [])
            print(f"Total: {query_result.get('TotalResultCount', 0)}")
            for project in results[:10]:
                print(f"  - {project.get('_refObjectName')} ({project.get('State')})")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def query_user_stories(project_id: str = None) -> dict[str, Any]:
    """Query user stories."""
    print("\n=== Query User Stories ===\n")

    client = create_rally_client()

    params = {
        "pagesize": 10,
        "fetch": "FormattedID,Name,ScheduleState,Owner",
        "order": "CreationDate desc",
    }

    if project_id:
        params["query"] = f"(Project.ObjectID = {project_id})"

    async with client:
        response = await client.get("/hierarchicalrequirement", params=params)

        print(f"Status: {response['status']}")
        if response["ok"]:
            query_result = response["data"].get("QueryResult", {})
            results = query_result.get("Results", [])
            print(f"Total: {query_result.get('TotalResultCount', 0)}")
            for story in results[:10]:
                owner = story.get("Owner", {}).get("_refObjectName", "Unassigned")
                print(f"  - {story.get('FormattedID')}: {story.get('Name')[:50]}... ({story.get('ScheduleState')}) - {owner}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def query_defects() -> dict[str, Any]:
    """Query defects."""
    print("\n=== Query Defects ===\n")

    client = create_rally_client()

    async with client:
        response = await client.get(
            "/defect",
            params={
                "pagesize": 10,
                "fetch": "FormattedID,Name,State,Severity,Priority,Owner",
                "order": "CreationDate desc",
            },
        )

        print(f"Status: {response['status']}")
        if response["ok"]:
            query_result = response["data"].get("QueryResult", {})
            results = query_result.get("Results", [])
            print(f"Total: {query_result.get('TotalResultCount', 0)}")
            for defect in results[:10]:
                owner = defect.get("Owner", {}).get("_refObjectName", "Unassigned")
                print(f"  - {defect.get('FormattedID')}: {defect.get('Name')[:40]}... ({defect.get('State')}) - {owner}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("Rally API Connection Test (Python Client Integration)")
    print("=" * 53)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"API Key: {CONFIG['RALLY_API_KEY'][:10]}..." if CONFIG['RALLY_API_KEY'] else "API Key: Not set")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await get_subscription()
    # await get_current_user()
    # await list_projects()
    # await query_user_stories()
    # await query_defects()


if __name__ == "__main__":
    asyncio.run(main())
