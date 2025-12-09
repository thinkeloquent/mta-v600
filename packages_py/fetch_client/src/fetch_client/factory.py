"""
Factory functions for creating fetch clients.

This module provides factory functions for creating HTTP clients.
For automatic proxy configuration, use create_client_with_dispatcher.
"""
from typing import Any, Optional, Union

import httpx

from .types import FetchResponse
from .config import ClientConfig, AuthConfig, TimeoutConfig, DefaultSerializer
from .core.base_client import AsyncFetchClient, SyncFetchClient
from .adapters.rest_adapter import AsyncRestAdapter, SyncRestAdapter


def _get_proxy_config_from_yaml() -> Optional[dict]:
    """
    Load proxy configuration from ConfigStore (server.*.yaml).
    Returns the proxy section from the YAML config.
    """
    try:
        from static_config import config
        return config.get("proxy")
    except ImportError:
        return None
    except Exception:
        return None


def get_proxy_config() -> dict:
    """
    Get the current proxy configuration for debugging.

    Returns a dictionary with the proxy configuration from YAML,
    or an empty dict if not configured.

    Example:
        from fetch_client import get_proxy_config
        import json
        print(json.dumps(get_proxy_config(), indent=2))
    """
    config = _get_proxy_config_from_yaml()
    return config if config else {}


def print_proxy_config() -> None:
    """
    Print the current proxy configuration for debugging.

    Example:
        from fetch_client import print_proxy_config
        print_proxy_config()
    """
    import json
    config = get_proxy_config()
    print("=== Proxy Configuration (from YAML) ===")
    if config:
        print(json.dumps(config, indent=2, default=str))
    else:
        print("No proxy configuration found in YAML config.")
    print("=" * 40)


def _get_proxy_dispatcher_safe(
    async_client: bool = True,
    verify: Optional[bool] = None,
    cert: Optional[str] = None,
    ca_bundle: Optional[str] = None,
    proxy: Optional[str] = None,
):
    """
    Get proxy dispatcher from fetch_proxy_dispatcher package.
    Configures based on YAML config from ConfigStore.
    Runtime overrides take precedence over YAML config.
    Returns None if the package is not available.

    Args:
        async_client: If True, create async client; if False, create sync client.
        verify: Override SSL verification (True/False). None uses YAML config.
        cert: Override client certificate path. None uses YAML config.
        ca_bundle: Override CA bundle path. None uses YAML config.
        proxy: Override proxy URL (e.g., "http://proxy:8080"). None uses YAML/env config.
    """
    try:
        from fetch_proxy_dispatcher import (
            ProxyDispatcherFactory,
            FactoryConfig,
            ProxyUrlConfig,
            AgentProxyConfig,
        )

        # Load proxy config from YAML (server.*.yaml)
        yaml_config = _get_proxy_config_from_yaml() or {}

        # Apply runtime overrides (override YAML values if provided)
        effective_cert_verify = verify if verify is not None else yaml_config.get("cert_verify")
        effective_cert = cert if cert is not None else yaml_config.get("cert")
        effective_ca_bundle = ca_bundle if ca_bundle is not None else yaml_config.get("ca_bundle")

        if yaml_config or verify is not None or cert is not None or ca_bundle is not None or proxy is not None:
            # Build factory config from YAML with overrides
            # If proxy is explicitly provided, use it as agent_proxy (takes priority)
            agent_proxy_config = None
            if proxy:
                agent_proxy_config = AgentProxyConfig(
                    http_proxy=proxy,
                    https_proxy=proxy,
                )
            elif yaml_config.get("agent_proxy"):
                agent_proxy_config = AgentProxyConfig(
                    http_proxy=yaml_config.get("agent_proxy", {}).get("http_proxy"),
                    https_proxy=yaml_config.get("agent_proxy", {}).get("https_proxy"),
                )

            factory_config = FactoryConfig(
                proxy_urls=ProxyUrlConfig(**yaml_config.get("proxy_urls", {}))
                if yaml_config.get("proxy_urls")
                else None,
                agent_proxy=agent_proxy_config,
                default_environment=yaml_config.get("default_environment"),
                ca_bundle=effective_ca_bundle,
                cert=effective_cert,
                cert_verify=effective_cert_verify,
            )

            factory = ProxyDispatcherFactory(config=factory_config)
            result = factory.get_proxy_dispatcher(
                disable_tls=effective_cert_verify is False,
                async_client=async_client,
            )
            return result.client

        # Fallback to simple API if no YAML config and no overrides
        from fetch_proxy_dispatcher import get_proxy_dispatcher
        result = get_proxy_dispatcher(async_client=async_client)
        return result.client
    except ImportError:
        return None
    except Exception:
        return None


