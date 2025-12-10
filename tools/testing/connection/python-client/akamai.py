#!/usr/bin/env python3
"""
Akamai Edge API - Python Client Integration Test

Authentication: EdgeGrid (signature-based)
Base URL: https://<host>.luna.akamaiapis.net
Health Endpoint: GET /-/client-api/active-grants/implicit

Uses internal packages:
  - fetch_client: HTTP client with auth support
  - provider_api_getters: API key resolution (EdgeGrid credentials)
  - static_config: YAML configuration loading

API Documentation:
  https://techdocs.akamai.com/developer/docs/authenticate-with-edgegrid

EdgeGrid Authentication:
  Akamai uses signature-based authentication. Each request must include
  an Authorization header with a signature computed from:
  - client_token, client_secret, access_token
  - Request method, path, headers, and body

Note: This test file uses the akamai-edgegrid package for signature generation.
Install with: pip install edgegrid-python
"""
import asyncio
import json
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
from provider_api_getters import AkamaiApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = AkamaiApiToken(static_config)
api_key_result = provider.get_api_key()
credentials = provider.get_credentials()

CONFIG = {
    # From provider_api_getters (EdgeGrid credentials)
    "CLIENT_TOKEN": credentials.client_token,
    "CLIENT_SECRET": credentials.client_secret,
    "ACCESS_TOKEN": credentials.access_token,
    "HOST": credentials.host,
    "AUTH_TYPE": api_key_result.auth_type,
    "HAS_CREDENTIALS": api_key_result.has_credentials,

    # Base URL (derived from host)
    "BASE_URL": provider.get_base_url(),

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
# EdgeGrid Authentication Helper
# ============================================================================
def get_edgegrid_auth():
    """
    Create EdgeGrid authentication object.

    Requires: pip install edgegrid-python
    """
    try:
        from akamai.edgegrid import EdgeGridAuth
    except ImportError:
        print("Error: edgegrid-python package not installed.")
        print("Install with: pip install edgegrid-python")
        return None

    if not CONFIG["HAS_CREDENTIALS"]:
        print("Error: EdgeGrid credentials not found.")
        print("Set AKAMAI_CLIENT_TOKEN, AKAMAI_CLIENT_SECRET, AKAMAI_ACCESS_TOKEN, AKAMAI_HOST")
        print("Or create ~/.edgerc file with [default] section.")
        return None

    return EdgeGridAuth(
        client_token=CONFIG["CLIENT_TOKEN"],
        client_secret=CONFIG["CLIENT_SECRET"],
        access_token=CONFIG["ACCESS_TOKEN"],
    )


def create_akamai_client():
    """
    Create an Akamai API client.

    Note: EdgeGrid auth requires signing each request, so we use
    a custom auth approach with the requests library directly.
    """
    return create_client_with_dispatcher(
        base_url=CONFIG["BASE_URL"],
        auth=AuthConfig(
            type="custom",  # EdgeGrid requires custom signing per request
            raw_api_key="",  # Not used directly, signing handled separately
            header_name="Authorization",
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
    print("\n=== Akamai Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("akamai")

    print(f"Status: {result.status}")
    if result.latency_ms:
        print(f"Latency: {result.latency_ms:.2f}ms")
    if result.message:
        print(f"Message: {result.message}")
    if result.error:
        print(f"Error: {result.error}")

    return {"success": result.status == "connected", "result": result}


# ============================================================================
# Sample API Calls using requests with EdgeGrid auth
# ============================================================================
def get_active_grants():
    """Get active API client grants."""
    print("\n=== Get Active Grants ===\n")

    try:
        import requests
    except ImportError:
        print("Error: requests package not installed.")
        return {"success": False, "error": "requests not installed"}

    auth = get_edgegrid_auth()
    if not auth:
        return {"success": False, "error": "No EdgeGrid auth"}

    url = f"{CONFIG['BASE_URL']}/-/client-api/active-grants/implicit"

    try:
        response = requests.get(url, auth=auth, verify=CONFIG["SSL_VERIFY"])
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return {"success": response.ok, "data": response.json()}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


def get_contracts():
    """Get list of contracts."""
    print("\n=== Get Contracts ===\n")

    try:
        import requests
    except ImportError:
        print("Error: requests package not installed.")
        return {"success": False, "error": "requests not installed"}

    auth = get_edgegrid_auth()
    if not auth:
        return {"success": False, "error": "No EdgeGrid auth"}

    url = f"{CONFIG['BASE_URL']}/papi/v1/contracts"

    try:
        response = requests.get(url, auth=auth, verify=CONFIG["SSL_VERIFY"])
        print(f"Status: {response.status_code}")
        if response.ok:
            data = response.json()
            contracts = data.get("contracts", {}).get("items", [])
            print(f"Found {len(contracts)} contracts")
            for contract in contracts[:5]:
                print(f"  - {contract.get('contractId')}: {contract.get('contractTypeName')}")
        else:
            print(f"Response: {response.text}")
        return {"success": response.ok, "data": response.json() if response.ok else None}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


def get_groups():
    """Get list of groups."""
    print("\n=== Get Groups ===\n")

    try:
        import requests
    except ImportError:
        print("Error: requests package not installed.")
        return {"success": False, "error": "requests not installed"}

    auth = get_edgegrid_auth()
    if not auth:
        return {"success": False, "error": "No EdgeGrid auth"}

    url = f"{CONFIG['BASE_URL']}/papi/v1/groups"

    try:
        response = requests.get(url, auth=auth, verify=CONFIG["SSL_VERIFY"])
        print(f"Status: {response.status_code}")
        if response.ok:
            data = response.json()
            groups = data.get("groups", {}).get("items", [])
            print(f"Found {len(groups)} groups")
            for group in groups[:5]:
                print(f"  - {group.get('groupId')}: {group.get('groupName')}")
        else:
            print(f"Response: {response.text}")
        return {"success": response.ok, "data": response.json() if response.ok else None}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


def get_properties(contract_id: str, group_id: str):
    """Get list of properties."""
    print(f"\n=== Get Properties (contract: {contract_id}, group: {group_id}) ===\n")

    try:
        import requests
    except ImportError:
        print("Error: requests package not installed.")
        return {"success": False, "error": "requests not installed"}

    auth = get_edgegrid_auth()
    if not auth:
        return {"success": False, "error": "No EdgeGrid auth"}

    url = f"{CONFIG['BASE_URL']}/papi/v1/properties"
    params = {"contractId": contract_id, "groupId": group_id}

    try:
        response = requests.get(url, auth=auth, params=params, verify=CONFIG["SSL_VERIFY"])
        print(f"Status: {response.status_code}")
        if response.ok:
            data = response.json()
            properties = data.get("properties", {}).get("items", [])
            print(f"Found {len(properties)} properties")
            for prop in properties[:10]:
                print(f"  - {prop.get('propertyId')}: {prop.get('propertyName')}")
        else:
            print(f"Response: {response.text}")
        return {"success": response.ok, "data": response.json() if response.ok else None}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


def purge_cache(hostname: str, paths: list[str]):
    """Purge cache for specified paths."""
    print(f"\n=== Purge Cache (hostname: {hostname}) ===\n")

    try:
        import requests
    except ImportError:
        print("Error: requests package not installed.")
        return {"success": False, "error": "requests not installed"}

    auth = get_edgegrid_auth()
    if not auth:
        return {"success": False, "error": "No EdgeGrid auth"}

    url = f"{CONFIG['BASE_URL']}/ccu/v3/invalidate/url/production"
    payload = {
        "hostname": hostname,
        "objects": paths,
    }

    try:
        response = requests.post(
            url,
            auth=auth,
            json=payload,
            headers={"Content-Type": "application/json"},
            verify=CONFIG["SSL_VERIFY"]
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return {"success": response.ok, "data": response.json()}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    print("Akamai Edge API Connection Test (Python Client Integration)")
    print("=" * 60)
    print(f"Base URL: {CONFIG['BASE_URL']}")
    print(f"Host: {CONFIG['HOST'] or 'Not set'}")
    print(f"Client Token: {CONFIG['CLIENT_TOKEN'][:10] + '...' if CONFIG['CLIENT_TOKEN'] else 'Not set'}")
    print(f"Access Token: {CONFIG['ACCESS_TOKEN'][:10] + '...' if CONFIG['ACCESS_TOKEN'] else 'Not set'}")
    print(f"Auth Type: {CONFIG['AUTH_TYPE']}")
    print(f"Has Credentials: {CONFIG['HAS_CREDENTIALS']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests (requires edgegrid-python package):
    # get_active_grants()
    # get_contracts()
    # get_groups()
    # get_properties("ctr_XXX", "grp_XXX")
    # purge_cache("www.example.com", ["/path/to/purge"])


if __name__ == "__main__":
    asyncio.run(main())
