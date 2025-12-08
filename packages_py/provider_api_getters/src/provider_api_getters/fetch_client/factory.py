"""
Factory for creating pre-configured HTTP clients for providers.

Integrates:
- static_config_property_management for provider/proxy configuration
- fetch_proxy_dispatcher for proxy handling
- fetch_client for HTTP requests

This module provides comprehensive logging for debugging client creation
and configuration issues.
"""
import logging
from typing import Any, Optional
from ..api_token import get_api_token_class, BaseApiToken
from ..api_token.base import mask_sensitive

# Configure logger
logger = logging.getLogger("provider_api_getters.fetch_client")


class ProviderClientFactory:
    """Factory for creating pre-configured HTTP clients per provider."""

    def __init__(self, config_store: Optional[Any] = None):
        logger.debug(
            f"ProviderClientFactory.__init__: Initializing with "
            f"config_store={'provided' if config_store else 'None (lazy-load)'}"
        )
        self._config_store = config_store

    @property
    def config_store(self) -> Any:
        """Get config store, lazy-loading if not set."""
        if self._config_store is None:
            logger.debug("ProviderClientFactory.config_store: Lazy-loading static_config")
            from static_config import config
            self._config_store = config
            logger.debug("ProviderClientFactory.config_store: static_config loaded successfully")
        return self._config_store

    def _get_proxy_config(self) -> dict[str, Any]:
        """Get proxy configuration from static config."""
        logger.debug("ProviderClientFactory._get_proxy_config: Getting proxy configuration")
        try:
            proxy_config = self.config_store.get_nested("proxy") or {}
            logger.debug(
                f"ProviderClientFactory._get_proxy_config: Proxy config = "
                f"{{keys={list(proxy_config.keys())}}}"
            )
            return proxy_config
        except Exception as e:
            logger.warning(f"ProviderClientFactory._get_proxy_config: Error getting proxy config: {e}")
            return {}

    def _create_httpx_client(self) -> Any:
        """Create an httpx client with proxy configuration."""
        logger.debug("ProviderClientFactory._create_httpx_client: Creating httpx client")
        try:
            from fetch_proxy_dispatcher import get_proxy_dispatcher
            logger.debug("ProviderClientFactory._create_httpx_client: fetch_proxy_dispatcher imported")
        except ImportError:
            logger.warning(
                "ProviderClientFactory._create_httpx_client: fetch_proxy_dispatcher not available, "
                "using plain httpx.AsyncClient"
            )
            import httpx
            return httpx.AsyncClient()

        proxy_config = self._get_proxy_config()
        disable_tls = proxy_config.get("cert_verify") is False
        logger.debug(
            f"ProviderClientFactory._create_httpx_client: Creating dispatcher with "
            f"disable_tls={disable_tls}, timeout=30.0, async_client=True"
        )
        result = get_proxy_dispatcher(
            disable_tls=disable_tls,
            timeout=30.0,
            async_client=True,
        )
        logger.debug("ProviderClientFactory._create_httpx_client: Dispatcher created successfully")
        return result.client

    def get_api_token(self, provider_name: str) -> Optional[BaseApiToken]:
        """Get API token instance for a provider."""
        logger.debug(f"ProviderClientFactory.get_api_token: Getting token for '{provider_name}'")
        token_class = get_api_token_class(provider_name)
        if token_class is None:
            logger.warning(f"ProviderClientFactory.get_api_token: No token class for '{provider_name}'")
            return None
        logger.debug(f"ProviderClientFactory.get_api_token: Token class = {token_class.__name__}")
        return token_class(self.config_store)

    def get_client(self, provider_name: str) -> Optional[Any]:
        """
        Get a pre-configured HTTP client for a provider.

        Returns an AsyncFetchClient configured with:
        - Provider's base URL from static config
        - Provider's auth from api_token
        - Proxy from static config via fetch_proxy_dispatcher
        """
        logger.info(f"ProviderClientFactory.get_client: Creating client for provider '{provider_name}'")

        try:
            from fetch_client import create_async_client, AuthConfig
            logger.debug("ProviderClientFactory.get_client: fetch_client imported successfully")
        except ImportError as e:
            logger.error(f"ProviderClientFactory.get_client: Failed to import fetch_client: {e}")
            return None

        api_token = self.get_api_token(provider_name)
        if api_token is None:
            logger.error(f"ProviderClientFactory.get_client: No API token for '{provider_name}'")
            return None

        base_url = api_token.get_base_url()
        logger.debug(f"ProviderClientFactory.get_client: Base URL = {base_url}")
        if not base_url:
            logger.error(f"ProviderClientFactory.get_client: No base URL for '{provider_name}'")
            return None

        api_key_result = api_token.get_api_key()
        logger.debug(
            f"ProviderClientFactory.get_client: API key result - "
            f"has_credentials={api_key_result.has_credentials}, "
            f"is_placeholder={api_key_result.is_placeholder}, "
            f"auth_type={api_key_result.auth_type}, "
            f"header_name={api_key_result.header_name}"
        )

        if api_key_result.is_placeholder:
            logger.warning(f"ProviderClientFactory.get_client: Provider '{provider_name}' is a placeholder")
            return None

        logger.debug("ProviderClientFactory.get_client: Creating httpx client")
        httpx_client = self._create_httpx_client()

        auth_config = None
        if api_key_result.api_key:
            api_key_masked = mask_sensitive(api_key_result.api_key)
            if api_key_result.auth_type == "basic":
                logger.debug(
                    f"ProviderClientFactory.get_client: Using Basic auth with "
                    f"header={api_key_result.header_name}, key={api_key_masked}"
                )
                auth_config = AuthConfig(
                    type="custom",
                    api_key=api_key_result.api_key,
                    header_name=api_key_result.header_name,
                )
            elif api_key_result.auth_type == "x-api-key":
                logger.debug(
                    f"ProviderClientFactory.get_client: Using X-API-Key auth with "
                    f"header={api_key_result.header_name}, key={api_key_masked}"
                )
                auth_config = AuthConfig(
                    type="custom",
                    api_key=api_key_result.api_key,
                    header_name=api_key_result.header_name,
                )
            else:
                logger.debug(
                    f"ProviderClientFactory.get_client: Using Bearer auth with key={api_key_masked}"
                )
                auth_config = AuthConfig(
                    type="bearer",
                    api_key=api_key_result.api_key,
                )
        else:
            logger.warning(f"ProviderClientFactory.get_client: No API key for '{provider_name}'")

        logger.info(
            f"ProviderClientFactory.get_client: Creating AsyncFetchClient for '{provider_name}' "
            f"with base_url={base_url}"
        )
        client = create_async_client(
            base_url=base_url,
            httpx_client=httpx_client,
            auth=auth_config,
        )
        logger.debug(f"ProviderClientFactory.get_client: Client created successfully for '{provider_name}'")

        return client


_factory: Optional[ProviderClientFactory] = None


def get_provider_client(provider_name: str) -> Optional[Any]:
    """Get a pre-configured HTTP client for a provider (convenience function)."""
    global _factory
    if _factory is None:
        _factory = ProviderClientFactory()
    return _factory.get_client(provider_name)
