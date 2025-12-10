"""
Factory for creating pre-configured HTTP clients for providers.

Integrates:
- app_static_config_yaml for provider/proxy configuration
- fetch_proxy_dispatcher for proxy handling
- fetch_client for HTTP requests

This module provides comprehensive logging for debugging client creation
and configuration issues.
"""
import logging
from typing import Any, Dict, Optional
from console_print import console
from ..api_token import get_api_token_class, BaseApiToken
from ..api_token.base import mask_sensitive
from ..utils.deep_merge import deep_merge

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

    def _get_proxy_config(self) -> Dict[str, Any]:
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

    def _get_client_config(self) -> Dict[str, Any]:
        """Get client configuration from static config."""
        logger.debug("ProviderClientFactory._get_client_config: Getting client configuration")
        try:
            client_config = self.config_store.get_nested("client") or {}
            logger.debug(
                f"ProviderClientFactory._get_client_config: Client config = "
                f"{{keys={list(client_config.keys())}}}"
            )
            return client_config
        except Exception as e:
            logger.warning(f"ProviderClientFactory._get_client_config: Error getting client config: {e}")
            return {}

    def _get_merged_config_for_provider(
        self, provider_name: str, runtime_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get merged configuration for a provider, combining global config with provider overrides.

        Resolution priority (deep merge):
        1. runtime_override (if provided via POST endpoint)
        2. providers.{name}.overwrite_root_config.* (provider-specific)
        3. Global settings (proxy.*, client.*)

        Args:
            provider_name: Provider name
            runtime_override: Optional runtime override from POST request

        Returns:
            Merged configuration with proxy, client, headers, and override flags
        """
        logger.debug(
            f"ProviderClientFactory._get_merged_config_for_provider: "
            f"Getting merged config for '{provider_name}'"
        )

        api_token = self.get_api_token(provider_name)
        if not api_token:
            return {
                "proxy": self._get_proxy_config(),
                "client": self._get_client_config(),
                "headers": {},
                "has_overwrite_root_config": False,
                "has_runtime_override": False,
            }

        overwrite = api_token.get_overwrite_root_config() or {}
        global_proxy = self._get_proxy_config()
        global_client = self._get_client_config()

        # Priority: runtime_override > overwrite_root_config > global
        merged_proxy = deep_merge(global_proxy, overwrite.get("proxy", {}))
        merged_client = deep_merge(global_client, overwrite.get("client", {}))
        headers = dict(overwrite.get("headers", {}))

        # Apply runtime override if provided
        if runtime_override:
            if runtime_override.get("proxy"):
                merged_proxy = deep_merge(merged_proxy, runtime_override["proxy"])
            if runtime_override.get("client"):
                merged_client = deep_merge(merged_client, runtime_override["client"])
            if runtime_override.get("headers"):
                headers = {**headers, **runtime_override["headers"]}

        has_overrides = len(overwrite) > 0
        if has_overrides:
            logger.info(
                f"ProviderClientFactory._get_merged_config_for_provider: "
                f"Provider '{provider_name}' has overwrite_root_config with keys: {list(overwrite.keys())}"
            )
            console.print(
                f"[bold yellow]Provider '{provider_name}' overwrite_root_config applied:[/bold yellow]",
                list(overwrite.keys())
            )

        has_runtime = runtime_override and len(runtime_override) > 0
        if has_runtime:
            logger.info(
                f"ProviderClientFactory._get_merged_config_for_provider: "
                f"Runtime override applied with keys: {list(runtime_override.keys())}"
            )
            console.print(
                f"[bold cyan]Runtime override applied:[/bold cyan]",
                list(runtime_override.keys())
            )

        return {
            "proxy": merged_proxy,
            "client": merged_client,
            "headers": headers,
            "has_overwrite_root_config": has_overrides,
            "has_runtime_override": has_runtime,
        }

    def _create_httpx_client(
        self,
        proxy_config: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        async_client: bool = True,
    ) -> Any:
        """
        Create an httpx client with proxy configuration.

        Reads proxy config (merged global + provider overrides):
        - proxy.default_environment: Environment name for proxy selection
        - proxy.proxy_urls: Per-environment proxy URLs
        - proxy.agent_proxy: Agent proxy (http_proxy, https_proxy)
        - proxy.ca_bundle: CA bundle path (null = use default, undefined = check ENV)
        - proxy.cert: Client cert path (null = none, undefined = check ENV)
        - proxy.cert_verify: SSL verification (false = disable)

        Falls back to ENV if YAML value is undefined (not present).
        Does nothing if YAML value is explicitly null.

        Args:
            proxy_config: Merged proxy configuration (global + provider overrides)
            timeout: Request timeout in seconds
            async_client: Create async client if True, sync client if False
        """
        logger.debug("ProviderClientFactory._create_httpx_client: Creating httpx client")

        try:
            from fetch_proxy_dispatcher import (
                ProxyDispatcherFactory,
                FactoryConfig,
                ProxyUrlConfig,
                AgentProxyConfig,
            )
            logger.debug("ProviderClientFactory._create_httpx_client: fetch_proxy_dispatcher imported")
        except ImportError:
            logger.warning(
                "ProviderClientFactory._create_httpx_client: fetch_proxy_dispatcher not available, "
                "using plain httpx client"
            )
            import httpx
            return httpx.AsyncClient() if async_client else httpx.Client()

        # Use provided config or fall back to global
        if proxy_config is None:
            proxy_config = self._get_proxy_config()

        # Build ProxyUrlConfig from YAML (empty dict if not configured)
        proxy_urls = None
        yaml_proxy_urls = proxy_config.get("proxy_urls")
        if yaml_proxy_urls and isinstance(yaml_proxy_urls, dict) and yaml_proxy_urls:
            proxy_urls = ProxyUrlConfig(**yaml_proxy_urls)
            logger.debug(f"ProviderClientFactory._create_httpx_client: proxy_urls={list(yaml_proxy_urls.keys())}")

        # Build AgentProxyConfig from YAML
        agent_proxy = None
        yaml_agent_proxy = proxy_config.get("agent_proxy")
        if yaml_agent_proxy and isinstance(yaml_agent_proxy, dict):
            http_proxy = yaml_agent_proxy.get("http_proxy")
            https_proxy = yaml_agent_proxy.get("https_proxy")
            if http_proxy or https_proxy:
                agent_proxy = AgentProxyConfig(http_proxy=http_proxy, https_proxy=https_proxy)
                logger.debug(
                    f"ProviderClientFactory._create_httpx_client: agent_proxy "
                    f"http={http_proxy is not None}, https={https_proxy is not None}"
                )

        # Get other config values (null = don't use, undefined = fall through to ENV)
        default_environment = proxy_config.get("default_environment")
        ca_bundle = proxy_config.get("ca_bundle")  # null = no ca_bundle
        cert = proxy_config.get("cert")  # null = no cert
        cert_verify = proxy_config.get("cert_verify")  # false = disable SSL verify

        logger.debug(
            f"ProviderClientFactory._create_httpx_client: default_env={default_environment}, "
            f"ca_bundle={ca_bundle is not None}, cert={cert is not None}, cert_verify={cert_verify}"
        )

        # Build factory config
        factory_config = FactoryConfig(
            proxy_urls=proxy_urls,
            agent_proxy=agent_proxy,
            default_environment=default_environment,
            ca_bundle=ca_bundle,
            cert=cert,
            cert_verify=cert_verify,
        )
        console.print("[bold blue]FactoryConfig:[/bold blue]", {
            "proxy_urls": proxy_urls is not None,
            "agent_proxy": agent_proxy is not None,
            "default_environment": default_environment,
            "ca_bundle": ca_bundle is not None,
            "cert": cert is not None,
            "cert_verify": cert_verify,
        })

        factory = ProxyDispatcherFactory(config=factory_config)

        # Determine TLS setting: cert_verify=False means disable TLS verification
        disable_tls = cert_verify is False

        logger.debug(
            f"ProviderClientFactory._create_httpx_client: Creating dispatcher with "
            f"disable_tls={disable_tls}, timeout={timeout}, async_client={async_client}"
        )

        result = factory.get_proxy_dispatcher(
            disable_tls=disable_tls,
            timeout=timeout,
            async_client=async_client,
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

    async def get_client(self, provider_name: str) -> Optional[Any]:
        """
        Get a pre-configured HTTP client for a provider.

        Returns an AsyncFetchClient configured with:
        - Provider's base URL from static config
        - Provider's auth from api_token (with registry integration)
        - Proxy from merged config (global + provider overrides)
        - Timeout from merged config
        - Additional headers from provider overwrite_config
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

        # Use async method to support dynamic token resolution
        api_key_result = await api_token.get_api_key_async()
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

        # Get merged config (global + provider overrides)
        merged_config = self._get_merged_config_for_provider(provider_name)

        # Check token resolver type for per-request tokens
        token_resolver_type = api_token.get_token_resolver_type()

        # Get timeout from merged client config
        timeout = merged_config["client"].get("timeout_seconds", 30.0)

        logger.debug(
            f"ProviderClientFactory.get_client: Creating httpx client with "
            f"timeout={timeout}, has_proxy_override={'proxy' in merged_config}"
        )
        httpx_client = self._create_httpx_client(
            proxy_config=merged_config["proxy"],
            timeout=timeout,
        )

        auth_config = None
        if api_key_result.api_key:
            # Use get_auth_type() and get_header_name() from api_token for consistent auth type
            auth_type = api_token.get_auth_type()
            header_name = api_token.get_header_name()
            api_key_masked = mask_sensitive(api_key_result.api_key)

            if auth_type in ("basic", "x-api-key", "custom"):
                logger.debug(
                    f"ProviderClientFactory.get_client: Using {auth_type} auth with "
                    f"header={header_name}, key={api_key_masked}"
                )
                auth_config = AuthConfig(
                    type="custom",
                    raw_api_key=api_key_result.api_key,
                    header_name=header_name,
                )
                console.print(f"[bold green]AuthConfig ({auth_type}):[/bold green]", {
                    "type": "custom",
                    "header_name": header_name,
                    "raw_api_key": api_key_masked,
                })
            else:
                logger.debug(
                    f"ProviderClientFactory.get_client: Using Bearer auth with key={api_key_masked}"
                )
                auth_config = AuthConfig(
                    type="bearer",
                    raw_api_key=api_key_result.api_key,
                )
                console.print("[bold green]AuthConfig (Bearer):[/bold green]", {
                    "type": "bearer",
                    "raw_api_key": api_key_masked,
                })
            logger.info(
                f"ProviderClientFactory.get_client: Auth config created "
                f"provider={provider_name}, auth_type={auth_type}, header_name={header_name}"
            )
        else:
            logger.warning(f"ProviderClientFactory.get_client: No API key for '{provider_name}'")

        # Build client options
        client_kwargs = {
            "base_url": base_url,
            "httpx_client": httpx_client,
            "auth": auth_config,
        }

        # Apply additional headers from overwrite_config
        override_headers = merged_config.get("headers", {})
        if override_headers:
            client_kwargs["headers"] = override_headers
            logger.debug(
                f"ProviderClientFactory.get_client: Applying override headers: "
                f"{list(override_headers.keys())}"
            )

        # For per-request tokens, add dynamic auth handler
        if token_resolver_type == "request":
            async def get_api_key_for_request(context):
                result = await api_token.get_api_key_for_request_async(context)
                return result.api_key
            client_kwargs["get_api_key_for_request"] = get_api_key_for_request
            logger.info(
                f"ProviderClientFactory.get_client: Dynamic auth enabled for per-request tokens "
                f"provider={provider_name}"
            )

        logger.info(
            f"ProviderClientFactory.get_client: Creating AsyncFetchClient for '{provider_name}' "
            f"with base_url={base_url}, has_override_headers={len(override_headers) > 0}, "
            f"token_resolver_type={token_resolver_type}"
        )
        client = create_async_client(**client_kwargs)
        console.print("[bold cyan]AsyncFetchClient created:[/bold cyan]", {
            "provider": provider_name,
            "base_url": base_url,
            "has_override_headers": len(override_headers) > 0,
            "token_resolver_type": token_resolver_type,
        })
        logger.debug(f"ProviderClientFactory.get_client: Client created successfully for '{provider_name}'")

        return client


_factory: Optional[ProviderClientFactory] = None


def get_provider_client(provider_name: str) -> Optional[Any]:
    """Get a pre-configured HTTP client for a provider (convenience function)."""
    global _factory
    if _factory is None:
        _factory = ProviderClientFactory()
    return _factory.get_client(provider_name)
