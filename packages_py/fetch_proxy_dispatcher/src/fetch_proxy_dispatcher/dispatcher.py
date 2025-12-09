"""
Simple API for auto-detecting proxy configuration.

Provides convenience functions that automatically detect environment
and return appropriately configured HTTP clients.

Defensive Programming Patterns:
- Comprehensive logging at all proxy resolution points
- Secure proxy URL logging (no credentials exposed)
- Type-safe configuration handling
"""
import logging
import os
from typing import Optional, Dict, Any

import httpx

from .config import get_effective_proxy_url, is_dev, is_ssl_verify_disabled_by_env

# Configure logger for dispatcher module
logger = logging.getLogger("fetch_proxy_dispatcher.dispatcher")


def _mask_proxy_url(url: str | None) -> str:
    """Mask proxy URL for safe logging (hide credentials if present)."""
    if not url:
        return "None"
    if "@" in url:
        protocol_end = url.find("://")
        if protocol_end != -1:
            at_pos = url.find("@")
            return f"{url[:protocol_end + 3]}***@{url[at_pos + 1:]}"
    return url


def _is_debug_mode() -> bool:
    """Check if debug/development mode is enabled."""
    env = os.environ.get("APP_ENV", os.environ.get("NODE_ENV", "development"))
    return env.lower() in ("development", "dev", "local")


from .models import ProxyConfig, DispatcherResult
from .adapters.adapter_httpx import HttpxAdapter

# Default adapter instance
_default_adapter = HttpxAdapter()


def get_proxy_dispatcher(
    disable_tls: Optional[bool] = None,
    cert_verify: Optional[bool] = None,
    timeout: float = 30.0,
    async_client: bool = True,
) -> DispatcherResult:
    """
    Get appropriate httpx client for current environment.

    Automatically detects proxy configuration from environment variables
    and returns a configured client.

    Args:
        disable_tls: Force TLS disabled (default: auto based on cert_verify or is_dev()).
                    If None, uses cert_verify if provided, else is_dev() default.
        cert_verify: SSL certificate verification setting (from YAML config).
                    If None, falls back to is_dev() behavior.
        timeout: Request timeout in seconds.
        async_client: If True return AsyncClient, else return sync Client.

    Returns:
        DispatcherResult containing:
        - client: Configured httpx.Client or httpx.AsyncClient
        - config: The ProxyConfig used
        - proxy_dict: Raw kwargs for manual client creation

    Example:
        >>> result = get_proxy_dispatcher()
        >>> async with result.client as client:
        ...     response = await client.get("https://api.example.com")
        >>> print(f"Used proxy: {result.config.proxy_url}")
    """
    logger.debug(
        f"get_proxy_dispatcher: disable_tls={disable_tls!r}, cert_verify={cert_verify!r}, "
        f"timeout={timeout}, async_client={async_client}"
    )

    proxy_url = get_effective_proxy_url()
    logger.debug(f"get_proxy_dispatcher: effective_proxy_url={_mask_proxy_url(proxy_url)}")

    # Priority: env vars > disable_tls > cert_verify > is_dev() default
    # Check environment variables first (NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0)
    if is_ssl_verify_disabled_by_env():
        verify_ssl = False
        logger.debug("get_proxy_dispatcher: verify_ssl=False from env var (NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0)")
    elif disable_tls is not None:
        verify_ssl = not disable_tls
        logger.debug(f"get_proxy_dispatcher: verify_ssl from disable_tls param: {verify_ssl}")
    elif cert_verify is not None:
        verify_ssl = cert_verify
        logger.debug(f"get_proxy_dispatcher: verify_ssl from cert_verify param: {verify_ssl}")
    else:
        verify_ssl = not is_dev()
        logger.debug(f"get_proxy_dispatcher: verify_ssl from is_dev() fallback: {verify_ssl}")

    config = ProxyConfig(
        proxy_url=proxy_url,
        verify_ssl=verify_ssl,
        timeout=timeout,
        trust_env=False,
    )

    logger.debug(
        f"get_proxy_dispatcher: ProxyConfig created - "
        f"proxy_url={_mask_proxy_url(config.proxy_url)}, verify_ssl={config.verify_ssl}, "
        f"timeout={config.timeout}, trust_env={config.trust_env}"
    )

    if async_client:
        result = _default_adapter.create_async_client(config)
        logger.debug(f"get_proxy_dispatcher: Created AsyncClient, proxy_dict={result.proxy_dict}")
        return result

    result = _default_adapter.create_sync_client(config)
    logger.debug(f"get_proxy_dispatcher: Created sync Client, proxy_dict={result.proxy_dict}")
    return result


