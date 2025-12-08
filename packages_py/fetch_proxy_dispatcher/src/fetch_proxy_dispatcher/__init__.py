"""
fetch_proxy_dispatcher - Environment-aware proxy dispatcher for httpx.

This package provides utilities for configuring HTTP clients with proxy
settings based on environment variables. It supports both synchronous
and asynchronous clients via httpx.

Example - Simple API (auto-detect):
    >>> from fetch_proxy_dispatcher import get_proxy_dispatcher
    >>>
    >>> # Async client (default)
    >>> result = get_proxy_dispatcher()
    >>> async with result.client as client:
    ...     response = await client.get("https://api.example.com")
    >>> print(f"Proxy: {result.config.proxy_url}")
    >>>
    >>> # Sync client
    >>> result = get_proxy_dispatcher(async_client=False)
    >>> with result.client as client:
    ...     response = client.get("https://api.example.com")

Example - Factory API with custom environment names:
    >>> from fetch_proxy_dispatcher import (
    ...     create_proxy_dispatcher_factory,
    ...     FactoryConfig,
    ...     ProxyUrlConfig,
    ... )
    >>>
    >>> # User-defined environment names (case-sensitive)
    >>> factory = create_proxy_dispatcher_factory(
    ...     config=FactoryConfig(
    ...         proxy_urls=ProxyUrlConfig(
    ...             Live="http://proxy.company.com:8080",
    ...             STAGING="http://staging-proxy.company.com:8080",
    ...             Preview="http://preview-proxy.company.com:8080",
    ...         ),
    ...         default_environment="Live",
    ...     ),
    ... )
    >>> result = factory.get_proxy_dispatcher()
    >>> result = factory.get_proxy_dispatcher(environment="Preview")

Environment Variables:
    APP_ENV: Environment detection (any user-defined value, case-sensitive)
    HTTP_PROXY: Agent proxy override
    HTTPS_PROXY: Agent proxy override (higher priority)
    DEBUG: Logging control (set to "false" or "0" to disable, enabled by default)
"""
import logging
import os

__version__ = "1.0.0"


def _is_debug_enabled() -> bool:
    """
    Check if debug logging is enabled.
    Logging is ENABLED by default. Disable with DEBUG=false or DEBUG=0.
    """
    debug = os.environ.get("DEBUG", "").lower()
    # Disable only if explicitly set to false/0
    if debug in ("false", "0"):
        return False
    return True  # Enabled by default


def _configure_logging() -> None:
    """Configure package logging based on DEBUG environment variable."""
    package_logger = logging.getLogger("fetch_proxy_dispatcher")

    if _is_debug_enabled():
        # Enable debug logging by default
        package_logger.setLevel(logging.DEBUG)

        # Add handler if none exists (avoid duplicate handlers)
        if not package_logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "[%(name)s] %(message)s"
            )
            handler.setFormatter(formatter)
            package_logger.addHandler(handler)
    else:
        # Disable logging
        package_logger.setLevel(logging.WARNING)


# Configure logging on import
_configure_logging()

# Config
from .config import (
    Environment,
    AppEnv,  # Deprecated: use str instead for custom environment names
    get_app_env,
    is_dev,
    get_proxy_url,
    get_agent_proxy_url,
    get_effective_proxy_url,
    is_proxy_configured,
)

# Models
from .models import (
    ProxyConfig,
    ProxyUrlConfig,
    AgentProxyConfig,
    FactoryConfig,
    DispatcherResult,
)

# Simple API
from .dispatcher import (
    get_proxy_dispatcher,
    get_proxy_config,
    get_async_client,
    get_sync_client,
    get_request_kwargs,
)

# Factory API
from .factory import (
    ProxyDispatcherFactory,
    create_proxy_dispatcher_factory,
)

# Adapters
from .adapters.base import BaseAdapter
from .adapters.adapter_httpx import HttpxAdapter

__all__ = [
    # Version
    "__version__",
    # Config
    "Environment",
    "AppEnv",
    "get_app_env",
    "is_dev",
    "get_proxy_url",
    "get_agent_proxy_url",
    "get_effective_proxy_url",
    "is_proxy_configured",
    # Models
    "ProxyConfig",
    "ProxyUrlConfig",
    "AgentProxyConfig",
    "FactoryConfig",
    "DispatcherResult",
    # Simple API
    "get_proxy_dispatcher",
    "get_proxy_config",
    "get_async_client",
    "get_sync_client",
    "get_request_kwargs",
    # Factory API
    "ProxyDispatcherFactory",
    "create_proxy_dispatcher_factory",
    # Adapters
    "BaseAdapter",
    "HttpxAdapter",
]
