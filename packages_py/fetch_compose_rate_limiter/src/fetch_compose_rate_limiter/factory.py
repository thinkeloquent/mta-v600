"""
Factory functions for creating rate-limited transports and clients
"""
from typing import Optional, Callable, TypeVar, Any

import httpx

from fetch_rate_limiter import (
    RateLimiterConfig,
    StaticRateLimitConfig,
    RateLimitStore,
)
from .transport import RateLimitTransport, SyncRateLimitTransport


T = TypeVar("T", bound=httpx.BaseTransport)


def compose_transport(
    base: httpx.AsyncBaseTransport,
    *wrappers: Callable[[httpx.AsyncBaseTransport], httpx.AsyncBaseTransport],
) -> httpx.AsyncBaseTransport:
    """
    Compose multiple transport wrappers together.

    This mimics undici's compose pattern for HTTPX.

    Args:
        base: The base transport to wrap
        *wrappers: Transport wrapper functions to apply in order

    Returns:
        Composed transport with all wrappers applied

    Example:
        base = httpx.AsyncHTTPTransport(proxy="http://proxy:8080")
        transport = compose_transport(
            base,
            lambda inner: RateLimitTransport(inner, max_per_second=10),
            lambda inner: RetryTransport(inner, max_retries=3),
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
    Compose multiple sync transport wrappers together.

    Args:
        base: The base transport to wrap
        *wrappers: Transport wrapper functions to apply in order

    Returns:
        Composed transport with all wrappers applied
    """
    transport = base
    for wrapper in wrappers:
        transport = wrapper(transport)
    return transport


def create_rate_limited_client(
    *,
    max_per_second: Optional[float] = None,
    config: Optional[RateLimiterConfig] = None,
    store: Optional[RateLimitStore] = None,
    base_url: Optional[str] = None,
    proxy: Optional[str] = None,
    timeout: float = 5.0,
    **client_kwargs: Any,
) -> httpx.AsyncClient:
    """
    Create a rate-limited async HTTP client.

    Args:
        max_per_second: Maximum requests per second
        config: Custom rate limiter config
        store: Custom store for distributed rate limiting
        base_url: Base URL for requests
        proxy: Proxy URL to use
        timeout: Request timeout in seconds. Default: 5.0
        **client_kwargs: Additional arguments for httpx.AsyncClient

    Returns:
        Rate-limited async HTTP client

    Example:
        client = create_rate_limited_client(
            max_per_second=10,
            base_url="https://api.example.com",
        )
        response = await client.get("/data")
    """
    # Create base transport
    base_transport = httpx.AsyncHTTPTransport(proxy=proxy)

    # Wrap with rate limiter
    transport = RateLimitTransport(
        base_transport,
        max_per_second=max_per_second,
        config=config,
        store=store,
    )

    return httpx.AsyncClient(
        transport=transport,
        base_url=base_url or "",
        timeout=timeout,
        **client_kwargs,
    )


def create_rate_limited_sync_client(
    *,
    max_per_second: Optional[float] = None,
    base_url: Optional[str] = None,
    proxy: Optional[str] = None,
    timeout: float = 5.0,
    **client_kwargs: Any,
) -> httpx.Client:
    """
    Create a rate-limited sync HTTP client.

    Args:
        max_per_second: Maximum requests per second
        base_url: Base URL for requests
        proxy: Proxy URL to use
        timeout: Request timeout in seconds. Default: 5.0
        **client_kwargs: Additional arguments for httpx.Client

    Returns:
        Rate-limited sync HTTP client
    """
    # Create base transport
    base_transport = httpx.HTTPTransport(proxy=proxy)

    # Wrap with rate limiter
    transport = SyncRateLimitTransport(
        base_transport,
        max_per_second=max_per_second,
    )

    return httpx.Client(
        transport=transport,
        base_url=base_url or "",
        timeout=timeout,
        **client_kwargs,
    )


def create_api_rate_limiter(
    api_id: str,
    max_per_second: float,
    store: Optional[RateLimitStore] = None,
) -> Callable[[httpx.AsyncBaseTransport], RateLimitTransport]:
    """
    Create a rate limiter wrapper function for a specific API.

    Args:
        api_id: Unique identifier for the API
        max_per_second: Maximum requests per second
        store: Optional distributed store

    Returns:
        Transport wrapper function

    Example:
        github_limiter = create_api_rate_limiter("github", 5000 / 3600)
        openai_limiter = create_api_rate_limiter("openai", 60)

        github_transport = github_limiter(httpx.AsyncHTTPTransport())
        openai_transport = openai_limiter(httpx.AsyncHTTPTransport())
    """

    def wrapper(inner: httpx.AsyncBaseTransport) -> RateLimitTransport:
        return RateLimitTransport(
            inner,
            config=RateLimiterConfig(
                id=api_id,
                static=StaticRateLimitConfig(
                    max_requests=int(max_per_second),
                    interval_seconds=1.0,
                ),
            ),
            store=store,
        )

    return wrapper