def get_proxy_config(
    timeout: float = 30.0,
    cert: Optional[Any] = None,
    ca_bundle: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get proxy configuration as dict for custom httpx.Client creation.

    Use this when you need to create your own httpx client with
    custom options (http2, limits, etc.) but want the proxy/SSL
    configuration handled automatically.

    Note: verify defaults to False unless ca_bundle is provided.

    Args:
        timeout: Request timeout in seconds.
        cert: Client certificate path or (cert, key) tuple for proxy auth.
        ca_bundle: CA bundle path for SSL verification (sets verify to this path).

    Returns:
        Dictionary suitable for httpx.Client/AsyncClient constructor.

    Example:
        >>> config = get_proxy_config(cert="/path/to/client.crt")
        >>> with httpx.Client(**config, http2=True) as client:
        ...     response = client.post("https://api.example.com", json=data)
    """
    proxy_url = get_effective_proxy_url()

    # Check environment variables for SSL verification override
    env_ssl_disabled = is_ssl_verify_disabled_by_env()

    config = ProxyConfig(
        proxy_url=proxy_url,
        verify_ssl=False if env_ssl_disabled else False,  # env vars or default False
        timeout=timeout,
        trust_env=False,
        cert=cert,
        ca_bundle=ca_bundle if not env_ssl_disabled else None,  # ignore ca_bundle if env disables SSL
    )

    return _default_adapter.get_proxy_dict(config)


def get_async_client(
    disable_tls: Optional[bool] = None,
    timeout: float = 30.0,
) -> httpx.AsyncClient:
    """
    Get configured AsyncClient.

    Convenience function that returns just the client without the
    DispatcherResult wrapper.

    Args:
        disable_tls: Force TLS disabled (default: auto based on APP_ENV).
        timeout: Request timeout in seconds.

    Returns:
        Configured httpx.AsyncClient.

    Example:
        >>> async with get_async_client() as client:
        ...     response = await client.get("https://api.example.com")
    """
    result = get_proxy_dispatcher(
        disable_tls=disable_tls,
        timeout=timeout,
        async_client=True,
    )
    return result.client  # type: ignore


def get_sync_client(
    disable_tls: Optional[bool] = None,
    timeout: float = 30.0,
) -> httpx.Client:
    """
    Get configured sync Client.

    Convenience function that returns just the client without the
    DispatcherResult wrapper.

    Args:
        disable_tls: Force TLS disabled (default: auto based on APP_ENV).
        timeout: Request timeout in seconds.

    Returns:
        Configured httpx.Client.

    Example:
        >>> with get_sync_client() as client:
        ...     response = client.get("https://api.example.com")
    """
    result = get_proxy_dispatcher(
        disable_tls=disable_tls,
        timeout=timeout,
        async_client=False,
    )
    return result.client  # type: ignore


def get_request_kwargs(
    timeout: float = 30.0,
    ca_bundle: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get kwargs dict for httpx top-level functions (get, post, put, delete, etc).

    Returns a dictionary that can be spread into httpx top-level function calls
    to apply proxy and SSL configuration based on environment auto-detection.

    Note: verify defaults to False unless ca_bundle is provided.
    Note: For client certificates (cert), use get_proxy_dispatcher() with the
          client pattern instead, as httpx top-level functions don't support cert.

    Args:
        timeout: Request timeout in seconds.
        ca_bundle: CA bundle path for SSL verification (sets verify to this path).

    Returns:
        Dictionary suitable for spreading into httpx.get(), httpx.post(), etc.

    Example:
        >>> kwargs = get_request_kwargs()
        >>> response = httpx.get("https://api.example.com", **kwargs)
        >>>
        >>> # With CA bundle for SSL verification
        >>> kwargs = get_request_kwargs(ca_bundle="/path/to/ca-bundle.crt")
    """
    proxy_url = get_effective_proxy_url()

    # Check environment variables for SSL verification override
    env_ssl_disabled = is_ssl_verify_disabled_by_env()

    # If env vars disable SSL, always set verify=False regardless of ca_bundle
    if env_ssl_disabled:
        verify_value = False
    else:
        verify_value = ca_bundle if ca_bundle else False

    kwargs: Dict[str, Any] = {
        "timeout": timeout,
        "trust_env": False,
        "verify": verify_value,
    }
    if proxy_url:
        kwargs["proxy"] = proxy_url

    return kwargs