def create_client(
    base_url: str,
    httpx_client: Optional[Union[httpx.AsyncClient, httpx.Client]] = None,
    auth: Optional[AuthConfig] = None,
    timeout: Optional[Union[float, TimeoutConfig]] = None,
    default_headers: Optional[dict[str, str]] = None,
    content_type: str = "application/json",
    serializer: Optional[Any] = None,
) -> Union[AsyncFetchClient, SyncFetchClient]:
    """
    Create a fetch client with the given configuration.

    Args:
        base_url: Base URL for all requests.
        httpx_client: Pre-configured httpx client (AsyncClient or Client).
        auth: Authentication configuration.
        timeout: Request timeout (seconds or TimeoutConfig).
        default_headers: Default headers for all requests.
        content_type: Default content type.
        serializer: Custom JSON serializer/deserializer.

    Returns:
        AsyncFetchClient if httpx_client is AsyncClient, SyncFetchClient otherwise.

    Example:
        # Async client
        async_client = httpx.AsyncClient()
        client = create_client(
            base_url="https://api.example.com",
            httpx_client=async_client,
            auth=AuthConfig(type="bearer", api_key="secret"),
        )

        # Sync client
        sync_client = httpx.Client()
        client = create_client(
            base_url="https://api.example.com",
            httpx_client=sync_client,
        )
    """
    config = ClientConfig(
        base_url=base_url,
        httpx_client=httpx_client,
        auth=auth,
        timeout=timeout,
        headers=default_headers or {},
        content_type=content_type,
    )

    # Determine client type based on httpx client type
    if httpx_client is None or isinstance(httpx_client, httpx.AsyncClient):
        return AsyncFetchClient(config)
    else:
        return SyncFetchClient(config)


def create_client_with_dispatcher(
    base_url: str,
    auth: Optional[AuthConfig] = None,
    timeout: Optional[Union[float, TimeoutConfig]] = None,
    default_headers: Optional[dict[str, str]] = None,
    content_type: str = "application/json",
    serializer: Optional[Any] = None,
    async_client: bool = True,
    verify: Optional[bool] = None,
    cert: Optional[str] = None,
    ca_bundle: Optional[str] = None,
    proxy: Optional[str] = None,
) -> Union[AsyncFetchClient, SyncFetchClient]:
    """
    Create a fetch client with automatic proxy dispatcher configuration.

    Uses fetch_proxy_dispatcher to automatically configure the appropriate
    httpx client based on environment (DEV, QA, STAGE, PROD).

    Proxy configuration is loaded from server.*.yaml (via ConfigStore):
    ```yaml
    proxy:
      default_environment: "dev"
      proxy_urls:
        PROD: "http://proxy.company.com:8080"
        QA: "http://qa-proxy.company.com:8080"
      cert_verify: false
      agent_proxy:
        http_proxy: null
        https_proxy: null
    ```

    Args:
        base_url: Base URL for all requests.
        auth: Authentication configuration.
        timeout: Request timeout (seconds or TimeoutConfig).
        default_headers: Default headers for all requests.
        content_type: Default content type.
        serializer: Custom JSON serializer/deserializer.
        async_client: If True, create async client; if False, create sync client.
        verify: Override SSL verification (True/False). None uses YAML config.
        cert: Override client certificate path. None uses YAML config.
        ca_bundle: Override CA bundle path. None uses YAML config.
        proxy: Override proxy URL (e.g., "http://proxy:8080"). None uses YAML/env config.

    Returns:
        AsyncFetchClient or SyncFetchClient with proxy-configured httpx client.

    Example:
        # Async client with automatic proxy configuration (uses YAML config)
        client = create_client_with_dispatcher(
            base_url="https://api.example.com",
            auth=AuthConfig(type="bearer", api_key="secret"),
        )
        async with client:
            response = await client.get("/users")

        # Async client with explicit proxy override
        client = create_client_with_dispatcher(
            base_url="https://api.example.com",
            auth=AuthConfig(type="bearer", api_key="secret"),
            proxy="http://proxy.company.com:8080",
            verify=False,
        )

        # Sync client with automatic proxy configuration
        client = create_client_with_dispatcher(
            base_url="https://api.example.com",
            async_client=False,
        )
        with client:
            response = client.get("/users")

        # Debug: Print current proxy config
        from fetch_client import print_proxy_config
        print_proxy_config()
    """
    # Try to get proxy-configured httpx client with optional overrides
    httpx_client = _get_proxy_dispatcher_safe(
        async_client=async_client,
        verify=verify,
        cert=cert,
        ca_bundle=ca_bundle,
        proxy=proxy,
    )

    return create_client(
        base_url=base_url,
        httpx_client=httpx_client,
        auth=auth,
        timeout=timeout,
        default_headers=default_headers,
        content_type=content_type,
        serializer=serializer,
    )


