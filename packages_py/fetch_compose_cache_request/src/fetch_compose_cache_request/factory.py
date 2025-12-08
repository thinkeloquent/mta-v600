"""
Factory functions for creating cache request transports.
"""
from typing import Callable, List, Optional

import httpx

from cache_request import (
    IdempotencyConfig,
    SingleflightConfig,
    CacheRequestStore,
    SingleflightStore,
)

from .transport import CacheRequestTransport, SyncCacheRequestTransport


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
            lambda inner: CacheRequestTransport(inner),
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


def create_cache_request_transport(
    inner: Optional[httpx.AsyncBaseTransport] = None,
    *,
    enable_idempotency: bool = True,
    enable_singleflight: bool = True,
    idempotency_config: Optional[IdempotencyConfig] = None,
    singleflight_config: Optional[SingleflightConfig] = None,
    idempotency_store: Optional[CacheRequestStore] = None,
    singleflight_store: Optional[SingleflightStore] = None,
    on_idempotency_key_generated: Optional[Callable[[str, str, str], None]] = None,
    on_request_coalesced: Optional[Callable[[str, int], None]] = None,
) -> CacheRequestTransport:
    """
    Create a cache request transport.

    Args:
        inner: The inner transport (defaults to AsyncHTTPTransport)
        enable_idempotency: Enable idempotency key management
        enable_singleflight: Enable request coalescing
        idempotency_config: Idempotency configuration
        singleflight_config: Singleflight configuration
        idempotency_store: Custom store for idempotency
        singleflight_store: Custom store for singleflight
        on_idempotency_key_generated: Callback when idempotency key is generated
        on_request_coalesced: Callback when request is coalesced

    Returns:
        CacheRequestTransport instance
    """
    if inner is None:
        inner = httpx.AsyncHTTPTransport()

    return CacheRequestTransport(
        inner,
        enable_idempotency=enable_idempotency,
        enable_singleflight=enable_singleflight,
        idempotency_config=idempotency_config,
        singleflight_config=singleflight_config,
        idempotency_store=idempotency_store,
        singleflight_store=singleflight_store,
        on_idempotency_key_generated=on_idempotency_key_generated,
        on_request_coalesced=on_request_coalesced,
    )


def create_cache_request_sync_transport(
    inner: Optional[httpx.BaseTransport] = None,
    *,
    enable_idempotency: bool = True,
    idempotency_config: Optional[IdempotencyConfig] = None,
    on_idempotency_key_generated: Optional[Callable[[str, str, str], None]] = None,
) -> SyncCacheRequestTransport:
    """
    Create a sync cache request transport.

    Args:
        inner: The inner transport (defaults to HTTPTransport)
        enable_idempotency: Enable idempotency key management
        idempotency_config: Idempotency configuration
        on_idempotency_key_generated: Callback when idempotency key is generated

    Returns:
        SyncCacheRequestTransport instance
    """
    if inner is None:
        inner = httpx.HTTPTransport()

    return SyncCacheRequestTransport(
        inner,
        enable_idempotency=enable_idempotency,
        idempotency_config=idempotency_config,
        on_idempotency_key_generated=on_idempotency_key_generated,
    )


def create_cache_request_client(
    *,
    enable_idempotency: bool = True,
    enable_singleflight: bool = True,
    idempotency_config: Optional[IdempotencyConfig] = None,
    singleflight_config: Optional[SingleflightConfig] = None,
    base_url: Optional[str] = None,
    **client_kwargs,
) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient with cache request capabilities.

    Args:
        enable_idempotency: Enable idempotency key management
        enable_singleflight: Enable request coalescing
        idempotency_config: Idempotency configuration
        singleflight_config: Singleflight configuration
        base_url: Base URL for the client
        **client_kwargs: Additional arguments for httpx.AsyncClient

    Returns:
        AsyncClient with cache request transport
    """
    transport = create_cache_request_transport(
        enable_idempotency=enable_idempotency,
        enable_singleflight=enable_singleflight,
        idempotency_config=idempotency_config,
        singleflight_config=singleflight_config,
    )

    return httpx.AsyncClient(
        transport=transport,
        base_url=base_url or "",
        **client_kwargs,
    )


def create_cache_request_sync_client(
    *,
    enable_idempotency: bool = True,
    idempotency_config: Optional[IdempotencyConfig] = None,
    base_url: Optional[str] = None,
    **client_kwargs,
) -> httpx.Client:
    """
    Create an httpx.Client with cache request capabilities.

    Args:
        enable_idempotency: Enable idempotency key management
        idempotency_config: Idempotency configuration
        base_url: Base URL for the client
        **client_kwargs: Additional arguments for httpx.Client

    Returns:
        Client with cache request transport
    """
    transport = create_cache_request_sync_transport(
        enable_idempotency=enable_idempotency,
        idempotency_config=idempotency_config,
    )

    return httpx.Client(
        transport=transport,
        base_url=base_url or "",
        **client_kwargs,
    )
