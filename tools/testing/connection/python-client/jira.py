#!/usr/bin/env python3
"""
Jira API - Python Client Integration Test

Authentication: Basic (email:api_token)
Base URL: https://{company}.atlassian.net
Health Endpoint: GET /myself

Uses internal packages:
  - fetch_proxy_dispatcher: Environment-aware proxy configuration
  - fetch_client: HTTP client with auth support
  - provider_api_getters: API key resolution
  - app_static_config_yaml: YAML configuration loading
"""
import asyncio
import base64
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
from provider_api_getters import JiraApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = JiraApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters
    "JIRA_API_TOKEN": api_key_result.raw_api_key,  # Raw API token (not pre-encoded)
    "JIRA_EMAIL": api_key_result.email or api_key_result.username,
    "AUTH_TYPE": "basic_email_token",  # Atlassian APIs use Basic <base64(email:token)>

    # Base URL (from provider or override)
    "BASE_URL": provider.get_base_url() or os.getenv("JIRA_BASE_URL", "https://your-company.atlassian.net"),

    # SSL/TLS Configuration (runtime override, or use YAML config)
    "SSL_VERIFY": False,  # Set to None to use YAML config
    "CERT": os.getenv("CERT"),  # Client certificate path
    "CA_BUNDLE": os.getenv("CA_BUNDLE"),  # CA bundle path

    # Proxy Configuration
    "PROXY": os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"),

    # Debug
    "DEBUG": os.getenv("DEBUG", "true").lower() not in ("false", "0"),
}


def create_basic_auth_header() -> str:
    """Create Basic auth header."""
    credentials = f"{CONFIG['JIRA_EMAIL']}:{CONFIG['JIRA_API_TOKEN']}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


# ============================================================================
# Health Check
# ============================================================================
async def health_check() -> dict[str, Any]:
    """Health check using ProviderHealthChecker."""
    print("\n=== Jira Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("jira")

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
async def get_myself() -> dict[str, Any]:
    """Get current user."""
    print("\n=== Get Current User ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(
            type="basic_email_token",
            raw_api_key=CONFIG["JIRA_API_TOKEN"],
            email=CONFIG["JIRA_EMAIL"],
        ),
        default_headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        response = await client.get("/myself")

        print(f"Status: {response['status']}")
        print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def list_projects() -> dict[str, Any]:
    """List all projects."""
    print("\n=== List Projects ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(
            type="basic_email_token",
            raw_api_key=CONFIG["JIRA_API_TOKEN"],
            email=CONFIG["JIRA_EMAIL"],
        ),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        response = await client.get("/project")

        print(f"Status: {response['status']}")
        if response["ok"] and isinstance(response["data"], list):
            print(f"Found {len(response['data'])} projects")
            for project in response["data"][:10]:
                print(f"  - {project['key']}: {project['name']}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def search_issues(jql: str) -> dict[str, Any]:
    """Search issues using JQL."""
    print(f"\n=== Search Issues: {jql} ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(
            type="basic_email_token",
            raw_api_key=CONFIG["JIRA_API_TOKEN"],
            email=CONFIG["JIRA_EMAIL"],
        ),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        response = await client.get(
            "/search",
            params={"jql": jql, "maxResults": 10},
        )

        print(f"Status: {response['status']}")
        if response["ok"]:
            print(f"Found {response['data'].get('total', 0)} issues")
            for issue in response["data"].get("issues", [])[:5]:
                print(f"  - {issue['key']}: {issue['fields']['summary']}")
        else:
            print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


async def get_issue(issue_key: str) -> dict[str, Any]:
    """Get issue details."""
    print(f"\n=== Get Issue: {issue_key} ===\n")

    client = create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(
            type="basic_email_token",
            raw_api_key=CONFIG["JIRA_API_TOKEN"],
            email=CONFIG["JIRA_EMAIL"],
        ),
        default_headers={
            "Accept": "application/json",
        },
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )

    async with client:
        response = await client.get(f"/issue/{issue_key}")

        print(f"Status: {response['status']}")
        print(f"Response: {json.dumps(response['data'], indent=2)}")

        return {"success": response["ok"], "data": response["data"]}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("Jira API Connection Test (Python Client Integration)")
    print("=" * 52)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Email: {CONFIG['JIRA_EMAIL']}")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await get_myself()
    # await list_projects()
    # await search_issues("project = MYPROJECT ORDER BY created DESC")
    # await get_issue("MYPROJECT-123")


if __name__ == "__main__":
    asyncio.run(main())
