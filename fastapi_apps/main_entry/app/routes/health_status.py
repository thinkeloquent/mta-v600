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
    - ProviderHealthChecker for comprehensive connectivity check and config resolution
    - static_config for YAML configuration

    Returns:
    dict: Health status with provider config and optional connectivity check
    """
    from provider_api_getters import ProviderHealthChecker
    
    # Initialize checker with static config
    checker = ProviderHealthChecker(static_config)
    
    # Perform health check (which also resolves config)
    result = await checker.check("sonar")
    
    # Extract resolved configuration from the result
    config_used = result.config_used or {}
    network_config = config_used.get("network") or {}
    client_config = config_used.get("client") or {}
    
    # Build flattened config for display (matching previous format)
    display_config = {
        "base_url": config_used.get("base_url"),
        "has_credentials": result.status not in ("not_implemented", "error"), # Approximation if not exposed directly
        "auth_type": config_used.get("auth_type"),
        "network": {
            "proxy_url": config_used.get("proxy_url"), # Direct override
            "cert_verify": network_config.get("cert_verify"),
            # Add other network details verified to be working
            "agent_proxy": network_config.get("agent_proxy"),
            "proxy_urls": network_config.get("proxy_urls"),
        },
    }

    # Build status response
    status = {
        "status": "healthy" if result.status == "connected" else "degraded",
        "provider": "sonar",
        "config": display_config,
        "connectivity": {
            "connected": result.status == "connected",
            "status": result.status,
            "error": result.error,
            "latency_ms": result.latency_ms,
        }
    }

    return status
