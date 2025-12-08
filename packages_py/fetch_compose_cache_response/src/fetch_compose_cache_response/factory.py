"""
Factory functions for creating cache response transports.
"""
from typing import Callable, Optional

import httpx

from cache_response import (
    CacheResponseConfig,
    CacheResponseStore,
    CacheFreshness,
)

from .transport import CacheResponseTransport, SyncCacheResponseTransport


def compose_transport(
    base: httpx.AsyncBaseTransport,
    *wrappers: Callable[[httpx.AsyncBaseTransport], httpx.AsyncBaseTransport],
) -> httpx.AsyncBaseTransport:
    """
    Compose multiple transport wrappers together.

    Args:
        base: The base transport
        wrappers: Transport wrapper functions to apply

    Returns:
        Composed transport

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = compose_transport(
            base,
            lambda inner: CacheResponseTransport(inner),
            lambda inner: RateLimitTransport(inner, max_per_second=10),
        )
    """
    transport = base
    for wrapper in wrappers:
        transport = wrapper(transport)
    return transport


def compose_sync_transport(
    base: httpx.BaseTransport,
    *wrappers: Callable[[httpx.BaseTransport], httpx.BaseTransport],
) -> httpx.BaseTransport:
    """
    Compose multiple sync transport wrappers together.

    Args:
        base: The base transport
        wrappers: Transport wrapper functions to apply

    Returns:
        Composed transport
    """
    transport = base
    for wrapper in wrappers:
        transport = wrapper(transport)
    return transport


def create_cache_response_transport(
    inner: Optional[httpx.AsyncBaseTransport] = None,
    *,
    config: Optional[CacheResponseConfig] = None,
    store: Optional[CacheResponseStore] = None,
    enable_background_revalidation: bool = True,
    on_cache_hit: Optional[Callable[[str, CacheFreshness], None]] = None,
    on_cache_miss: Optional[Callable[[str], None]] = None,
    on_cache_store: Optional[Callable[[str, int, float], None]] = None,
    on_revalidated: Optional[Callable[[str], None]] = None,
) -> CacheResponseTransport:
    """
    Create a cache response transport.

    Args:
        inner: The inner transport (defaults to AsyncHTTPTransport)
        config: Cache configuration
        store: Custom cache store
        enable_background_revalidation: Enable stale-while-revalidate
        on_cache_hit: Callback when cache hit occurs
        on_cache_miss: Callback when cache miss occurs
        on_cache_store: Callback when response is cached
        on_revalidated: Callback when conditional request results in 304

    Returns:
        CacheResponseTransport instance
    """
    if inner is None:
        inner = httpx.AsyncHTTPTransport()

    return CacheResponseTransport(
        inner,
        config=config,
        store=store,
        enable_background_revalidation=enable_background_revalidation,
        on_cache_hit=on_cache_hit,
        on_cache_miss=on_cache_miss,
        on_cache_store=on_cache_store,
        on_revalidated=on_revalidated,
    )


def create_cache_response_sync_transport(
    inner: Optional[httpx.BaseTransport] = None,
    *,
    config: Optional[CacheResponseConfig] = None,
    on_cache_hit: Optional[Callable[[str, str], None]] = None,
    on_cache_miss: Optional[Callable[[str], None]] = None,
    on_cache_store: Optional[Callable[[str, int, float], None]] = None,
) -> SyncCacheResponseTransport:
    """
    Create a sync cache response transport.

    Args:
        inner: The inner transport (defaults to HTTPTransport)
        config: Cache configuration
        on_cache_hit: Callback when cache hit occurs
        on_cache_miss: Callback when cache miss occurs
        on_cache_store: Callback when response is cached

    Returns:
        SyncCacheResponseTransport instance
    """
    if inner is None:
        inner = httpx.HTTPTransport()

    return SyncCacheResponseTransport(
        inner,
        config=config,
        on_cache_hit=on_cache_hit,
        on_cache_miss=on_cache_miss,
        on_cache_store=on_cache_store,
    )


def create_cache_response_client(
    *,
    config: Optional[CacheResponseConfig] = None,
    store: Optional[CacheResponseStore] = None,
    enable_background_revalidation: bool = True,
    base_url: Optional[str] = None,
    **client_kwargs,
) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient with cache response capabilities.

    Args:
        config: Cache configuration
        store: Custom cache store
        enable_background_revalidation: Enable stale-while-revalidate
        base_url: Base URL for the client
        **client_kwargs: Additional arguments for httpx.AsyncClient

    Returns:
        AsyncClient with cache response transport
    """
    transport = create_cache_response_transport(
        config=config,
        store=store,
        enable_background_revalidation=enable_background_revalidation,
    )

    return httpx.AsyncClient(
        transport=transport,
        base_url=base_url or "",
        **client_kwargs,
    )


def create_cache_response_sync_client(
    *,
    config: Optional[CacheResponseConfig] = None,
    base_url: Optional[str] = None,
    **client_kwargs,
) -> httpx.Client:
    """
    Create an httpx.Client with cache response capabilities.

    Args:
        config: Cache configuration
        base_url: Base URL for the client
        **client_kwargs: Additional arguments for httpx.Client

    Returns:
        Client with cache response transport
    """
    transport = create_cache_response_sync_transport(config=config)

    return httpx.Client(
        transport=transport,
        base_url=base_url or "",
        **client_kwargs,
    )
