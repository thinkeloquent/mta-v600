"""
Redis connection getter.

Returns a Redis connection URL or client instance rather than an API key.
"""
import logging
import os
from typing import Any, Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Default environment variable names
DEFAULT_CONNECTION_URL_ENV_VAR = "REDIS_URL"


class RedisApiToken(BaseApiToken):
    """
    Connection getter for Redis.

    Returns connection URL information rather than API key.
    Supports both connection URL and individual component configuration.

    Configuration:
        providers.redis.env_connection_url: "REDIS_URL"

    Environment Variables:
        REDIS_URL: Full Redis connection URL
        REDIS_HOST: Redis host (default: localhost)
        REDIS_PORT: Redis port (default: 6379)
        REDIS_USERNAME: Redis username (optional)
        REDIS_PASSWORD: Redis password (optional)
        REDIS_DB: Redis database number (default: 0)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Redis."""
        return "redis"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check command for Redis.

        PING is the standard Redis health check command.
        """
        logger.debug("RedisApiToken.health_endpoint: Returning PING")
        return "PING"

    def _build_connection_url(self) -> Optional[str]:
        """
        Build connection URL from individual environment variables.

        Always returns a URL since Redis has sensible defaults for most params.
        Uses rediss:// (TLS) when REDIS_TLS=true or port is a known TLS port (25061).

        Returns:
            Connection URL string
        """
        logger.debug("RedisApiToken._build_connection_url: Building URL from components")

        host = os.getenv("REDIS_HOST", "localhost")
        port = os.getenv("REDIS_PORT", "6379")
        password = os.getenv("REDIS_PASSWORD")
        db = os.getenv("REDIS_DB", "0")
        username = os.getenv("REDIS_USERNAME")

        # Determine if TLS should be used
        # - Explicit REDIS_TLS=true
        # - Known TLS ports (25061 is DigitalOcean's TLS port)
        redis_tls = os.getenv("REDIS_TLS", "").lower() in ("true", "1", "yes")
        tls_ports = {"25061", "6380"}  # Common TLS ports
        use_tls = redis_tls or port in tls_ports

        scheme = "rediss" if use_tls else "redis"

        logger.debug(
            f"RedisApiToken._build_connection_url: Components - "
            f"host={host}, port={port}, "
            f"username={username is not None}, password={'***' if password else None}, "
            f"db={db}, use_tls={use_tls}, scheme={scheme}"
        )

        if password:
            if username:
                url = f"{scheme}://{username}:{password}@{host}:{port}/{db}"
                logger.debug(
                    f"RedisApiToken._build_connection_url: Built URL with username and password "
                    f"(masked={_mask_sensitive(url)})"
                )
            else:
                url = f"{scheme}://:{password}@{host}:{port}/{db}"
                logger.debug(
                    f"RedisApiToken._build_connection_url: Built URL with password only "
                    f"(masked={_mask_sensitive(url)})"
                )
        else:
            url = f"{scheme}://{host}:{port}/{db}"
            logger.debug(
                f"RedisApiToken._build_connection_url: Built URL without auth "
                f"(url={url})"
            )

        return url

    def get_connection_url(self) -> Optional[str]:
        """
        Get Redis connection URL.

        First checks for REDIS_URL env var, then builds from components.

        Returns:
            Connection URL string (always returns a URL due to Redis defaults)
        """
        logger.debug("RedisApiToken.get_connection_url: Starting connection URL resolution")

        # Get env var name from config
        provider_config = self._get_provider_config()
        env_url = provider_config.get("env_connection_url", DEFAULT_CONNECTION_URL_ENV_VAR)

        logger.debug(
            f"RedisApiToken.get_connection_url: Checking env var '{env_url}'"
        )

        url = os.getenv(env_url)

        if url:
            logger.debug(
                f"RedisApiToken.get_connection_url: Found URL in env var '{env_url}' "
                f"(masked={_mask_sensitive(url)})"
            )
            return url
        else:
            logger.debug(
                f"RedisApiToken.get_connection_url: Env var '{env_url}' not set, "
                "building from components"
            )

        # Build from components (always succeeds due to defaults)
        url = self._build_connection_url()

        logger.debug(
            "RedisApiToken.get_connection_url: Built URL from components"
        )

        return url

    def get_sync_client(self) -> Optional[Any]:
        """
        Get sync Redis client.

        Returns:
            Redis client instance or None if unavailable
        """
        logger.debug("RedisApiToken.get_sync_client: Getting sync Redis client")

        try:
            import redis
            logger.debug("RedisApiToken.get_sync_client: redis module imported successfully")
        except ImportError:
            logger.warning(
                "RedisApiToken.get_sync_client: redis not installed. "
                "Install with: pip install redis"
            )
            return None

        connection_url = self.get_connection_url()

        if not connection_url:
            logger.warning(
                "RedisApiToken.get_sync_client: No connection URL available"
            )
            return None

        logger.debug("RedisApiToken.get_sync_client: Creating Redis client")

        try:
            client = redis.from_url(connection_url, decode_responses=True)
            logger.debug(
                "RedisApiToken.get_sync_client: Redis client created successfully"
            )
            return client
        except Exception as e:
            logger.error(
                f"RedisApiToken.get_sync_client: Failed to create client: {type(e).__name__}: {e}"
            )
            return None

    async def get_async_client(self) -> Optional[Any]:
        """
        Get async Redis client.

        Returns:
            Async Redis client instance or None if unavailable
        """
        logger.debug("RedisApiToken.get_async_client: Getting async Redis client")

        try:
            import redis.asyncio as aioredis
            logger.debug("RedisApiToken.get_async_client: redis.asyncio module imported successfully")
        except ImportError:
            logger.warning(
                "RedisApiToken.get_async_client: redis[async] not installed. "
                "Install with: pip install redis[async]"
            )
            return None

        connection_url = self.get_connection_url()

        if not connection_url:
            logger.warning(
                "RedisApiToken.get_async_client: No connection URL available"
            )
            return None

        logger.debug("RedisApiToken.get_async_client: Creating async Redis client")

        try:
            client = aioredis.from_url(connection_url, decode_responses=True)
            logger.debug(
                "RedisApiToken.get_async_client: Async Redis client created successfully"
            )
            return client
        except Exception as e:
            logger.error(
                f"RedisApiToken.get_async_client: Failed to create client: {type(e).__name__}: {e}"
            )
            return None

    def get_api_key(self) -> ApiKeyResult:
        """
        Return connection info as ApiKeyResult.

        For database connections, the api_key field contains the connection URL.

        Returns:
            ApiKeyResult with connection URL as api_key
        """
        logger.debug("RedisApiToken.get_api_key: Starting API key resolution")

        connection_url = self.get_connection_url()

        if connection_url:
            logger.debug(
                f"RedisApiToken.get_api_key: Found connection URL "
                f"(masked={_mask_sensitive(connection_url)})"
            )
            result = ApiKeyResult(
                api_key=connection_url,
                auth_type="connection_string",
                header_name="",
                client=None,
            )
        else:
            logger.warning(
                "RedisApiToken.get_api_key: No connection URL available"
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="connection_string",
                header_name="",
                client=None,
            )

        logger.debug(
            f"RedisApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result
