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


class ProvidersListResponse(BaseModel):
    """List of available providers."""

    providers: List[str]
    count: int
    timestamp: str


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
        Connection status including latency, success message or error details.

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
    )
