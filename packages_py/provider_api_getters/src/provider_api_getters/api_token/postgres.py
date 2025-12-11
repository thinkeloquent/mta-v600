"""
PostgreSQL connection getter.

Returns a database connection URL or client instance rather than an API key.
"""
import logging
import os
from typing import Any, Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Default environment variable names
DEFAULT_CONNECTION_URL_ENV_VAR = "DATABASE_URL"


class PostgresApiToken(BaseApiToken):
    """
    Connection getter for PostgreSQL.

    Returns connection URL information rather than API key.
    Supports both connection URL and individual component configuration.

    Configuration:
        providers.postgres.env_connection_url: "DATABASE_URL"

    Environment Variables:
        DATABASE_URL: Full PostgreSQL connection URL
        POSTGRES_HOST: Database host
        POSTGRES_PORT: Database port (default: 5432)
        POSTGRES_USER: Database user
        POSTGRES_PASSWORD: Database password
        POSTGRES_DB: Database name
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for PostgreSQL."""
        return "postgres"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check query for PostgreSQL.

        A simple SELECT 1 query verifies database connectivity.
        """
        logger.debug("PostgresApiToken.health_endpoint: Returning SELECT 1")
        return "SELECT 1"

    def _build_connection_url(self) -> Optional[str]:
        """
        Build connection URL from individual environment variables.

        Supports:
            POSTGRES_HOST: Database host
            POSTGRES_PORT: Database port (default: 5432)
            POSTGRES_USER: Database user
            POSTGRES_PASSWORD: Database password
            POSTGRES_DB: Database name
            POSTGRES_SSLMODE: SSL mode (require, verify-ca, verify-full, prefer, disable)

        Returns:
            Connection URL string or None if required components are missing
        """
        logger.debug("PostgresApiToken._build_connection_url: Building URL from components")

        host = os.getenv("POSTGRES_HOST")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        database = os.getenv("POSTGRES_DB")
        sslmode = os.getenv("POSTGRES_SSLMODE")

        logger.debug(
            f"PostgresApiToken._build_connection_url: Components - "
            f"host={host is not None}, port={port}, "
            f"user={user is not None}, password={'***' if password else None}, "
            f"database={database is not None}, sslmode={sslmode}"
        )

        if all([host, user, database]):
            logger.debug(
                "PostgresApiToken._build_connection_url: Required components present, building URL"
            )
            if password:
                url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            else:
                url = f"postgresql://{user}@{host}:{port}/{database}"

            # Add SSL mode if specified
            if sslmode:
                # Normalize "true" to "require" for common usage
                if sslmode.lower() in ("true", "1", "yes"):
                    sslmode = "require"
                url = f"{url}?sslmode={sslmode}"
                logger.debug(
                    f"PostgresApiToken._build_connection_url: Added sslmode={sslmode}"
                )

            logger.debug(
                f"PostgresApiToken._build_connection_url: Built URL "
                f"(masked={_mask_sensitive(url)})"
            )
            return url
        else:
            missing = []
            if not host:
                missing.append("POSTGRES_HOST")
            if not user:
                missing.append("POSTGRES_USER")
            if not database:
                missing.append("POSTGRES_DB")

            logger.debug(
                f"PostgresApiToken._build_connection_url: Missing required components: {missing}"
            )
            return None

    def get_connection_url(self) -> Optional[str]:
        """
        Get PostgreSQL connection URL.

        Resolution order:
        1. Build from individual POSTGRES_* env vars (if all required are present)
        2. Use DATABASE_URL env var (or configured env var name)

        This order prioritizes individual env vars because they're more explicit
        and DATABASE_URL may contain stale values.

        Returns:
            Connection URL string or None if not configured
        """
        logger.debug("PostgresApiToken.get_connection_url: Starting connection URL resolution")

        # First try building from individual components (more explicit)
        url = self._build_connection_url()

        if url:
            logger.debug(
                "PostgresApiToken.get_connection_url: Built URL from POSTGRES_* env vars"
            )
            return url

        # Fall back to DATABASE_URL env var
        provider_config = self._get_provider_config()
        env_url = provider_config.get("env_connection_url", DEFAULT_CONNECTION_URL_ENV_VAR)

        logger.debug(
            f"PostgresApiToken.get_connection_url: Components incomplete, "
            f"checking env var '{env_url}'"
        )

        url = os.getenv(env_url)

        if url:
            logger.debug(
                f"PostgresApiToken.get_connection_url: Found URL in env var '{env_url}' "
                f"(masked={_mask_sensitive(url)})"
            )
            return url

        logger.warning(
            "PostgresApiToken.get_connection_url: No connection URL available. "
            f"Set POSTGRES_HOST/USER/DB or {env_url} environment variables."
        )
        return None

    def _get_ssl_context(self) -> Any:
        """
        Get SSL context based on POSTGRES_SSLMODE and SSL_CERT_VERIFY.

        asyncpg doesn't parse ?sslmode= from URLs, so we need to
        pass ssl parameter explicitly.

        SSL is disabled when:
        - SSL_CERT_VERIFY=0
        - NODE_TLS_REJECT_UNAUTHORIZED=0
        - POSTGRES_SSLMODE=disable

        Returns:
            ssl.SSLContext for 'require' (no cert verification)
            True for 'verify-ca'/'verify-full' (with cert verification)
            False for 'disable' or when not configured (matches Fastify default)
            "prefer" for prefer mode
        """
        import ssl

        # Check if SSL should be disabled via environment variables
        # SSL_CERT_VERIFY=0 or NODE_TLS_REJECT_UNAUTHORIZED=0 means disable SSL
        ssl_cert_verify = os.getenv("SSL_CERT_VERIFY", "")
        node_tls = os.getenv("NODE_TLS_REJECT_UNAUTHORIZED", "")
        if ssl_cert_verify == "0" or node_tls == "0":
            logger.debug(
                f"PostgresApiToken._get_ssl_context: SSL disabled via env var "
                f"(SSL_CERT_VERIFY={ssl_cert_verify!r}, NODE_TLS_REJECT_UNAUTHORIZED={node_tls!r})"
            )
            return False

        sslmode = os.getenv("POSTGRES_SSLMODE")
        if not sslmode:
            # No SSL mode specified = no SSL (matches Fastify default behavior)
            logger.debug("PostgresApiToken._get_ssl_context: No POSTGRES_SSLMODE set, defaulting to no SSL")
            return False

        # Normalize common values
        sslmode_lower = sslmode.lower()

        if sslmode_lower in ("true", "1", "yes", "require"):
            # require = use SSL but don't verify certificate
            # This is common for managed databases like DigitalOcean
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            logger.debug("PostgresApiToken._get_ssl_context: Using SSL without cert verification")
            return ctx
        elif sslmode_lower in ("verify-ca", "verify-full"):
            # verify-ca/verify-full = use SSL with certificate verification
            logger.debug("PostgresApiToken._get_ssl_context: Using SSL with cert verification")
            return True
        elif sslmode_lower in ("false", "0", "no", "disable"):
            logger.debug("PostgresApiToken._get_ssl_context: SSL disabled")
            return False
        elif sslmode_lower == "prefer":
            # prefer means try SSL first, fall back to non-SSL
            logger.debug("PostgresApiToken._get_ssl_context: Using prefer mode")
            return "prefer"

        # Unknown value, default to no SSL
        logger.debug(f"PostgresApiToken._get_ssl_context: Unknown sslmode '{sslmode}', defaulting to no SSL")
        return False

    async def get_async_client(self) -> Optional[Any]:
        """
        Get async PostgreSQL client (asyncpg pool).

        Returns:
            asyncpg connection pool or None if unavailable
        """
        logger.debug("PostgresApiToken.get_async_client: Getting async PostgreSQL client")

        try:
            import asyncpg
            logger.debug("PostgresApiToken.get_async_client: asyncpg module imported successfully")
        except ImportError:
            logger.warning(
                "PostgresApiToken.get_async_client: asyncpg not installed. "
                "Install with: pip install asyncpg"
            )
            return None

        connection_url = self.get_connection_url()

        if not connection_url:
            logger.warning(
                "PostgresApiToken.get_async_client: No connection URL available"
            )
            return None

        # Remove sslmode from URL since asyncpg doesn't parse it
        # We pass ssl as a separate parameter
        base_url = connection_url.split("?")[0]
        ssl_context = self._get_ssl_context()

        logger.debug(
            f"PostgresApiToken.get_async_client: Creating connection pool "
            f"(ssl={ssl_context})"
        )

        try:
            # ssl_context can be: SSLContext, True, False, or "prefer"
            # False = no SSL (default for non-SSL servers, matches Fastify behavior)

            pool = await asyncpg.create_pool(
                base_url,
                min_size=1,
                max_size=1,
                ssl=ssl_context,
                timeout=10,
            )
            logger.debug(
                "PostgresApiToken.get_async_client: Connection pool created successfully"
            )
            return pool
        except Exception as e:
            logger.error(
                f"PostgresApiToken.get_async_client: Failed to create pool: {type(e).__name__}: {e}"
            )
            return None

    def get_api_key(self) -> ApiKeyResult:
        """
        Return connection info as ApiKeyResult.

        For database connections, the api_key field contains the connection URL.

        Returns:
            ApiKeyResult with connection URL as api_key
        """
        logger.debug("PostgresApiToken.get_api_key: Starting API key resolution")

        connection_url = self.get_connection_url()

        # Get raw credentials for the result
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")

        if connection_url:
            logger.debug(
                f"PostgresApiToken.get_api_key: Found connection URL "
                f"(masked={_mask_sensitive(connection_url)})"
            )
            result = ApiKeyResult(
                api_key=connection_url,
                auth_type="connection_string",
                header_name="",
                username=user,
                email=user,
                raw_api_key=password,
                client=None,
            )
        else:
            logger.warning(
                "PostgresApiToken.get_api_key: No connection URL available"
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="connection_string",
                header_name="",
                username=user,
                email=user,
                raw_api_key=password,
                client=None,
            )

        logger.debug(
            f"PostgresApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result
