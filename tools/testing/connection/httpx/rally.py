#!/usr/bin/env python3
"""
Rally API - httpx Connection Test

Authentication: ZSESSIONID header or API Key
Base URL: https://rally1.rallydev.com/slm/webservice/v2.0
Health Endpoint: GET /security/authorize

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
    # Required (use one of these methods)
    "RALLY_API_KEY": os.getenv("RALLY_API_KEY", ""),  # Preferred method
    "RALLY_ZSESSIONID": os.getenv("RALLY_ZSESSIONID", ""),  # Alternative

    # Base URL
    "BASE_URL": os.getenv("RALLY_BASE_URL", "https://rally1.rallydev.com/slm/webservice/v2.0"),

    # Optional: Workspace
    "RALLY_WORKSPACE": os.getenv("RALLY_WORKSPACE", ""),

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


def create_auth_headers() -> dict[str, str]:
    """Create authentication headers."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if CONFIG["RALLY_API_KEY"]:
        headers["ZSESSIONID"] = CONFIG["RALLY_API_KEY"]
    elif CONFIG["RALLY_ZSESSIONID"]:
        headers["ZSESSIONID"] = CONFIG["RALLY_ZSESSIONID"]

    return headers


# ============================================================================
# Health Check
# ============================================================================

async def health_check() -> dict[str, Any]:
    """Perform health check against Rally API."""
    print("\n=== Rally Health Check ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/security/authorize",
                headers=create_auth_headers(),
            )

            data = response.json()

            print(f"Status: {response.status_code}")

            operation_result = data.get("OperationResult", {})
            if operation_result.get("SecurityToken"):
                print(f"Security Token: {operation_result['SecurityToken'][:20]}...")
                print("Authentication: Success")
            else:
                errors = operation_result.get("Errors", [])
                if errors:
                    print(f"Errors: {errors}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Sample API Calls
# ============================================================================

async def get_user() -> dict[str, Any]:
    """Get current user information."""
    print("\n=== Get Current User ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/user",
                headers=create_auth_headers(),
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            user = data.get("User", {})
            print(f"User: {user.get('_refObjectName')}")
            print(f"Email: {user.get('EmailAddress')}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def list_workspaces() -> dict[str, Any]:
    """List available workspaces."""
    print("\n=== List Workspaces ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/subscription",
                params={"fetch": "Workspaces"},
                headers=create_auth_headers(),
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            subscription = data.get("Subscription", {})
            workspaces = subscription.get("Workspaces", {}).get("_tagsNameArray", [])
            print(f"Found {len(workspaces)} workspaces")
            for ws in workspaces[:10]:
                print(f"  - {ws.get('Name')}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def list_projects(workspace_ref: str = "") -> dict[str, Any]:
    """List projects in a workspace."""
    print("\n=== List Projects ===\n")

    async with create_client() as client:
        try:
            params = {"fetch": "Name,ObjectID", "pagesize": 20}
            if workspace_ref:
                params["workspace"] = workspace_ref

            response = await client.get(
                f"{CONFIG['BASE_URL']}/project",
                params=params,
                headers=create_auth_headers(),
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            query_result = data.get("QueryResult", {})
            results = query_result.get("Results", [])
            print(f"Found {query_result.get('TotalResultCount', 0)} projects")
            for project in results[:10]:
                print(f"  - {project.get('Name')} ({project.get('ObjectID')})")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def query_user_stories(project_ref: str = "", query: str = "") -> dict[str, Any]:
    """Query user stories."""
    print("\n=== Query User Stories ===\n")

    async with create_client() as client:
        try:
            params = {
                "fetch": "FormattedID,Name,ScheduleState,Owner",
                "pagesize": 10,
                "order": "FormattedID desc",
            }
            if project_ref:
                params["project"] = project_ref
            if query:
                params["query"] = query

            response = await client.get(
                f"{CONFIG['BASE_URL']}/hierarchicalrequirement",
                params=params,
                headers=create_auth_headers(),
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            query_result = data.get("QueryResult", {})
            results = query_result.get("Results", [])
            print(f"Found {query_result.get('TotalResultCount', 0)} stories")
            for story in results[:10]:
                owner = story.get("Owner", {})
                owner_name = owner.get("_refObjectName", "Unassigned") if owner else "Unassigned"
                print(f"  - {story.get('FormattedID')}: {story.get('Name')} ({story.get('ScheduleState')}) - {owner_name}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def query_defects(project_ref: str = "", query: str = "") -> dict[str, Any]:
    """Query defects."""
    print("\n=== Query Defects ===\n")

    async with create_client() as client:
        try:
            params = {
                "fetch": "FormattedID,Name,State,Priority,Severity",
                "pagesize": 10,
                "order": "FormattedID desc",
            }
            if project_ref:
                params["project"] = project_ref
            if query:
                params["query"] = query

            response = await client.get(
                f"{CONFIG['BASE_URL']}/defect",
                params=params,
                headers=create_auth_headers(),
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            query_result = data.get("QueryResult", {})
            results = query_result.get("Results", [])
            print(f"Found {query_result.get('TotalResultCount', 0)} defects")
            for defect in results[:10]:
                print(f"  - {defect.get('FormattedID')}: {defect.get('Name')} ({defect.get('State')}) - {defect.get('Priority')}/{defect.get('Severity')}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("Rally API Connection Test")
    print("=========================")
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Proxy: {CONFIG['HTTPS_PROXY'] or 'None'}")
    print(f"API Key: {'Configured' if CONFIG['RALLY_API_KEY'] else 'Not configured'}")
    print(f"ZSESSIONID: {'Configured' if CONFIG['RALLY_ZSESSIONID'] else 'Not configured'}")
    print(f"SSL Verify: {CONFIG['VERIFY_SSL']}")
    print(f"CA Bundle: {CONFIG['CA_BUNDLE'] or 'System default'}")

    await health_check()
    # await get_user()
    # await list_workspaces()
    # await list_projects()
    # await query_user_stories()
    # await query_defects()


if __name__ == "__main__":
    asyncio.run(main())
