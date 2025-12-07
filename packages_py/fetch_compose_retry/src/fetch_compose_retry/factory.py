"""
Factory functions for creating retry-enabled transports and clients
"""
from typing import Optional, Callable, Any

import httpx

from fetch_retry import RetryConfig
from .transport import RetryTransport, SyncRetryTransport


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
            lambda inner: RetryTransport(inner, max_retries=3),
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


def create_retry_client(
    *,
    max_retries: Optional[int] = None,
    config: Optional[RetryConfig] = None,
    base_url: Optional[str] = None,
    proxy: Optional[str] = None,
    timeout: float = 5.0,
    respect_retry_after: bool = True,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
    on_success: Optional[Callable[[int, float], None]] = None,
    **client_kwargs: Any,
) -> httpx.AsyncClient:
    """
    Create a retry-enabled async HTTP client.

    Args:
        max_retries: Maximum retries (default: 3)
        config: Custom retry config
        base_url: Base URL for requests
        proxy: Proxy URL to use
        timeout: Request timeout in seconds. Default: 5.0
        respect_retry_after: Whether to respect Retry-After headers. Default: True
        on_retry: Callback before each retry attempt
        on_success: Callback on success
        **client_kwargs: Additional arguments for httpx.AsyncClient

    Returns:
        Retry-enabled async HTTP client

    Example:
        client = create_retry_client(
            max_retries=3,
            base_url="https://api.example.com",
        )
        response = await client.get("/data")
    """
    # Create base transport
    base_transport = httpx.AsyncHTTPTransport(proxy=proxy)

    # Wrap with retry transport
    transport = RetryTransport(
        base_transport,
        max_retries=max_retries,
        config=config,
        respect_retry_after=respect_retry_after,
        on_retry=on_retry,
        on_success=on_success,
    )

    return httpx.AsyncClient(
        transport=transport,
        base_url=base_url or "",
        timeout=timeout,
        **client_kwargs,
    )


def create_retry_sync_client(
    *,
    max_retries: Optional[int] = None,
    config: Optional[RetryConfig] = None,
    base_url: Optional[str] = None,
    proxy: Optional[str] = None,
    timeout: float = 5.0,
    respect_retry_after: bool = True,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
    on_success: Optional[Callable[[int, float], None]] = None,
    **client_kwargs: Any,
) -> httpx.Client:
    """
    Create a retry-enabled sync HTTP client.

    Args:
        max_retries: Maximum retries (default: 3)
        config: Custom retry config
        base_url: Base URL for requests
        proxy: Proxy URL to use
        timeout: Request timeout in seconds. Default: 5.0
        respect_retry_after: Whether to respect Retry-After headers. Default: True
        on_retry: Callback before each retry attempt
        on_success: Callback on success
        **client_kwargs: Additional arguments for httpx.Client

    Returns:
        Retry-enabled sync HTTP client
    """
    # Create base transport
    base_transport = httpx.HTTPTransport(proxy=proxy)

    # Wrap with retry transport
    transport = SyncRetryTransport(
        base_transport,
        max_retries=max_retries,
        config=config,
        respect_retry_after=respect_retry_after,
        on_retry=on_retry,
        on_success=on_success,
    )

    return httpx.Client(
        transport=transport,
        base_url=base_url or "",
        timeout=timeout,
        **client_kwargs,
    )


def create_api_retry_transport(
    api_id: str,
    max_retries: int = 3,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
) -> Callable[[httpx.AsyncBaseTransport], RetryTransport]:
    """
    Create a retry transport wrapper function for a specific API.

    Args:
        api_id: Unique identifier for logging/debugging
        max_retries: Maximum retries (default: 3)
        config: Custom retry config
        on_retry: Callback before each retry attempt

    Returns:
        Transport wrapper function

    Example:
        github_retry = create_api_retry_transport("github", max_retries=5)
        openai_retry = create_api_retry_transport("openai", max_retries=3)

        github_transport = github_retry(httpx.AsyncHTTPTransport())
        openai_transport = openai_retry(httpx.AsyncHTTPTransport())
    """

    def wrapper(inner: httpx.AsyncBaseTransport) -> RetryTransport:
        return RetryTransport(
            inner,
            max_retries=max_retries,
            config=config,
            on_retry=on_retry,
        )

    return wrapper


# Preset retry configurations
RETRY_PRESETS = {
    "default": RetryConfig(
        max_retries=3,
        base_delay_seconds=1.0,
        max_delay_seconds=30.0,
        jitter_factor=0.5,
        retry_on_status=[429, 500, 502, 503, 504],
    ),
    "aggressive": RetryConfig(
        max_retries=5,
        base_delay_seconds=0.5,
        max_delay_seconds=60.0,
        jitter_factor=0.3,
        retry_on_status=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524],
    ),
    "quick": RetryConfig(
        max_retries=2,
        base_delay_seconds=0.2,
        max_delay_seconds=2.0,
        jitter_factor=0.5,
        retry_on_status=[429, 502, 503, 504],
    ),
    "gentle": RetryConfig(
        max_retries=5,
        base_delay_seconds=2.0,
        max_delay_seconds=120.0,
        jitter_factor=0.7,
        retry_on_status=[429],
    ),
}
