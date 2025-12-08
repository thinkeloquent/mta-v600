"""
Factory for creating pre-configured HTTP clients for providers.

Integrates:
- static_config_property_management for provider/proxy configuration
- fetch_proxy_dispatcher for proxy handling
- fetch_client for HTTP requests
"""
from typing import Any, Optional
from ..api_token import get_api_token_class, BaseApiToken


class ProviderClientFactory:
    """Factory for creating pre-configured HTTP clients per provider."""

    def __init__(self, config_store: Optional[Any] = None):
        self._config_store = config_store

    @property
    def config_store(self) -> Any:
        """Get config store, lazy-loading if not set."""
        if self._config_store is None:
            from static_config import config
            self._config_store = config
        return self._config_store

    def _get_proxy_config(self) -> dict[str, Any]:
        """Get proxy configuration from static config."""
        try:
            return self.config_store.get_nested("proxy") or {}
        except Exception:
            return {}

    def _create_httpx_client(self) -> Any:
        """Create an httpx client with proxy configuration."""
        try:
            from fetch_proxy_dispatcher import get_proxy_dispatcher
        except ImportError:
            import httpx
            return httpx.AsyncClient()

        proxy_config = self._get_proxy_config()
        result = get_proxy_dispatcher(
            disable_tls=proxy_config.get("cert_verify") is False,
            timeout=30.0,
            async_client=True,
        )
        return result.client

    def get_api_token(self, provider_name: str) -> Optional[BaseApiToken]:
        """Get API token instance for a provider."""
        token_class = get_api_token_class(provider_name)
        if token_class is None:
            return None
        return token_class(self.config_store)

    def get_client(self, provider_name: str) -> Optional[Any]:
        """
        Get a pre-configured HTTP client for a provider.

        Returns an AsyncFetchClient configured with:
        - Provider's base URL from static config
        - Provider's auth from api_token
        - Proxy from static config via fetch_proxy_dispatcher
        """
        try:
            from fetch_client import create_async_client, AuthConfig
        except ImportError:
            return None

        api_token = self.get_api_token(provider_name)
        if api_token is None:
            return None

        base_url = api_token.get_base_url()
        if not base_url:
            return None

        api_key_result = api_token.get_api_key()
        if api_key_result.is_placeholder:
            return None

        httpx_client = self._create_httpx_client()

        auth_config = None
        if api_key_result.api_key:
            if api_key_result.auth_type == "basic":
                auth_config = AuthConfig(
                    type="custom",
                    api_key=api_key_result.api_key,
                    header_name=api_key_result.header_name,
                )
            elif api_key_result.auth_type == "x-api-key":
                auth_config = AuthConfig(
                    type="custom",
                    api_key=api_key_result.api_key,
                    header_name=api_key_result.header_name,
                )
            else:
                auth_config = AuthConfig(
                    type="bearer",
                    api_key=api_key_result.api_key,
                )

        client = create_async_client(
            base_url=base_url,
            httpx_client=httpx_client,
            auth=auth_config,
        )

        return client


_factory: Optional[ProviderClientFactory] = None


def get_provider_client(provider_name: str) -> Optional[Any]:
    """Get a pre-configured HTTP client for a provider (convenience function)."""
    global _factory
    if _factory is None:
        _factory = ProviderClientFactory()
    return _factory.get_client(provider_name)
