"""Health status endpoint with full internal package integration.

Demonstrates integration with:
- static_config for YAML configuration
- provider_api_getters for API token resolution
- fetch_client for HTTP requests
- fetch_proxy_dispatcher for proxy configuration
"""

from fastapi import APIRouter

from static_config import config as static_config
from fetch_client import create_client_with_dispatcher, AuthConfig
from provider_api_getters import SonarApiToken

router = APIRouter()


@router.get("/status")
async def health_status():
    """
    Health status endpoint demonstrating internal package integration.

    Uses:
    - static_config for YAML configuration
    - provider_api_getters for API token resolution
    - fetch_client for HTTP requests
    - fetch_proxy_dispatcher for proxy configuration

    Returns:
        dict: Health status with provider config and optional connectivity check
    """
    # Initialize provider from static config
    provider = SonarApiToken(static_config)
    api_key_result = provider.get_api_key()
    network_config = provider.get_network_config() or {}
    base_url = provider.get_base_url()

    # Build status response
    status = {
        "status": "healthy",
        "provider": "sonar",
        "config": {
            "base_url": base_url,
            "has_credentials": api_key_result.has_credentials,
            "auth_type": api_key_result.auth_type,
            "network": {
                "proxy_url": network_config.get("proxy_url"),
                "cert_verify": network_config.get("cert_verify"),
            },
        },
    }

    # Make actual API call to verify connectivity
    if api_key_result.has_credentials and base_url:
        try:
            client = create_client_with_dispatcher(
                base_url=base_url,
                auth=AuthConfig(
                    type=api_key_result.auth_type,
                    raw_api_key=api_key_result.raw_api_key,
                    header_name=api_key_result.header_name,
                ),
                default_headers={"Accept": "application/json"},
                verify=network_config.get("cert_verify", False),
                proxy_url=provider.get_proxy_url(),
            )
            async with client:
                response = await client.get("/api/authentication/validate")
                status["connectivity"] = {
                    "connected": response["ok"],
                    "status_code": response["status"],
                }
        except Exception as e:
            status["connectivity"] = {
                "connected": False,
                "error": str(e),
            }
    else:
        status["connectivity"] = {
            "connected": False,
            "error": "Missing credentials or base_url",
        }

    return status
