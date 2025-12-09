#!/usr/bin/env python3
"""
Figma API - httpx Connection Test

Authentication: X-Figma-Token header
Base URL: https://api.figma.com/v1
Health Endpoint: GET /v1/me

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
    "FIGMA_TOKEN": os.getenv("FIGMA_TOKEN", "your_figma_token_here"),

    # Base URL
    "BASE_URL": "https://api.figma.com",

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


# ============================================================================
# Health Check
# ============================================================================

async def health_check() -> dict[str, Any]:
    """Perform health check against Figma API."""
    print("\n=== Figma Health Check ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/v1/me",
                headers={
                    "X-Figma-Token": CONFIG["FIGMA_TOKEN"],
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

async def get_file(file_key: str) -> dict[str, Any]:
    """Get file details."""
    print(f"\n=== Get File: {file_key} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/v1/files/{file_key}",
                headers={
                    "X-Figma-Token": CONFIG["FIGMA_TOKEN"],
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"File Name: {data.get('name')}")
            print(f"Last Modified: {data.get('lastModified')}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def get_file_nodes(file_key: str, node_ids: list[str]) -> dict[str, Any]:
    """Get specific nodes from a file."""
    print(f"\n=== Get File Nodes: {file_key} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/v1/files/{file_key}/nodes",
                params={"ids": ",".join(node_ids)},
                headers={
                    "X-Figma-Token": CONFIG["FIGMA_TOKEN"],
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(data, indent=2)}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def get_file_images(file_key: str, node_ids: list[str], format: str = "png") -> dict[str, Any]:
    """Get images for specific nodes."""
    print(f"\n=== Get File Images: {file_key} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/v1/images/{file_key}",
                params={"ids": ",".join(node_ids), "format": format},
                headers={
                    "X-Figma-Token": CONFIG["FIGMA_TOKEN"],
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            print(f"Images: {data.get('images')}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


async def list_team_projects(team_id: str) -> dict[str, Any]:
    """List projects in a team."""
    print(f"\n=== List Team Projects: {team_id} ===\n")

    async with create_client() as client:
        try:
            response = await client.get(
                f"{CONFIG['BASE_URL']}/v1/teams/{team_id}/projects",
                headers={
                    "X-Figma-Token": CONFIG["FIGMA_TOKEN"],
                },
            )

            data = response.json()

            print(f"Status: {response.status_code}")
            projects = data.get("projects", [])
            print(f"Found {len(projects)} projects")
            for project in projects:
                print(f"  - {project['name']} ({project['id']})")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("Figma API Connection Test")
    print("=========================")
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Proxy: {CONFIG['HTTPS_PROXY'] or 'None'}")
    print(f"Token: {CONFIG['FIGMA_TOKEN'][:10]}...")
    print(f"SSL Verify: {CONFIG['VERIFY_SSL']}")
    print(f"CA Bundle: {CONFIG['CA_BUNDLE'] or 'System default'}")

    await health_check()
    # await get_file("file_key_here")
    # await get_file_nodes("file_key_here", ["node_id_1", "node_id_2"])
    # await get_file_images("file_key_here", ["node_id_1"], "png")
    # await list_team_projects("team_id_here")


if __name__ == "__main__":
    asyncio.run(main())
