"""
Provider health check implementation.
"""
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..api_token import get_api_token_class, BaseApiToken, ApiKeyResult
from ..api_token.postgres import PostgresApiToken
from ..api_token.redis import RedisApiToken
from ..fetch_client import ProviderClientFactory


@dataclass
class ProviderConnectionResponse:
    """Response from a provider connection health check."""

    provider: str
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""

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
        }


class ProviderHealthChecker:
    """Health checker for provider connections."""

    def __init__(self, config_store: Optional[Any] = None):
        self._config_store = config_store
        self._client_factory = ProviderClientFactory(config_store)

    @property
    def config_store(self) -> Any:
        """Get config store."""
        if self._config_store is None:
            from static_config import config
            self._config_store = config
        return self._config_store

    async def check(self, provider_name: str) -> ProviderConnectionResponse:
        """Check connection to a provider."""
        provider_name_lower = provider_name.lower()

        token_class = get_api_token_class(provider_name_lower)
        if token_class is None:
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                error=f"Unknown provider: {provider_name}",
            )

        api_token = token_class(self.config_store)
        api_key_result = api_token.get_api_key()

        if api_key_result.is_placeholder:
            return ProviderConnectionResponse(
                provider=provider_name,
                status="not_implemented",
                message=api_key_result.placeholder_message,
            )

        if provider_name_lower == "postgres":
            return await self._check_postgres(api_token)
        elif provider_name_lower == "redis":
            return await self._check_redis(api_token)
        else:
            return await self._check_http(provider_name, api_token, api_key_result)

    async def _check_postgres(self, api_token: PostgresApiToken) -> ProviderConnectionResponse:
        """Check PostgreSQL connection."""
        start_time = time.perf_counter()

        try:
            pool = await api_token.get_async_client()
            if pool is None:
                return ProviderConnectionResponse(
                    provider="postgres",
                    status="error",
                    error="Failed to create connection pool. Check asyncpg installation and credentials.",
                )

            async with pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                if result == 1:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    await pool.close()
                    return ProviderConnectionResponse(
                        provider="postgres",
                        status="connected",
                        latency_ms=round(latency_ms, 2),
                        message="PostgreSQL connection successful",
                    )

            await pool.close()
            return ProviderConnectionResponse(
                provider="postgres",
                status="error",
                error="Unexpected query result",
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ProviderConnectionResponse(
                provider="postgres",
                status="error",
                latency_ms=round(latency_ms, 2),
                error=str(e),
            )

    async def _check_redis(self, api_token: RedisApiToken) -> ProviderConnectionResponse:
        """Check Redis connection."""
        start_time = time.perf_counter()

        try:
            client = await api_token.get_async_client()
            if client is None:
                return ProviderConnectionResponse(
                    provider="redis",
                    status="error",
                    error="Failed to create Redis client. Check redis installation and credentials.",
                )

            result = await client.ping()
            latency_ms = (time.perf_counter() - start_time) * 1000
            await client.aclose()

            if result:
                return ProviderConnectionResponse(
                    provider="redis",
                    status="connected",
                    latency_ms=round(latency_ms, 2),
                    message="Redis connection successful (PONG)",
                )

            return ProviderConnectionResponse(
                provider="redis",
                status="error",
                error="PING did not return expected response",
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ProviderConnectionResponse(
                provider="redis",
                status="error",
                latency_ms=round(latency_ms, 2),
                error=str(e),
            )

    async def _check_http(
        self,
        provider_name: str,
        api_token: BaseApiToken,
        api_key_result: ApiKeyResult,
    ) -> ProviderConnectionResponse:
        """Check HTTP provider connection."""
        start_time = time.perf_counter()

        if not api_key_result.has_credentials:
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                error="No API credentials configured",
            )

        base_url = api_token.get_base_url()
        if not base_url:
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                error="No base URL configured",
            )

        client = self._client_factory.get_client(api_token.provider_name)
        if client is None:
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                error="Failed to create HTTP client",
            )

        try:
            health_endpoint = api_token.health_endpoint
            response = await client.get(health_endpoint)
            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code >= 200 and response.status_code < 300:
                message = self._extract_success_message(provider_name, response.data)
                return ProviderConnectionResponse(
                    provider=provider_name,
                    status="connected",
                    latency_ms=round(latency_ms, 2),
                    message=message,
                )
            else:
                return ProviderConnectionResponse(
                    provider=provider_name,
                    status="error",
                    latency_ms=round(latency_ms, 2),
                    error=f"HTTP {response.status_code}: {response.data}",
                )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ProviderConnectionResponse(
                provider=provider_name,
                status="error",
                latency_ms=round(latency_ms, 2),
                error=str(e),
            )
        finally:
            try:
                await client.close()
            except Exception:
                pass

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
