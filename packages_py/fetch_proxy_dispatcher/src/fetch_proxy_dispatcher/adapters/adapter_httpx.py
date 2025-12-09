"""
httpx adapter implementation.

Provides support for both sync (httpx.Client) and async (httpx.AsyncClient).
"""
import logging
from typing import Dict, Any

import httpx

from .base import BaseAdapter
from ..models import ProxyConfig, DispatcherResult
from ..config import is_ssl_verify_disabled_by_env

# Configure logger for httpx adapter
logger = logging.getLogger("fetch_proxy_dispatcher.adapters.httpx")


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
        logger.debug(
            f"_build_kwargs: Input config - proxy_url={_mask_proxy_url(config.proxy_url)}, "
            f"verify_ssl={config.verify_ssl}, timeout={config.timeout}, "
            f"trust_env={config.trust_env}, cert={config.cert is not None}, "
            f"ca_bundle={config.ca_bundle}"
        )

        kwargs: Dict[str, Any] = {
            "timeout": httpx.Timeout(config.timeout),
            "follow_redirects": True,
            "trust_env": config.trust_env,
        }

        if config.proxy_url:
            kwargs["proxy"] = config.proxy_url
            logger.debug(f"_build_kwargs: Added proxy={_mask_proxy_url(config.proxy_url)}")

        # Check environment variables for SSL verification override
        # NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0 will disable SSL verification
        env_ssl_disabled = is_ssl_verify_disabled_by_env()

        # SSL verification - env vars > ca_bundle path > verify_ssl setting
        if env_ssl_disabled:
            kwargs["verify"] = False
            logger.debug("_build_kwargs: verify=False from env var (NODE_TLS_REJECT_UNAUTHORIZED=0 or SSL_CERT_VERIFY=0)")
        else:
            kwargs["verify"] = config.ca_bundle if config.ca_bundle else config.verify_ssl
            logger.debug(f"_build_kwargs: verify={kwargs['verify']}")

        # Client certificate for proxy authentication
        if config.cert:
            kwargs["cert"] = config.cert
            logger.debug(f"_build_kwargs: Added cert (path or tuple)")

        logger.debug(
            f"_build_kwargs: Final kwargs - timeout={kwargs['timeout']}, "
            f"follow_redirects={kwargs['follow_redirects']}, trust_env={kwargs['trust_env']}, "
            f"proxy={_mask_proxy_url(kwargs.get('proxy'))}, verify={kwargs['verify']}, "
            f"cert={kwargs.get('cert') is not None}"
        )

        return kwargs

    def create_sync_client(self, config: ProxyConfig) -> DispatcherResult:
        """
        Create a synchronous httpx.Client.

        Args:
            config: Proxy configuration.

        Returns:
            DispatcherResult with configured httpx.Client.
        """
        logger.debug("create_sync_client: Building kwargs")
        kwargs = self._build_kwargs(config)

        logger.debug("create_sync_client: Creating httpx.Client")
        client = httpx.Client(**kwargs)
        logger.debug(f"create_sync_client: httpx.Client created successfully")

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
        logger.debug("create_async_client: Building kwargs")
        kwargs = self._build_kwargs(config)

        logger.debug("create_async_client: Creating httpx.AsyncClient")
        client = httpx.AsyncClient(**kwargs)
        logger.debug(f"create_async_client: httpx.AsyncClient created successfully")

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
        logger.debug("get_proxy_dict: Building kwargs for manual client creation")
        return self._build_kwargs(config)
