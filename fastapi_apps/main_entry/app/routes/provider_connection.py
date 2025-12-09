"""Provider Connection Health Check Routes.

Exposes provider connection health check endpoints.
Uses provider_api_getters for API token resolution and health checking.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from provider_api_getters import (
    ProviderHealthChecker,
    check_provider_connection,
    PROVIDER_REGISTRY,
)


class ProviderConnectionResponse(BaseModel):
    """Provider connection health check response."""

    provider: str
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: str
    config_used: Optional[Dict[str, Any]] = None


class ProvidersListResponse(BaseModel):
    """List of available providers."""

    providers: List[str]
    count: int
    timestamp: str


class RuntimeOverrideRequest(BaseModel):
    """Request body for runtime proxy/client override testing."""

    proxy: Optional[Dict[str, Any]] = None
    client: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


router = APIRouter()


def get_static_config():
    """Get static config from main module."""
    from app.main import static_config_env
    return static_config_env


@router.get("", response_model=ProvidersListResponse)
async def list_providers() -> ProvidersListResponse:
    """
    List all available providers that can be health-checked.

    Returns a list of provider names that can be passed to the
    /{provider_name} endpoint.
    """
    providers = list(PROVIDER_REGISTRY.keys())
    unique_providers = sorted(set(providers))

    return ProvidersListResponse(
        providers=unique_providers,
        count=len(unique_providers),
        timestamp=datetime.now().isoformat(),
    )


@router.get("/{provider_name}", response_model=ProviderConnectionResponse)
async def check_provider(
    provider_name: str,
    static_config=Depends(get_static_config),
) -> ProviderConnectionResponse:
    """
    Check connection to a specific provider.

    Args:
        provider_name: The name of the provider to check
            (e.g., 'figma', 'github', 'jira', 'postgres', 'redis')

    Returns:
        Connection status including latency, success message or error details,
        and the effective configuration used for the connection test.

    Status values:
        - connected: Successfully connected to the provider
        - error: Failed to connect (check error field for details)
        - not_implemented: Provider is a placeholder (not yet implemented)
    """
    checker = ProviderHealthChecker(static_config)
    result = await checker.check(provider_name)

    return ProviderConnectionResponse(
        provider=result.provider,
        status=result.status,
        latency_ms=result.latency_ms,
        message=result.message,
        error=result.error,
        timestamp=result.timestamp,
        config_used=result.config_used,
    )


@router.post("/{provider_name}", response_model=ProviderConnectionResponse)
async def check_provider_with_override(
    provider_name: str,
    override: RuntimeOverrideRequest,
    static_config=Depends(get_static_config),
) -> ProviderConnectionResponse:
    """
    Check connection to a provider with runtime proxy/client override.

    Useful for testing VPN/proxy configurations without modifying YAML.
    The override is deep-merged with the static config (global + overwrite_root_config).

    Args:
        provider_name: The name of the provider to check
        override: Runtime override for proxy, client, and headers settings

    Example request body:
    ```json
    {
        "proxy": {
            "default_environment": "prod",
            "proxy_urls": {"prod": "http://proxy.internal:8080"},
            "cert_verify": false
        },
        "client": {
            "timeout_seconds": 120.0
        }
    }
    ```

    Returns:
        Connection status with the effective configuration used.
    """
    runtime_override = override.model_dump(exclude_none=True)
    checker = ProviderHealthChecker(static_config, runtime_override=runtime_override)
    result = await checker.check(provider_name)

    return ProviderConnectionResponse(
        provider=result.provider,
        status=result.status,
        latency_ms=result.latency_ms,
        message=result.message,
        error=result.error,
        timestamp=result.timestamp,
        config_used=result.config_used,
    )
