"""
Factory pattern for explicit configuration.

Provides ProxyDispatcherFactory class for advanced use cases where
explicit configuration injection is preferred over environment detection.

Defensive Programming Patterns:
- Comprehensive logging at all proxy resolution points
- Parameter validation with clear error messages
- Type-safe configuration handling
- Secure proxy URL logging (no credentials exposed)
"""
import logging
import os
from typing import Optional, Dict, Any, Type

from .config import get_app_env, Environment

logger = logging.getLogger(__name__)


def _mask_proxy_url(url: str | None) -> str:
    """Mask proxy URL for safe logging (hide credentials if present)."""
    if not url:
        return "None"
    # Check for credentials in URL (format: http://user:pass@host:port)
    if "@" in url:
        # Hide credentials but show host:port
        protocol_end = url.find("://")
        if protocol_end != -1:
            at_pos = url.find("@")
            return f"{url[:protocol_end + 3]}***@{url[at_pos + 1:]}"
    return url


def _is_debug_mode() -> bool:
    """Check if debug/development mode is enabled."""
    env = os.environ.get("APP_ENV", os.environ.get("NODE_ENV", "development"))
    return env.lower() in ("development", "dev", "local")


from .models import (
    ProxyConfig,
    ProxyUrlConfig,
    AgentProxyConfig,
    FactoryConfig,
    DispatcherResult,
)
from .adapters.base import BaseAdapter
from .adapters.adapter_httpx import HttpxAdapter


