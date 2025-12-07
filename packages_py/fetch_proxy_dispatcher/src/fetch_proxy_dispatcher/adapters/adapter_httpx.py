"""
httpx adapter implementation.

Provides support for both sync (httpx.Client) and async (httpx.AsyncClient).
"""
from typing import Dict, Any

import httpx

from .base import BaseAdapter
from ..models import ProxyConfig, DispatcherResult


class HttpxAdapter(BaseAdapter):
    """
    httpx adapter supporting both sync and async clients.

    This is the primary adapter for fetch_proxy_dispatcher, leveraging
    httpx's excellent proxy and SSL configuration support.
    """

    @property
    def name(self) -> str:
        return "httpx"

    @property
    def supports_sync(self) -> bool:
        return True

    @property
    def supports_async(self) -> bool:
        return True

    def _build_kwargs(self, config: ProxyConfig) -> Dict[str, Any]:
        """
        Build kwargs for httpx.Client/AsyncClient.

        Args:
            config: Proxy configuration.

        Returns:
            Dictionary of kwargs for httpx client constructor.
        """
        kwargs: Dict[str, Any] = {
            "timeout": httpx.Timeout(config.timeout),
            "follow_redirects": True,
            "trust_env": config.trust_env,
        }

        if config.proxy_url:
            kwargs["proxy"] = config.proxy_url

        # SSL verification - ca_bundle path or False (default)
        kwargs["verify"] = config.ca_bundle if config.ca_bundle else config.verify_ssl

        # Client certificate for proxy authentication
        if config.cert:
            kwargs["cert"] = config.cert

        return kwargs

    def create_sync_client(self, config: ProxyConfig) -> DispatcherResult:
        """
        Create a synchronous httpx.Client.

        Args:
            config: Proxy configuration.

        Returns:
            DispatcherResult with configured httpx.Client.
        """
        kwargs = self._build_kwargs(config)
        client = httpx.Client(**kwargs)
        return DispatcherResult(
            client=client,
            config=config,
            proxy_dict=kwargs,
        )

    def create_async_client(self, config: ProxyConfig) -> DispatcherResult:
        """
        Create an asynchronous httpx.AsyncClient.

        Args:
            config: Proxy configuration.

        Returns:
            DispatcherResult with configured httpx.AsyncClient.
        """
        kwargs = self._build_kwargs(config)
        client = httpx.AsyncClient(**kwargs)
        return DispatcherResult(
            client=client,
            config=config,
            proxy_dict=kwargs,
        )

    def get_proxy_dict(self, config: ProxyConfig) -> Dict[str, Any]:
        """
        Get proxy configuration as dict for manual client creation.

        Args:
            config: Proxy configuration.

        Returns:
            Dictionary suitable for httpx.Client/AsyncClient constructor.
        """
        return self._build_kwargs(config)
