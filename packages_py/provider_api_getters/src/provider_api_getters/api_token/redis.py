"""
Redis connection getter.

Returns a Redis client instance rather than an API key.
"""
import os
from typing import Any, Optional
from .base import BaseApiToken, ApiKeyResult


class RedisApiToken(BaseApiToken):
    """Connection getter for Redis."""

    @property
    def provider_name(self) -> str:
        return "redis"

    @property
    def health_endpoint(self) -> str:
        return "PING"

    def _build_connection_url(self) -> Optional[str]:
        """Build connection URL from individual environment variables."""
        host = os.getenv("REDIS_HOST", "localhost")
        port = os.getenv("REDIS_PORT", "6379")
        password = os.getenv("REDIS_PASSWORD")
        db = os.getenv("REDIS_DB", "0")
        username = os.getenv("REDIS_USERNAME")

        if password:
            if username:
                return f"redis://{username}:{password}@{host}:{port}/{db}"
            return f"redis://:{password}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"

    def get_connection_url(self) -> Optional[str]:
        """Get Redis connection URL."""
        provider_config = self._get_provider_config()
        env_url = provider_config.get("env_connection_url", "REDIS_URL")
        url = os.getenv(env_url)
        if not url:
            url = self._build_connection_url()
        return url

    def get_sync_client(self) -> Optional[Any]:
        """Get sync Redis client."""
        try:
            import redis
        except ImportError:
            return None

        connection_url = self.get_connection_url()
        if not connection_url:
            return None

        try:
            client = redis.from_url(connection_url, decode_responses=True)
            return client
        except Exception:
            return None

    async def get_async_client(self) -> Optional[Any]:
        """Get async Redis client."""
        try:
            import redis.asyncio as aioredis
        except ImportError:
            return None

        connection_url = self.get_connection_url()
        if not connection_url:
            return None

        try:
            client = aioredis.from_url(connection_url, decode_responses=True)
            return client
        except Exception:
            return None

    def get_api_key(self) -> ApiKeyResult:
        """Return connection info as ApiKeyResult."""
        connection_url = self.get_connection_url()
        return ApiKeyResult(
            api_key=connection_url,
            auth_type="connection_string",
            header_name="",
            client=None,
        )