class ProxyDispatcherFactory:
    """
    Factory for creating proxy-configured HTTP clients.

    Allows explicit configuration injection for advanced use cases
    where environment-based auto-detection is not sufficient.

    Example:
        >>> factory = ProxyDispatcherFactory(
        ...     config=FactoryConfig(
        ...         proxy_urls=ProxyUrlConfig(
        ...             PROD="http://proxy.company.com:8080",
        ...             QA="http://qa-proxy.company.com:8080",
        ...         ),
        ...     ),
        ... )
        >>> result = factory.get_proxy_dispatcher()
        >>> async with result.client as client:
        ...     response = await client.get("https://api.example.com")
    """

    # Adapter registry
    _adapters: Dict[str, Type[BaseAdapter]] = {"httpx": HttpxAdapter}

    def __init__(
        self,
        config: Optional[FactoryConfig] = None,
        adapter: str = "httpx",
    ):
        """
        Initialize factory with configuration.

        Args:
            config: Factory configuration with proxy URLs and corporate proxy.
            adapter: Adapter name to use (default: "httpx").

        Raises:
            KeyError: If adapter name is not registered.
        """
        self._config = config or FactoryConfig()
        self._adapter = self._adapters[adapter]()

        # Log factory initialization in development mode
        if _is_debug_mode():
            proxy_urls_str = "None"
            if self._config.proxy_urls:
                proxy_urls_str = ", ".join(
                    f"{k}={_mask_proxy_url(v)}"
                    for k, v in self._config.proxy_urls.__dict__.items()
                    if v is not None
                )
            agent_proxy_str = "None"
            if self._config.agent_proxy:
                agent_proxy_str = (
                    f"http={_mask_proxy_url(self._config.agent_proxy.http_proxy)}, "
                    f"https={_mask_proxy_url(self._config.agent_proxy.https_proxy)}"
                )
            logger.info(
                f"[ProxyDispatcherFactory] initialized: adapter={adapter}, "
                f"proxy_urls=[{proxy_urls_str}], agent_proxy=[{agent_proxy_str}], "
                f"default_env={self._config.default_environment}"
            )

    def _resolve_proxy_url(self, environment: Optional[str] = None) -> Optional[str]:
        """
        Resolve the effective proxy URL.

        Priority:
        1. Agent proxy (https_proxy > http_proxy)
        2. Environment-specific proxy from config

        Args:
            environment: Target environment override (any user-defined name).

        Returns:
            Resolved proxy URL or None.
        """
        # Priority 1: Agent proxy
        if self._config.agent_proxy:
            agent = (
                self._config.agent_proxy.https_proxy
                or self._config.agent_proxy.http_proxy
            )
            if agent:
                return agent

        # Priority 2: Environment-specific
        env = environment or self._config.default_environment or get_app_env()
        if self._config.proxy_urls:
            return self._config.proxy_urls.get(env)
        return None

    def get_proxy_dispatcher(
        self,
        environment: Optional[str] = None,
        disable_tls: Optional[bool] = None,
        timeout: float = 30.0,
        async_client: bool = True,
    ) -> DispatcherResult:
        """
        Get dispatcher based on factory config.

        Args:
            environment: Target environment (default: auto-detect from APP_ENV).
            disable_tls: Force TLS disabled (default: auto based on environment).
            timeout: Request timeout in seconds.
            async_client: If True return AsyncClient, else return sync Client.

        Returns:
            DispatcherResult with configured client.
        """
        env = environment or self._config.default_environment or get_app_env()
        proxy_url = self._resolve_proxy_url(environment)

        # Priority: disable_tls param > cert_verify from config (YAML)
        if disable_tls is not None:
            verify_ssl = not disable_tls
        else:
            verify_ssl = self._config.cert_verify if self._config.cert_verify is not None else False

        # Log proxy resolution in development mode
        if _is_debug_mode():
            logger.info(
                f"[get_proxy_dispatcher] env={env}, proxy_url={_mask_proxy_url(proxy_url)}, "
                f"verify_ssl={verify_ssl}, timeout={timeout}s, async={async_client}"
            )

        config = ProxyConfig(
            proxy_url=proxy_url,
            verify_ssl=verify_ssl,
            timeout=timeout,
            trust_env=False,
        )

        if async_client:
            return self._adapter.create_async_client(config)
        return self._adapter.create_sync_client(config)

    def get_dispatcher_for_environment(
        self,
        env: str,
        async_client: bool = True,
    ) -> DispatcherResult:
        """
        Get dispatcher for a specific environment.

        Args:
            env: Target environment.
            async_client: If True return AsyncClient, else return sync Client.

        Returns:
            DispatcherResult with configured client.
        """
        return self.get_proxy_dispatcher(environment=env, async_client=async_client)

    def get_request_kwargs(
        self,
        environment: Optional[str] = None,
        timeout: float = 30.0,
        ca_bundle: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get kwargs dict for httpx top-level functions (get, post, put, delete, etc).

        Returns a dictionary that can be spread into httpx top-level function calls
        to apply proxy and SSL configuration.

        Note: verify defaults to False unless ca_bundle is provided.
        Note: For client certificates (cert), use get_proxy_dispatcher() with the
              client pattern instead, as httpx top-level functions don't support cert.

        Args:
            environment: Target environment (default: auto-detect from APP_ENV).
            timeout: Request timeout in seconds.
            ca_bundle: CA bundle path for SSL verification (sets verify to this path).

        Returns:
            Dictionary suitable for spreading into httpx.get(), httpx.post(), etc.

        Example:
            >>> factory = ProxyDispatcherFactory(...)
            >>> kwargs = factory.get_request_kwargs("QA")
            >>> response = httpx.post("https://api.example.com", json=data, **kwargs)
        """
        proxy_url = self._resolve_proxy_url(environment)

        # Use provided ca_bundle or fall back to factory config
        effective_ca_bundle = ca_bundle or self._config.ca_bundle

        kwargs: Dict[str, Any] = {
            "timeout": timeout,
            "trust_env": False,
            "verify": effective_ca_bundle if effective_ca_bundle else False,
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url

        return kwargs

    def get_proxy_config(
        self,
        environment: Optional[str] = None,
        timeout: float = 30.0,
        cert: Optional[Any] = None,
        ca_bundle: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get proxy config dict for custom httpx.Client creation.

        Use this when you need to create your own httpx client with
        custom options (http2, limits, etc.) but want the proxy/SSL
        configuration handled by the factory.

        Note: verify defaults to False unless ca_bundle is provided.

        Args:
            environment: Target environment (default: auto-detect from APP_ENV).
            timeout: Request timeout in seconds.
            cert: Client certificate path or (cert, key) tuple for proxy auth.
            ca_bundle: CA bundle path for SSL verification (sets verify to this path).

        Returns:
            Dictionary suitable for httpx.Client/AsyncClient constructor.

        Example:
            >>> factory = ProxyDispatcherFactory(...)
            >>> config = factory.get_proxy_config("QA", cert="/path/to/client.crt")
            >>> with httpx.Client(**config, http2=True) as client:
            ...     response = client.post("https://api.example.com", json=data)
        """
        proxy_url = self._resolve_proxy_url(environment)

        # Use provided cert/ca_bundle or fall back to factory config
        effective_cert = cert or self._config.cert
        effective_ca_bundle = ca_bundle or self._config.ca_bundle

        config = ProxyConfig(
            proxy_url=proxy_url,
            verify_ssl=False,
            timeout=timeout,
            trust_env=False,
            cert=effective_cert,
            ca_bundle=effective_ca_bundle,
        )

        return self._adapter.get_proxy_dict(config)

    def set_proxy_urls(self, proxy_urls: ProxyUrlConfig) -> None:
        """
        Update proxy URL configuration.

        Args:
            proxy_urls: New proxy URL configuration.
        """
        self._config.proxy_urls = proxy_urls

    def set_agent_proxy(self, agent_proxy: AgentProxyConfig) -> None:
        """
        Update agent proxy configuration.

        Args:
            agent_proxy: New agent proxy configuration.
        """
        self._config.agent_proxy = agent_proxy

    def get_config(self) -> FactoryConfig:
        """
        Get current configuration.

        Returns:
            Copy of current factory configuration.
        """
        return FactoryConfig(
            proxy_urls=self._config.proxy_urls,
            agent_proxy=self._config.agent_proxy,
            default_environment=self._config.default_environment,
            cert=self._config.cert,
            ca_bundle=self._config.ca_bundle,
            cert_verify=self._config.cert_verify,
        )

    @classmethod
    def register_adapter(cls, name: str, adapter_class: Type[BaseAdapter]) -> None:
        """
        Register a new adapter.

        Args:
            name: Adapter name for lookup.
            adapter_class: Adapter class to register.
        """
        cls._adapters[name] = adapter_class


def create_proxy_dispatcher_factory(
    config: Optional[FactoryConfig] = None,
    adapter: str = "httpx",
) -> ProxyDispatcherFactory:
    """
    Create factory instance with configuration.

    Convenience function for creating a ProxyDispatcherFactory.

    Args:
        config: Factory configuration.
        adapter: Adapter name to use.

    Returns:
        Configured ProxyDispatcherFactory instance.

    Example:
        >>> factory = create_proxy_dispatcher_factory(
        ...     config=FactoryConfig(
        ...         proxy_urls=ProxyUrlConfig(PROD="http://proxy:8080"),
        ...     ),
        ... )
        >>> result = factory.get_proxy_dispatcher()
    """
    return ProxyDispatcherFactory(config=config, adapter=adapter)