def create_async_client(
    base_url: str,
    httpx_client: Optional[httpx.AsyncClient] = None,
    auth: Optional[AuthConfig] = None,
    timeout: Optional[Union[float, TimeoutConfig]] = None,
    default_headers: Optional[dict[str, str]] = None,
    content_type: str = "application/json",
    serializer: Optional[Any] = None,
) -> AsyncFetchClient:
    """
    Create an async fetch client.

    Args:
        base_url: Base URL for all requests.
        httpx_client: Pre-configured httpx.AsyncClient.
        auth: Authentication configuration.
        timeout: Request timeout (seconds or TimeoutConfig).
        default_headers: Default headers for all requests.
        content_type: Default content type.
        serializer: Custom JSON serializer/deserializer.

    Returns:
        AsyncFetchClient instance.
    """
    config = ClientConfig(
        base_url=base_url,
        httpx_client=httpx_client,
        auth=auth,
        timeout=timeout,
        headers=default_headers or {},
        content_type=content_type,
    )
    return AsyncFetchClient(config)


def create_sync_client(
    base_url: str,
    httpx_client: Optional[httpx.Client] = None,
    auth: Optional[AuthConfig] = None,
    timeout: Optional[Union[float, TimeoutConfig]] = None,
    default_headers: Optional[dict[str, str]] = None,
    content_type: str = "application/json",
    serializer: Optional[Any] = None,
) -> SyncFetchClient:
    """
    Create a sync fetch client.

    Args:
        base_url: Base URL for all requests.
        httpx_client: Pre-configured httpx.Client.
        auth: Authentication configuration.
        timeout: Request timeout (seconds or TimeoutConfig).
        default_headers: Default headers for all requests.
        content_type: Default content type.
        serializer: Custom JSON serializer/deserializer.

    Returns:
        SyncFetchClient instance.
    """
    config = ClientConfig(
        base_url=base_url,
        httpx_client=httpx_client,
        auth=auth,
        timeout=timeout,
        headers=default_headers or {},
        content_type=content_type,
    )
    return SyncFetchClient(config)


def create_rest_adapter(
    client: Union[AsyncFetchClient, SyncFetchClient],
) -> Union[AsyncRestAdapter, SyncRestAdapter]:
    """
    Create a REST adapter for an existing client.

    Args:
        client: Fetch client to wrap.

    Returns:
        AsyncRestAdapter or SyncRestAdapter depending on client type.
    """
    if isinstance(client, AsyncFetchClient):
        return AsyncRestAdapter(client)
    else:
        return SyncRestAdapter(client)
