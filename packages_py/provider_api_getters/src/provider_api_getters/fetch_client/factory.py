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
from console_print import console, print_auth_trace
from ..api_token import get_api_token_class, BaseApiToken
from ..api_token.base import mask_sensitive
from ..utils.deep_merge import deep_merge
from ..utils.auth_resolver import resolve_auth_config, get_auth_type_category

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

    def _get_network_config(self) -> Dict[str, Any]:
        """
        Get global network configuration from config store.

        Returns:
            Network config dictionary or empty dict if not found
        """
        try:
            if not self.config_store:
                return {}
            # Try 'network' first, fall back to 'proxy'
            return self.config_store.get_nested("network") or self.config_store.get_nested("proxy") or {}
        except Exception as e:
            logger.warning(f"Failed to get network config: {e}")
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
        1. runtime_override (passed in recursive calls or from API)
        2. providers.{name}.network|client|headers (provider-specific)
        3. Global settings (network.*, client.*)

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
                "network": self._get_network_config(),
                "client": self._get_client_config(),
                "headers": {},
                "proxy_url": None,
                "has_provider_override": False,
                "has_runtime_override": False,
            }

        # Get specific overrides directly from provider config
        # These correspond to providers.{name}.network, .client, .headers
        # We also support legacy 'proxy' key for backward compatibility or direct access
        provider_network = api_token.get_network_config() or api_token.get_proxy_config() or {}
        provider_client = api_token.get_client_config() or {}
        provider_headers = api_token.get_headers_config() or {}

        global_network = self._get_network_config()
        global_client = self._get_client_config()

        # Priority: runtime_override > provider_specific > global
        merged_network = deep_merge(global_network, provider_network)
        merged_client = deep_merge(global_client, provider_client)
        headers = dict(provider_headers)

        # Apply runtime override if provided
        if runtime_override:
            if runtime_override.get("network"):
                merged_network = deep_merge(merged_network, runtime_override["network"])
            # Legacy support for 'proxy' key in runtime override if clients send it?
            # Ideally we support both or migrate clients. For safety, check both.
            if runtime_override.get("proxy"):
                merged_network = deep_merge(merged_network, runtime_override["proxy"])

            if runtime_override.get("client"):
                merged_client = deep_merge(merged_client, runtime_override["client"])
            if runtime_override.get("headers"):
                headers = {**headers, **runtime_override["headers"]}

        has_overrides = bool(provider_network or provider_client or provider_headers)
        if has_overrides:
            logger.info(
                f"ProviderClientFactory._get_merged_config_for_provider: "
                f"Provider '{provider_name}' has specific overrides"
            )
            console.print(
                f"[bold yellow]Provider '{provider_name}' specific overrides applied[/bold yellow]"
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
            "network": merged_network,
            "client": merged_client,
            "headers": headers,
            "proxy_url": api_token.get_proxy_url(), # New: Direct proxy URL override from provider
            "has_provider_override": has_overrides,
            "has_runtime_override": has_runtime,
        }

    def _create_httpx_client(
        self,
        network_config: Optional[Dict[str, Any]] = None,
        proxy_url: Optional[str] = None,
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
            network_config: Merged network configuration (global + provider overrides)
            proxy_url: Optional direct proxy URL override
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
        if network_config is None:
            network_config = self._get_network_config()

        # Build ProxyUrlConfig from YAML (empty dict if not configured)
        proxy_urls = None
        yaml_proxy_urls = network_config.get("proxy_urls")
        if yaml_proxy_urls and isinstance(yaml_proxy_urls, dict) and yaml_proxy_urls:
            proxy_urls = ProxyUrlConfig(**yaml_proxy_urls)
            logger.debug(f"ProviderClientFactory._create_httpx_client: proxy_urls={list(yaml_proxy_urls.keys())}")

        # Build AgentProxyConfig from YAML
        agent_proxy = None
        yaml_agent_proxy = network_config.get("agent_proxy")
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
        default_environment = network_config.get("default_environment")
        ca_bundle = network_config.get("ca_bundle")  # null = no ca_bundle
        cert = network_config.get("cert")  # null = no cert
        cert_verify = network_config.get("cert_verify")  # false = disable SSL verify

        logger.debug(
            f"ProviderClientFactory._create_httpx_client: default_env={default_environment}, "
            f"ca_bundle={ca_bundle is not None}, cert={cert is not None}, cert_verify={cert_verify}"
        )

        # Build factory config
        factory_config = FactoryConfig(
            proxy_urls=proxy_urls,
            proxy_url=proxy_url,  # Pass direct override
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
        client_kwargs = {
            "timeout": timeout,
            # "proxy" is handled by the factory via create_async_client/create_sync_client
            # so we don't pass it directly here if we're using the factory.
        }

        # Create client using factory (configured with network settings)
        httpx_client = self._create_httpx_client(
            network_config=merged_config["network"],
            proxy_url=merged_config.get("proxy_url"),
            timeout=timeout,
            async_client=True,
        )
        auth_config = None
        if api_key_result.api_key:
            # Use get_auth_type() and get_header_name() from api_token for consistent auth type
            auth_type = api_token.get_auth_type()
            header_name = api_token.get_header_name()
            api_key_masked = mask_sensitive(api_key_result.api_key)

            # Use shared auth resolver utility (SINGLE SOURCE OF TRUTH)
            # See: utils/auth_resolver.py for auth type interpretation logic
            print_auth_trace("BEFORE resolve_auth_config", "factory.py:375", getattr(api_key_result, 'raw_api_key', None))
            auth_dict = resolve_auth_config(auth_type, api_key_result, header_name)
            auth_category = get_auth_type_category(auth_type)
            print_auth_trace("AFTER resolve_auth_config", "factory.py:378", auth_dict.get('raw_api_key', ''))

            logger.debug(
                f"ProviderClientFactory.get_client: Using {auth_category} auth ({auth_type}) with "
                f"resolved_type={auth_dict['type']}, header={auth_dict.get('header_name', 'Authorization')}, "
                f"key={api_key_masked}"
            )

            print_auth_trace("BEFORE AuthConfig", "factory.py:386")
            auth_config = AuthConfig(**auth_dict)
            print_auth_trace("AFTER AuthConfig", "factory.py:388", auth_config.raw_api_key)

            console.print(f"[bold green]AuthConfig ({auth_type} → {auth_category}):[/bold green]", {
                "type": auth_dict["type"],
                "header_name": auth_dict.get("header_name", "Authorization"),
                "raw_api_key": api_key_masked,
            })

            logger.info(
                f"ProviderClientFactory.get_client: Auth config created "
                f"provider={provider_name}, auth_type={auth_type}, category={auth_category}"
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
            client_kwargs["default_headers"] = override_headers
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
