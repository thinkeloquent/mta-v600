"""
Factory functions for creating fetch clients.
"""
from typing import Any, Optional, Union

import httpx

from .types import FetchResponse
from .config import ClientConfig, AuthConfig, TimeoutConfig, DefaultSerializer
from .core.base_client import AsyncFetchClient, SyncFetchClient
from .adapters.rest_adapter import AsyncRestAdapter, SyncRestAdapter


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
