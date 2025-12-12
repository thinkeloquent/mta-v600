"""
Provider health check implementation.

This module provides health check functionality for all configured providers
with comprehensive logging for debugging and observability.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from ..api_token import get_api_token_class, BaseApiToken, ApiKeyResult
from ..api_token.postgres import PostgresApiToken
from ..api_token.redis import RedisApiToken
from ..api_token.elasticsearch import ElasticsearchApiToken
from ..fetch_client import ProviderClientFactory

# Import console_print for pretty logging
try:
    from console_print import print_syntax_panel
    HAS_CONSOLE_PRINT = True
except ImportError:
    HAS_CONSOLE_PRINT = False
    print_syntax_panel = None

# Configure logger
logger = logging.getLogger("provider_api_getters.health_check")


def _mask_sensitive_header(value: str, visible_chars: int = 10) -> str:
    """Mask sensitive header value for safe logging, showing first N chars."""
    if not value:
        return "<empty>"
    if len(value) <= visible_chars:
        return "*" * len(value)
    return value[:visible_chars] + "*" * (len(value) - visible_chars)


def _format_headers_for_display(headers: Dict[str, str]) -> Dict[str, str]:
    """Format headers for display, masking sensitive values."""
    masked = {}
    sensitive_headers = {"authorization", "x-api-key", "x-figma-token", "cookie", "set-cookie"}
    for key, value in headers.items():
        if key.lower() in sensitive_headers:
            masked[key] = _mask_sensitive_header(value)
        else:
            masked[key] = value
    return masked


def _print_health_request_panel(
    provider_name: str,
    method: str,
    url: str,
    headers: Dict[str, str],
    auth_type: Optional[str] = None,
) -> None:
    """Print a pretty panel for the health check request."""
    if not HAS_CONSOLE_PRINT or print_syntax_panel is None:
        return

    masked_headers = _format_headers_for_display(headers)
    request_info = {
        "provider": provider_name,
        "method": method,
        "url": url,
        "auth_type": auth_type or "unknown",
        "headers": masked_headers,
    }
    print_syntax_panel(
        json.dumps(request_info, indent=2),
        lexer="json",
        title=f"[bold cyan]Provider Health Request → {provider_name.upper()}[/bold cyan]",
        theme="monokai",
        expand=False,
    )


def _print_proxy_config_panel(
    provider_name: str,
    config_used: Dict[str, Any],
) -> None:
    """Print a pretty panel for the proxy/network configuration used."""
    if not HAS_CONSOLE_PRINT or print_syntax_panel is None:
        return

    # Extract relevant proxy/network config
    proxy_config = config_used.get("proxy", {})
    client_config = config_used.get("client", {})

    config_info = {
        "provider": provider_name,
        "base_url": config_used.get("base_url"),
        "auth_type": config_used.get("auth_type"),
        "proxy": {
            "default_environment": proxy_config.get("default_environment"),
            "proxy_urls": proxy_config.get("proxy_urls") or "(none)",
            "ca_bundle": proxy_config.get("ca_bundle") or "(system default)",
            "cert": proxy_config.get("cert") or "(none)",
            "cert_verify": proxy_config.get("cert_verify"),
            "agent_proxy": proxy_config.get("agent_proxy") or "(none)",
        },
        "client": {
            "timeout_seconds": client_config.get("timeout_seconds"),
            "max_connections": client_config.get("max_connections"),
        },
        "overrides": {
            "has_provider_override": config_used.get("has_provider_override", False),
            "has_runtime_override": config_used.get("has_runtime_override", False),
        },
    }

    print_syntax_panel(
        json.dumps(config_info, indent=2, default=str),
        lexer="json",
        title=f"[bold magenta]Provider Config → {provider_name.upper()}[/bold magenta]",
        theme="monokai",
        expand=False,
    )


def _print_health_response_panel(
    provider_name: str,
    status: str,
    status_code: int,
    latency_ms: float,
    response_headers: Dict[str, str],
    response_data: Any,
    error: Optional[str] = None,
) -> None:
    """Print a pretty panel for the health check response."""
    if not HAS_CONSOLE_PRINT or print_syntax_panel is None:
        return

    # Determine status style
    if status == "connected":
        status_style = "[bold green]"
        title_color = "green"
    elif status == "error":
        status_style = "[bold red]"
        title_color = "red"
    else:
        status_style = "[bold yellow]"
        title_color = "yellow"

    # Build response info
    masked_resp_headers = _format_headers_for_display(response_headers)
    response_info: Dict[str, Any] = {
        "provider": provider_name,
        "status": status,
        "http_status": status_code,
        "latency_ms": round(latency_ms, 2),
        "headers": masked_resp_headers,
    }

    # Include response data (truncated if too large)
    if response_data is not None:
        if isinstance(response_data, dict):
            response_info["data"] = response_data
        elif isinstance(response_data, str) and len(response_data) > 500:
            response_info["data"] = response_data[:500] + "..."
        else:
            response_info["data"] = response_data

    if error:
        response_info["error"] = error

    print_syntax_panel(
        json.dumps(response_info, indent=2, default=str),
        lexer="json",
        title=f"[bold {title_color}]Provider Health Response ← {provider_name.upper()} ({status.upper()})[/bold {title_color}]",
        theme="monokai",
        expand=False,
    )


@dataclass
class ProviderConnectionResponse:
    """Response from a provider connection health check."""

    provider: str
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""
    config_used: Optional[Dict[str, Any]] = field(default=None)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp,
            "config_used": self.config_used,
        }


class ProviderHealthChecker:
    """Health checker for provider connections."""

    def __init__(
        self,
        config_store: Optional[Any] = None,
        runtime_override: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the health checker.

        Args:
            config_store: Static config store
            runtime_override: Optional runtime override for proxy/client settings
        """
        logger.debug(
            f"ProviderHealthChecker.__init__: Initializing with "
            f"config_store={'provided' if config_store else 'None (lazy-load)'}, "
            f"runtime_override={'provided' if runtime_override else 'None'}"
        )
        self._config_store = config_store
        self._runtime_override = runtime_override
        self._client_factory = ProviderClientFactory(config_store)
        logger.debug("ProviderHealthChecker.__init__: Client factory created")

    @property
    def config_store(self) -> Any:
        """Get config store."""
        if self._config_store is None:
            logger.debug("ProviderHealthChecker.config_store: Lazy-loading static_config")
            from static_config import config
            self._config_store = config
            logger.debug("ProviderHealthChecker.config_store: static_config loaded successfully")
        return self._config_store

    @property
    def runtime_override(self) -> Optional[Dict[str, Any]]:
        """Get runtime override."""
        return self._runtime_override

    def _build_config_used(
        self, provider_name: str, api_token: Optional[BaseApiToken]
    ) -> Dict[str, Any]:
        """Build config_used object for response."""
        merged_config = self._client_factory._get_merged_config_for_provider(
            provider_name, self._runtime_override
        )

        return {
            "base_url": api_token.get_base_url() if api_token else None,
            "proxy": merged_config.get("proxy"),
            "client": merged_config.get("client"),
            "auth_type": api_token.get_auth_type() if api_token else None,
            "has_provider_override": merged_config.get("has_provider_override", False),
            "has_runtime_override": merged_config.get("has_runtime_override", False),
        }

    async def check(self, provider_name: str) -> ProviderConnectionResponse:
        """Check connection to a provider."""
        logger.info(f"ProviderHealthChecker.check: Starting health check for provider '{provider_name}'")
        provider_name_lower = provider_name.lower()

        logger.debug(f"ProviderHealthChecker.check: Looking up token class for '{provider_name_lower}'")
        token_class = get_api_token_class(provider_name_lower)
        if token_class is None:
            logger.error(f"ProviderHealthChecker.check: Unknown provider '{provider_name}'")
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                error=f"Unknown provider: {provider_name}",
            )

        logger.debug(f"ProviderHealthChecker.check: Token class found: {token_class.__name__}")
        api_token = token_class(self.config_store)
        api_key_result = api_token.get_api_key()
        config_used = self._build_config_used(provider_name_lower, api_token)

        logger.debug(
            f"ProviderHealthChecker.check: API key result - "
            f"has_credentials={api_key_result.has_credentials}, "
            f"is_placeholder={api_key_result.is_placeholder}, "
            f"auth_type={api_key_result.auth_type}"
        )

        if api_key_result.is_placeholder:
            logger.warning(
                f"ProviderHealthChecker.check: Provider '{provider_name}' is a placeholder - "
                f"{api_key_result.placeholder_message}"
            )
            return ProviderConnectionResponse(
                provider=provider_name,
                status="not_implemented",
                message=api_key_result.placeholder_message,
                config_used=config_used,
            )

        if provider_name_lower == "postgres":
            logger.debug("ProviderHealthChecker.check: Routing to PostgreSQL check")
            return await self._check_postgres(api_token, config_used)
        elif provider_name_lower == "redis":
            logger.debug("ProviderHealthChecker.check: Routing to Redis check")
            return await self._check_redis(api_token, config_used)
        elif provider_name_lower == "elasticsearch":
            logger.debug("ProviderHealthChecker.check: Routing to Elasticsearch check")
            return await self._check_elasticsearch(api_token, config_used)
        else:
            logger.debug("ProviderHealthChecker.check: Routing to HTTP check")
            return await self._check_http(provider_name, api_token, api_key_result, config_used)

    async def _close_pool_with_timeout(self, pool, timeout: float = 2.0) -> None:
        """Close a pool with a timeout to avoid blocking.

        For health checks, we use a short timeout since we only need to verify
        connectivity. If graceful close hangs (common with SSL connections),
        we immediately terminate.
        """
        try:
            # First terminate to cancel any pending operations
            pool.terminate()
            # Then wait briefly for cleanup
            await asyncio.wait_for(pool.close(), timeout=timeout)
            logger.debug("ProviderHealthChecker._close_pool_with_timeout: Pool closed gracefully")
        except asyncio.TimeoutError:
            logger.debug(
                f"ProviderHealthChecker._close_pool_with_timeout: "
                f"Pool close completed after terminate (timeout={timeout}s)"
            )
        except Exception as e:
            logger.debug(f"ProviderHealthChecker._close_pool_with_timeout: Pool close error: {e}")

    async def _check_postgres(
        self, api_token: PostgresApiToken, config_used: Optional[Dict[str, Any]] = None
    ) -> ProviderConnectionResponse:
        """Check PostgreSQL connection."""
        logger.debug("ProviderHealthChecker._check_postgres: Starting PostgreSQL check")
        start_time = time.perf_counter()
        pool = None

        try:
            logger.debug("ProviderHealthChecker._check_postgres: Getting async client (asyncpg pool)")
            pool = await api_token.get_async_client()
            if pool is None:
                logger.error(
                    "ProviderHealthChecker._check_postgres: Failed to create connection pool. "
                    "Check asyncpg installation and credentials."
                )
                return ProviderConnectionResponse(
                    provider="postgres",
                    status="error",
                    error="Failed to create connection pool. Check asyncpg installation and credentials.",
                    config_used=config_used,
                )

            logger.debug("ProviderHealthChecker._check_postgres: Pool created, executing SELECT 1")
            async with pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                logger.debug(f"ProviderHealthChecker._check_postgres: Query result = {result}")
                if result == 1:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    await self._close_pool_with_timeout(pool)
                    logger.info(
                        f"ProviderHealthChecker._check_postgres: Connection successful, latency={latency_ms:.2f}ms"
                    )
                    return ProviderConnectionResponse(
                        provider="postgres",
                        status="connected",
                        latency_ms=round(latency_ms, 2),
                        message="PostgreSQL connection successful",
                        config_used=config_used,
                    )

            await self._close_pool_with_timeout(pool)
            logger.error("ProviderHealthChecker._check_postgres: Unexpected query result")
            return ProviderConnectionResponse(
                provider="postgres",
                status="error",
                error="Unexpected query result",
                config_used=config_used,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(f"ProviderHealthChecker._check_postgres: Exception: {e}")
            if pool is not None:
                try:
                    pool.terminate()
                except Exception:
                    pass
            return ProviderConnectionResponse(
                provider="postgres",
                status="error",
                latency_ms=round(latency_ms, 2),
                error=str(e),
                config_used=config_used,
            )

    async def _check_redis(
        self, api_token: RedisApiToken, config_used: Optional[Dict[str, Any]] = None
    ) -> ProviderConnectionResponse:
        """Check Redis connection."""
        logger.debug("ProviderHealthChecker._check_redis: Starting Redis check")
        start_time = time.perf_counter()

        try:
            logger.debug("ProviderHealthChecker._check_redis: Getting async client (redis-py)")
            client = await api_token.get_async_client()
            if client is None:
                logger.error(
                    "ProviderHealthChecker._check_redis: Failed to create Redis client. "
                    "Check redis installation and credentials."
                )
                return ProviderConnectionResponse(
                    provider="redis",
                    status="error",
                    error="Failed to create Redis client. Check redis installation and credentials.",
                    config_used=config_used,
                )

            logger.debug("ProviderHealthChecker._check_redis: Client created, sending PING")
            result = await client.ping()
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"ProviderHealthChecker._check_redis: PING result = {result}")
            await client.aclose()

            if result:
                logger.info(
                    f"ProviderHealthChecker._check_redis: Connection successful, latency={latency_ms:.2f}ms"
                )
                return ProviderConnectionResponse(
                    provider="redis",
                    status="connected",
                    latency_ms=round(latency_ms, 2),
                    message="Redis connection successful (PONG)",
                    config_used=config_used,
                )

            logger.error("ProviderHealthChecker._check_redis: PING did not return expected response")
            return ProviderConnectionResponse(
                provider="redis",
                status="error",
                error="PING did not return expected response",
                config_used=config_used,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(f"ProviderHealthChecker._check_redis: Exception: {e}")
            return ProviderConnectionResponse(
                provider="redis",
                status="error",
                latency_ms=round(latency_ms, 2),
                error=str(e),
                config_used=config_used,
            )

    async def _check_elasticsearch(
        self, api_token: ElasticsearchApiToken, config_used: Optional[Dict[str, Any]] = None
    ) -> ProviderConnectionResponse:
        """Check Elasticsearch/OpenSearch connection using HTTP directly.

        Uses httpx for health check to support both Elasticsearch and OpenSearch
        (the official elasticsearch-py client rejects OpenSearch servers).
        Uses proxy factory with YAML config for HTTP client creation.
        """
        logger.debug("ProviderHealthChecker._check_elasticsearch: Starting Elasticsearch/OpenSearch check")
        start_time = time.perf_counter()

        try:
            # Build the health check URL from connection config
            connection_url = api_token.get_connection_url()
            health_url = f"{connection_url}/_cluster/health"

            logger.debug(f"ProviderHealthChecker._check_elasticsearch: Checking {health_url}")

            # Use proxy factory to create httpx client with YAML config
            httpx_client = self._client_factory._create_httpx_client(timeout=10.0, async_client=True)
            logger.debug("ProviderHealthChecker._check_elasticsearch: Created httpx client with proxy config")

            async with httpx_client as client:
                response = await client.get(health_url)
                latency_ms = (time.perf_counter() - start_time) * 1000

                logger.debug(
                    f"ProviderHealthChecker._check_elasticsearch: Response status={response.status_code}"
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.debug(f"ProviderHealthChecker._check_elasticsearch: Health result = {result}")

                    if result and result.get("cluster_name"):
                        cluster_status = result.get("status", "unknown")
                        logger.info(
                            f"ProviderHealthChecker._check_elasticsearch: Connection successful, "
                            f"cluster={result['cluster_name']}, status={cluster_status}, latency={latency_ms:.2f}ms"
                        )
                        return ProviderConnectionResponse(
                            provider="elasticsearch",
                            status="connected",
                            latency_ms=round(latency_ms, 2),
                            message=f"Cluster '{result['cluster_name']}' is {cluster_status}",
                            config_used=config_used,
                        )

                    logger.error("ProviderHealthChecker._check_elasticsearch: Unexpected response format")
                    return ProviderConnectionResponse(
                        provider="elasticsearch",
                        status="error",
                        latency_ms=round(latency_ms, 2),
                        error="Unexpected response from cluster health check",
                        config_used=config_used,
                    )
                else:
                    logger.error(
                        f"ProviderHealthChecker._check_elasticsearch: HTTP {response.status_code}"
                    )
                    return ProviderConnectionResponse(
                        provider="elasticsearch",
                        status="error",
                        latency_ms=round(latency_ms, 2),
                        error=f"HTTP {response.status_code}: {response.text[:200]}",
                        config_used=config_used,
                    )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(f"ProviderHealthChecker._check_elasticsearch: Exception: {e}")
            return ProviderConnectionResponse(
                provider="elasticsearch",
                status="error",
                latency_ms=round(latency_ms, 2),
                error=str(e),
                config_used=config_used,
            )

    async def _check_http(
        self,
        provider_name: str,
        api_token: BaseApiToken,
        api_key_result: ApiKeyResult,
        config_used: Optional[Dict[str, Any]] = None,
    ) -> ProviderConnectionResponse:
        """Check HTTP provider connection."""
        logger.debug(f"ProviderHealthChecker._check_http: Starting HTTP check for '{provider_name}'")
        start_time = time.perf_counter()

        if not api_key_result.has_credentials:
            logger.error(f"ProviderHealthChecker._check_http: No API credentials for '{provider_name}'")
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                error="No API credentials configured",
                config_used=config_used,
            )

        base_url = api_token.get_base_url()
        logger.debug(f"ProviderHealthChecker._check_http: Base URL = {base_url}")
        if not base_url:
            logger.error(f"ProviderHealthChecker._check_http: No base URL configured for '{provider_name}'")
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                error="No base URL configured",
                config_used=config_used,
            )

        logger.debug(f"ProviderHealthChecker._check_http: Creating HTTP client for '{provider_name}'")
        client = await self._client_factory.get_client(api_token.provider_name)
        if client is None:
            logger.error(f"ProviderHealthChecker._check_http: Failed to create HTTP client for '{provider_name}'")
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                error="Failed to create HTTP client",
                config_used=config_used,
            )

        try:
            health_endpoint = api_token.health_endpoint
            full_url = f"{base_url}{health_endpoint}"

            logger.info(
                f"ProviderHealthChecker._check_http: Sending GET request to "
                f"{full_url} for provider '{provider_name}'"
            )
            logger.debug(
                f"ProviderHealthChecker._check_http: Auth header = {api_key_result.header_name}, "
                f"Auth type = {api_key_result.auth_type}"
            )

            # Print proxy/network config panel
            if config_used:
                _print_proxy_config_panel(provider_name, config_used)

            # Build request headers for display (from config + auth)
            request_headers: Dict[str, str] = {}
            # Get provider config headers
            headers_config = api_token.get_headers_config() or {}
            request_headers.update(headers_config)
            # Add auth header
            if api_key_result.header_name and api_key_result.api_key:
                request_headers[api_key_result.header_name] = api_key_result.api_key

            # Print request panel
            _print_health_request_panel(
                provider_name=provider_name,
                method="GET",
                url=full_url,
                headers=request_headers,
                auth_type=api_key_result.auth_type,
            )

            response = await client.get(health_endpoint)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # FetchResponse is a TypedDict with 'status' key (not 'status_code' attribute)
            status = response["status"]
            response_ok = response["ok"]
            response_data = response["data"]
            response_headers = response.get("headers", {})

            logger.debug(
                f"ProviderHealthChecker._check_http: Response received - "
                f"status={status}, ok={response_ok}, "
                f"headers={list(response_headers.keys())}, "
                f"latency_ms={latency_ms:.2f}"
            )

            if response_ok:
                message = self._extract_success_message(provider_name, response_data)
                logger.info(
                    f"ProviderHealthChecker._check_http: Provider '{provider_name}' connected - {message}"
                )

                # Print response panel (success)
                _print_health_response_panel(
                    provider_name=provider_name,
                    status="connected",
                    status_code=status,
                    latency_ms=latency_ms,
                    response_headers=response_headers,
                    response_data=response_data,
                )

                return ProviderConnectionResponse(
                    provider=provider_name,
                    status="connected",
                    latency_ms=round(latency_ms, 2),
                    message=message,
                    config_used=config_used,
                )
            else:
                error_msg = f"HTTP {status}: {response_data}"
                logger.warning(
                    f"ProviderHealthChecker._check_http: Provider '{provider_name}' returned error - {error_msg}"
                )

                # Print response panel (error)
                _print_health_response_panel(
                    provider_name=provider_name,
                    status="error",
                    status_code=status,
                    latency_ms=latency_ms,
                    response_headers=response_headers,
                    response_data=response_data,
                    error=error_msg,
                )

                return ProviderConnectionResponse(
                    provider=provider_name,
                    status="error",
                    latency_ms=round(latency_ms, 2),
                    error=error_msg,
                    config_used=config_used,
                )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                f"ProviderHealthChecker._check_http: Exception during health check for '{provider_name}': {e}"
            )

            # Print response panel (exception)
            _print_health_response_panel(
                provider_name=provider_name,
                status="error",
                status_code=0,
                latency_ms=latency_ms,
                response_headers={},
                response_data=None,
                error=str(e),
            )

            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                latency_ms=round(latency_ms, 2),
                error=str(e),
                config_used=config_used,
            )
        finally:
            try:
                logger.debug(f"ProviderHealthChecker._check_http: Closing client for '{provider_name}'")
                await client.close()
            except Exception as close_error:
                logger.debug(f"ProviderHealthChecker._check_http: Error closing client: {close_error}")

    def _extract_success_message(self, provider_name: str, data: Any) -> str:
        """Extract a meaningful success message from the response."""
        if not isinstance(data, dict):
            return f"Connected to {provider_name}"

        provider_lower = provider_name.lower()

        if provider_lower == "figma":
            email = data.get("email")
            if email:
                return f"Connected as {email}"

        elif provider_lower == "github":
            login = data.get("login")
            if login:
                return f"Connected as @{login}"

        elif provider_lower in ("jira", "confluence"):
            display_name = data.get("displayName")
            email = data.get("emailAddress")
            if display_name:
                return f"Connected as {display_name}"
            if email:
                return f"Connected as {email}"

        elif provider_lower in ("gemini", "openai", "gemini_openai"):
            models = data.get("data", [])
            if isinstance(models, list):
                return f"Connected, {len(models)} models available"

        return f"Connected to {provider_name}"


_checker: Optional[ProviderHealthChecker] = None


async def check_provider_connection(provider_name: str) -> ProviderConnectionResponse:
    """Check connection to a provider (convenience function)."""
    global _checker
    if _checker is None:
        _checker = ProviderHealthChecker()
    return await _checker.check(provider_name)
