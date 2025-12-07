"""
Factory functions for DNS cache transport
"""
from typing import Optional, Callable, Any

import httpx

from cache_dsn import (
    DnsCacheResolver,
    DnsCacheConfig,
    DnsCacheStore,
    LoadBalanceStrategy,
    create_memory_store,
)
from .transport import DnsCacheTransport, SyncDnsCacheTransport


def compose_transport(
    base: httpx.AsyncBaseTransport,
    *wrappers: Callable[[httpx.AsyncBaseTransport], httpx.AsyncBaseTransport],
) -> httpx.AsyncBaseTransport:
    """
    Compose multiple transport wrappers.

    Mimics undici's compose pattern for httpx.

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = compose_transport(
            base,
            lambda inner: DnsCacheTransport(inner, load_balance_strategy='power-of-two'),
            lambda inner: RateLimitTransport(inner, max_per_second=10),
        )
        client = httpx.AsyncClient(transport=transport)
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
    Compose multiple sync transport wrappers.
    """
    transport = base
    for wrapper in wrappers:
        transport = wrapper(transport)
    return transport


def create_dns_cached_client(
    *,
    default_ttl_seconds: float = 60.0,
    load_balance_strategy: LoadBalanceStrategy = "round-robin",
    hosts: Optional[list[str]] = None,
    exclude_hosts: Optional[list[str]] = None,
    base_url: Optional[str] = None,
    proxy: Optional[str] = None,
    **client_kwargs: Any,
) -> httpx.AsyncClient:
    """
    Create an async client with DNS caching.

    Example:
        client = create_dns_cached_client(
            load_balance_strategy='power-of-two',
            default_ttl_seconds=120,
        )
        response = await client.get('https://api.example.com/data')
    """
    base_transport = httpx.AsyncHTTPTransport(proxy=proxy)
    transport = DnsCacheTransport(
        base_transport,
        default_ttl_seconds=default_ttl_seconds,
        load_balance_strategy=load_balance_strategy,
        hosts=hosts,
        exclude_hosts=exclude_hosts,
    )
    return httpx.AsyncClient(
        transport=transport,
        base_url=base_url,
        **client_kwargs,
    )


def create_dns_cached_sync_client(
    *,
    default_ttl_seconds: float = 60.0,
    hosts: Optional[list[str]] = None,
    exclude_hosts: Optional[list[str]] = None,
    base_url: Optional[str] = None,
    proxy: Optional[str] = None,
    **client_kwargs: Any,
) -> httpx.Client:
    """
    Create a sync client with DNS caching.

    Example:
        client = create_dns_cached_sync_client(default_ttl_seconds=120)
        response = client.get('https://api.example.com/data')
    """
    base_transport = httpx.HTTPTransport(proxy=proxy)
    transport = SyncDnsCacheTransport(
        base_transport,
        default_ttl_seconds=default_ttl_seconds,
        hosts=hosts,
        exclude_hosts=exclude_hosts,
    )
    return httpx.Client(
        transport=transport,
        base_url=base_url,
        **client_kwargs,
    )


def create_api_dns_cache(
    api_id: str,
    *,
    ttl_seconds: float = 60.0,
    load_balance_strategy: LoadBalanceStrategy = "round-robin",
    store: Optional[DnsCacheStore] = None,
) -> Callable[[httpx.AsyncBaseTransport], DnsCacheTransport]:
    """
    Create a transport wrapper function for a specific API.

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = compose_transport(
            base,
            create_api_dns_cache('github', ttl_seconds=300),
            create_api_dns_cache('stripe', ttl_seconds=60),
        )
    """
    def wrapper(inner: httpx.AsyncBaseTransport) -> DnsCacheTransport:
        return DnsCacheTransport(
            inner,
            config=DnsCacheConfig(
                id=api_id,
                default_ttl_seconds=ttl_seconds,
                load_balance_strategy=load_balance_strategy,
                stale_while_revalidate=True,
            ),
            store=store,
        )
    return wrapper


# Presets
AGGRESSIVE_DNS_CACHE = {
    "default_ttl_seconds": 300.0,  # 5 minutes
    "load_balance_strategy": "power-of-two",
}

CONSERVATIVE_DNS_CACHE = {
    "default_ttl_seconds": 10.0,  # 10 seconds
    "load_balance_strategy": "round-robin",
}

HIGH_AVAILABILITY_DNS_CACHE = {
    "default_ttl_seconds": 30.0,  # 30 seconds
    "load_balance_strategy": "least-connections",
}


def create_from_preset(
    preset: dict[str, Any],
    inner: httpx.AsyncBaseTransport,
    **overrides: Any,
) -> DnsCacheTransport:
    """
    Create a transport from a preset configuration.

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = create_from_preset(AGGRESSIVE_DNS_CACHE, base)
    """
    config = {**preset, **overrides}
    return DnsCacheTransport(inner, **config)
