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
    # Proxy overrides via query params
    proxy_env: Optional[str] = None,
    proxy_url: Optional[str] = None,
    cert_verify: Optional[bool] = None,
    ca_bundle: Optional[str] = None,
    http_proxy: Optional[str] = None,
    https_proxy: Optional[str] = None,
    # Client overrides
    timeout_seconds: Optional[float] = None,
    timeout_ms: Optional[int] = None,
) -> ProviderConnectionResponse:
    """
    Check connection to a specific provider.

    Args:
        provider_name: The name of the provider to check
            (e.g., 'figma', 'github', 'jira', 'postgres', 'redis')

    Query Parameters (proxy overrides):
        proxy_env: Override default_environment (e.g., 'prod', 'dev')
        proxy_url: Override proxy URL for the current environment
        cert_verify: Override SSL certificate verification (true/false)
        ca_bundle: Override CA bundle path
        http_proxy: Override HTTP agent proxy
        https_proxy: Override HTTPS agent proxy

    Query Parameters (client overrides):
        timeout_seconds: Override request timeout in seconds
        timeout_ms: Override request timeout in milliseconds

    Returns:
        Connection status including latency, success message or error details,
        and the effective configuration used for the connection test.

    Status values:
        - connected: Successfully connected to the provider
        - error: Failed to connect (check error field for details)
        - not_implemented: Provider is a placeholder (not yet implemented)

    Examples:
        /healthz/providers/connection/gemini?proxy_env=prod&proxy_url=http://proxy:8080
        /healthz/providers/connection/jira?cert_verify=false&timeout_seconds=120
        /healthz/providers/connection/github?http_proxy=http://squid:3128&https_proxy=http://squid:3128
    """
    # Build runtime override from query params
    runtime_override: Dict[str, Any] = {}

    # Proxy overrides
    proxy_override: Dict[str, Any] = {}
    if proxy_env is not None:
        proxy_override["default_environment"] = proxy_env
    if proxy_url is not None:
        env_key = proxy_env or "default"
        proxy_override["proxy_urls"] = {env_key: proxy_url}
    if cert_verify is not None:
        proxy_override["cert_verify"] = cert_verify
    if ca_bundle is not None:
        proxy_override["ca_bundle"] = ca_bundle
    if http_proxy is not None or https_proxy is not None:
        proxy_override["agent_proxy"] = {}
        if http_proxy is not None:
            proxy_override["agent_proxy"]["http_proxy"] = http_proxy
        if https_proxy is not None:
            proxy_override["agent_proxy"]["https_proxy"] = https_proxy

    if proxy_override:
        runtime_override["proxy"] = proxy_override

    # Client overrides
    client_override: Dict[str, Any] = {}
    if timeout_seconds is not None:
        client_override["timeout_seconds"] = timeout_seconds
    if timeout_ms is not None:
        client_override["timeout_ms"] = timeout_ms

    if client_override:
        runtime_override["client"] = client_override

    # Create checker with optional runtime override
    checker = ProviderHealthChecker(
        static_config,
        runtime_override=runtime_override if runtime_override else None
    )
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
