"""
PostgreSQL connection getter.

Returns a database client instance rather than an API key.
"""
import os
from typing import Any, Optional
from .base import BaseApiToken, ApiKeyResult


class PostgresApiToken(BaseApiToken):
    """Connection getter for PostgreSQL."""

    @property
    def provider_name(self) -> str:
        return "postgres"

    @property
    def health_endpoint(self) -> str:
        return "SELECT 1"

    def _build_connection_url(self) -> Optional[str]:
        """Build connection URL from individual environment variables."""
        host = os.getenv("POSTGRES_HOST")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        database = os.getenv("POSTGRES_DB")

        if all([host, user, database]):
            if password:
                return f"postgresql://{user}:{password}@{host}:{port}/{database}"
            return f"postgresql://{user}@{host}:{port}/{database}"
        return None

    def get_connection_url(self) -> Optional[str]:
        """Get PostgreSQL connection URL."""
        provider_config = self._get_provider_config()
        env_url = provider_config.get("env_connection_url", "DATABASE_URL")
        url = os.getenv(env_url)
        if not url:
            url = self._build_connection_url()
        return url

    async def get_async_client(self) -> Optional[Any]:
        """Get async PostgreSQL client (asyncpg pool)."""
        try:
            import asyncpg
        except ImportError:
            return None

        connection_url = self.get_connection_url()
        if not connection_url:
            return None

        try:
            pool = await asyncpg.create_pool(connection_url, min_size=1, max_size=1)
            return pool
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
