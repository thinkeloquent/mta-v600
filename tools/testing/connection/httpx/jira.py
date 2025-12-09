#!/usr/bin/env python3
"""
Jira API - httpx Connection Test

Authentication: Basic (email:api_token)
Base URL: https://{company}.atlassian.net
Health Endpoint: GET /rest/api/2/myself

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
    "JIRA_BASE_URL": os.getenv("JIRA_BASE_URL", "https://your-company.atlassian.net"),
    "JIRA_EMAIL": os.getenv("JIRA_EMAIL", "your.email@example.com"),
    "JIRA_API_TOKEN": os.getenv("JIRA_API_TOKEN", "your_jira_api_token_here"),

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


def create_basic_auth_header() -> str:
    """Create Basic auth header."""
    credentials = f"{CONFIG['JIRA_EMAIL']}:{CONFIG['JIRA_API_TOKEN']}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


# ============================================================================
# Health Check
# ============================================================================

async def health_check() -> dict[str, Any]:
    """Perform health check against Jira API."""
    print("\n=== Jira Health Check ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['JIRA_BASE_URL']}/rest/api/2/myself",
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

async def search_issues(jql: str) -> dict[str, Any]:
    """Search issues using JQL."""
    print(f"\n=== Search Issues: {jql} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['JIRA_BASE_URL']}/rest/api/2/search",
                params={"jql": jql, "maxResults": 10},
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Found {data.get('total', 0)} issues")
            for issue in data.get("issues", [])[:5]:
                print(f"  - {issue['key']}: {issue['fields']['summary']}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def get_issue(issue_key: str) -> dict[str, Any]:
    """Get issue details."""
    print(f"\n=== Get Issue: {issue_key} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['JIRA_BASE_URL']}/rest/api/2/issue/{issue_key}",
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


async def list_projects() -> dict[str, Any]:
    """List all projects."""
    print("\n=== List Projects ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['JIRA_BASE_URL']}/rest/api/2/project",
                headers={
                    "Authorization": create_basic_auth_header(),
                    "Accept": "application/json",
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Found {len(data)} projects")
            for project in data[:10]:
                print(f"  - {project['key']}: {project['name']}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("Jira API Connection Test")
    print("========================")
    print(f"Base URL: {CONFIG['JIRA_BASE_URL']}")
    print(f"Proxy: {CONFIG['HTTPS_PROXY'] or 'None'}")
    print(f"Email: {CONFIG['JIRA_EMAIL']}")
    print(f"SSL Verify: {CONFIG['VERIFY_SSL']}")
    print(f"CA Bundle: {CONFIG['CA_BUNDLE'] or 'System default'}")

    await health_check()
    # await list_projects()
    # await search_issues("project = MYPROJECT ORDER BY created DESC")
    # await get_issue("MYPROJECT-123")


if __name__ == "__main__":
    asyncio.run(main())
