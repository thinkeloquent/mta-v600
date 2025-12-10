#!/usr/bin/env python3
"""
Sonar API - Python Client Integration Test

Authentication: Bearer Token
Base URL: https://sonarcloud.io or https://your-sonar.example.com (SonarQube)
Health Endpoint: GET /api/authentication/validate

Uses internal packages:
  - fetch_client: HTTP client with auth support
  - provider_api_getters: API key resolution
  - static_config: YAML configuration loading

API Documentation:
  SonarCloud: https://sonarcloud.io/web_api
  SonarQube: https://docs.sonarqube.org/latest/extension-guide/web-api/
"""
import asyncio
import os
import sys
from pathlib import Path

# ============================================================================
# Project Setup
# ============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "app_static_config_yaml" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "provider_api_getters" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "fetch_client" / "src"))

# Load static config
from static_config import load_yaml_config, config as static_config
config_dir = PROJECT_ROOT / "common" / "config"
load_yaml_config(config_dir=config_dir)

# Import internal packages
from fetch_client import create_client_with_dispatcher, AuthConfig
from provider_api_getters import SonarApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = SonarApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters
    "SONAR_TOKEN": api_key_result.api_key,
    "AUTH_TYPE": api_key_result.auth_type,

    # Base URL (from provider or override)
    "BASE_URL": provider.get_base_url() or os.getenv("SONAR_BASE_URL", "https://sonarcloud.io"),

    # SSL/TLS Configuration (runtime override, or None to use YAML config)
    "SSL_VERIFY": False,  # Set to None to use YAML config
    "CERT": os.getenv("CERT"),
    "CA_BUNDLE": os.getenv("CA_BUNDLE"),

    # Proxy Configuration (set to override YAML/environment config)
    "PROXY": os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"),

    # Debug
    "DEBUG": os.getenv("DEBUG", "true").lower() not in ("false", "0"),
}


# ============================================================================
# Client Factory
# ============================================================================
def create_sonar_client():
    """Create a Sonar API client with standard configuration."""
    return create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(
            type="bearer",
            raw_api_key=CONFIG["SONAR_TOKEN"],
        ),
        default_headers={"Accept": "application/json"},
        verify=CONFIG["SSL_VERIFY"],
        cert=CONFIG["CERT"],
        ca_bundle=CONFIG["CA_BUNDLE"],
        proxy=CONFIG["PROXY"],
    )


# ============================================================================
# Health Check
# ============================================================================
async def health_check():
    """Run health check using ProviderHealthChecker."""
    print("\n=== Sonar Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("sonar")

    print(f"Status: {result.status}")
    if result.latency_ms:
        print(f"Latency: {result.latency_ms:.2f}ms")
    if result.message:
        print(f"Message: {result.message}")
    if result.error:
        print(f"Error: {result.error}")

    return {"success": result.status == "connected", "result": result}


# ============================================================================
# Sample API Calls using fetch-client
# ============================================================================
async def validate_auth():
    """Validate authentication."""
    print("\n=== Validate Authentication ===\n")

    async with create_sonar_client() as client:
        response = await client.get("/api/authentication/validate")

        print(f"Status: {response.status}")
        print(f"Response: {response.data}")

        return {"success": response.ok, "data": response.data}


async def get_system_status():
    """Get system status (works without authentication)."""
    print("\n=== Get System Status ===\n")

    async with create_sonar_client() as client:
        response = await client.get("/api/system/status")

        print(f"Status: {response.status}")
        print(f"Response: {response.data}")

        return {"success": response.ok, "data": response.data}


async def list_projects(organization: str = None, page_size: int = 10):
    """List projects (SonarCloud requires organization parameter)."""
    print(f"\n=== List Projects (page_size: {page_size}) ===\n")

    params = {"ps": page_size}
    if organization:
        params["organization"] = organization

    async with create_sonar_client() as client:
        response = await client.get("/api/projects/search", params=params)

        print(f"Status: {response.status}")
        if response.ok and response.data:
            components = response.data.get("components", [])
            paging = response.data.get("paging", {})
            print(f"Total: {paging.get('total', 0)}")
            for project in components[:10]:
                print(f"  - {project.get('key')}: {project.get('name')}")
        else:
            print(f"Response: {response.data}")

        return {"success": response.ok, "data": response.data}


async def get_project_status(project_key: str):
    """Get project quality gate status."""
    print(f"\n=== Get Project Status: {project_key} ===\n")

    async with create_sonar_client() as client:
        response = await client.get(
            "/api/qualitygates/project_status",
            params={"projectKey": project_key}
        )

        print(f"Status: {response.status}")
        if response.ok and response.data:
            project_status = response.data.get("projectStatus", {})
            print(f"Quality Gate: {project_status.get('status')}")
            conditions = project_status.get("conditions", [])
            for condition in conditions[:5]:
                print(f"  - {condition.get('metricKey')}: {condition.get('status')} ({condition.get('actualValue')})")
        else:
            print(f"Response: {response.data}")

        return {"success": response.ok, "data": response.data}


async def get_project_metrics(project_key: str):
    """Get project metrics."""
    print(f"\n=== Get Project Metrics: {project_key} ===\n")

    metric_keys = "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density"

    async with create_sonar_client() as client:
        response = await client.get(
            "/api/measures/component",
            params={
                "component": project_key,
                "metricKeys": metric_keys
            }
        )

        print(f"Status: {response.status}")
        if response.ok and response.data:
            component = response.data.get("component", {})
            measures = component.get("measures", [])
            print(f"Project: {component.get('name')}")
            for measure in measures:
                print(f"  - {measure.get('metric')}: {measure.get('value')}")
        else:
            print(f"Response: {response.data}")

        return {"success": response.ok, "data": response.data}


async def list_issues(project_key: str = None, page_size: int = 10):
    """List issues (optionally filtered by project)."""
    print(f"\n=== List Issues (page_size: {page_size}) ===\n")

    params = {"ps": page_size, "resolved": "false"}
    if project_key:
        params["componentKeys"] = project_key

    async with create_sonar_client() as client:
        response = await client.get("/api/issues/search", params=params)

        print(f"Status: {response.status}")
        if response.ok and response.data:
            issues = response.data.get("issues", [])
            paging = response.data.get("paging", {})
            print(f"Total: {paging.get('total', 0)}")
            for issue in issues[:10]:
                severity = issue.get("severity", "UNKNOWN")
                issue_type = issue.get("type", "UNKNOWN")
                message = (issue.get("message", "")[:50] + "...") if len(issue.get("message", "")) > 50 else issue.get("message", "")
                print(f"  - [{severity}] {issue_type}: {message}")
        else:
            print(f"Response: {response.data}")

        return {"success": response.ok, "data": response.data}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    print("Sonar API Connection Test (Python Client Integration)")
    print("=" * 55)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Token: {CONFIG['SONAR_TOKEN'][:10] + '...' if CONFIG['SONAR_TOKEN'] else 'Not set'}")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await validate_auth()
    # await get_system_status()
    # await list_projects(organization="your-org")
    # await get_project_status("your-project-key")
    # await get_project_metrics("your-project-key")
    # await list_issues()


if __name__ == "__main__":
    asyncio.run(main())
