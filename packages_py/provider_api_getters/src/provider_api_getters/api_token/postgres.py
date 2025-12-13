"""
PostgreSQL connection getter.

Returns a database connection URL or client instance rather than an API key.
"""
import logging
import os
from typing import Any, Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Log prefix with file path for tracing
LOG_PREFIX = f"[POSTGRES:{__file__}]"

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

    def get_base_url(self) -> Optional[str]:
        """
        Get the base URL (connection URL) for generic usage.
        
        Overrides BaseApiToken.get_base_url which only reads from YAML.
        """
        return self.get_connection_url()

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check query for PostgreSQL.

        A simple SELECT 1 query verifies database connectivity.
        """
        logger.debug(f"{LOG_PREFIX} health_endpoint: Returning SELECT 1")
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
        logger.info(f"{LOG_PREFIX} _build_connection_url: START - Building URL from environment variables")

        # Read all environment variables
        host = os.getenv("POSTGRES_HOST")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        database = os.getenv("POSTGRES_DB")
        sslmode = os.getenv("POSTGRES_SSLMODE")
        ssl_cert_verify = os.getenv("SSL_CERT_VERIFY")
        node_tls = os.getenv("NODE_TLS_REJECT_UNAUTHORIZED")

        # Log all environment variable states
        logger.info(
            f"{LOG_PREFIX} _build_connection_url: Environment variables:\n"
            f"  POSTGRES_HOST={host!r}\n"
            f"  POSTGRES_PORT={port!r}\n"
            f"  POSTGRES_USER={_mask_sensitive(user) if user else None!r}\n"
            f"  POSTGRES_PASSWORD={'<set>' if password else '<not set>'}\n"
            f"  POSTGRES_DB={database!r}\n"
            f"  POSTGRES_SSLMODE={sslmode!r}\n"
            f"  SSL_CERT_VERIFY={ssl_cert_verify!r}\n"
            f"  NODE_TLS_REJECT_UNAUTHORIZED={node_tls!r}"
        )

        if all([host, user, database]):
            logger.info(
                f"{LOG_PREFIX} _build_connection_url: All required components present "
                f"(host={host}, user={_mask_sensitive(user)}, database={database})"
            )
            if password:
                url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
                logger.debug(f"{LOG_PREFIX} _build_connection_url: URL built with password")
            else:
                url = f"postgresql://{user}@{host}:{port}/{database}"
                logger.warning(f"{LOG_PREFIX} _build_connection_url: URL built WITHOUT password")

            # Add SSL mode if specified (note: asyncpg ignores this, we handle SSL separately)
            if sslmode:
                original_sslmode = sslmode
                # Normalize "true" to "require" for common usage
                if sslmode.lower() in ("true", "1", "yes"):
                    sslmode = "require"
                    logger.info(f"{LOG_PREFIX} _build_connection_url: Normalized sslmode '{original_sslmode}' -> 'require'")
                url = f"{url}?sslmode={sslmode}"
                logger.info(f"{LOG_PREFIX} _build_connection_url: Added sslmode={sslmode} to URL")
            else:
                logger.info(f"{LOG_PREFIX} _build_connection_url: No POSTGRES_SSLMODE set, URL has no sslmode parameter")

            logger.info(
                f"{LOG_PREFIX} _build_connection_url: SUCCESS - Built URL: "
                f"postgresql://{_mask_sensitive(user)}:****@{host}:{port}/{database}"
                f"{'?sslmode=' + sslmode if sslmode else ''}"
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

            logger.warning(
                f"{LOG_PREFIX} _build_connection_url: FAILED - Missing required env vars: {missing}"
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
        logger.info(f"{LOG_PREFIX} get_connection_url: START - Resolving connection URL")

        # First try building from individual components (more explicit)
        logger.info(f"{LOG_PREFIX} get_connection_url: Step 1 - Trying POSTGRES_* env vars")
        url = self._build_connection_url()

        if url:
            logger.info(
                f"{LOG_PREFIX} get_connection_url: SUCCESS - Built URL from POSTGRES_* env vars"
            )
            return url

        # Fall back to DATABASE_URL env var
        logger.info(f"{LOG_PREFIX} get_connection_url: Step 2 - POSTGRES_* incomplete, trying DATABASE_URL")
        provider_config = self._get_provider_config()
        env_url = provider_config.get("env_connection_url", DEFAULT_CONNECTION_URL_ENV_VAR)

        logger.info(
            f"{LOG_PREFIX} get_connection_url: Checking env var '{env_url}'"
        )

        url = os.getenv(env_url)

        if url:
            logger.info(
                f"{LOG_PREFIX} get_connection_url: SUCCESS - Found URL in env var '{env_url}' "
                f"(masked={_mask_sensitive(url)})"
            )
            return url

        logger.error(
            f"{LOG_PREFIX} get_connection_url: FAILED - No connection URL available.\n"
            f"  Set POSTGRES_HOST + POSTGRES_USER + POSTGRES_DB env vars, OR\n"
            f"  Set {env_url} env var with full connection string"
        )
        return None

    def get_connection_config(self) -> dict:
        """
        Get connection configuration as a dictionary.

        Returns individual connection parameters for use with ORMs
        or direct database connections.

        Returns:
            dict with host, port, database, username, password, ssl keys
        """
        logger.info(f"{LOG_PREFIX} get_connection_config: START - Building connection config dict")

        host = os.getenv("POSTGRES_HOST", "localhost")
        port_str = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "postgres")
        username = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD")

        # Parse port
        try:
            port = int(port_str)
        except ValueError:
            logger.warning(f"{LOG_PREFIX} get_connection_config: Invalid POSTGRES_PORT '{port_str}', defaulting to 5432")
            port = 5432

        logger.info(
            f"{LOG_PREFIX} get_connection_config: Connection parameters:\n"
            f"  host={host}\n"
            f"  port={port}\n"
            f"  database={database}\n"
            f"  username={_mask_sensitive(username)}\n"
            f"  password={'<set>' if password else '<not set>'}"
        )

        # Get SSL setting for asyncpg/SQLAlchemy
        logger.info(f"{LOG_PREFIX} get_connection_config: Resolving SSL configuration...")
        ssl_context = self._get_ssl_context()

        config = {
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password,
            "ssl": ssl_context,  # For asyncpg: pass directly to connect_args
        }

        # Determine SSL description for logging
        if ssl_context is False:
            ssl_desc = "DISABLED (False)"
        elif ssl_context is True:
            ssl_desc = "ENABLED with cert verification (True)"
        elif ssl_context == "prefer":
            ssl_desc = "PREFER mode"
        elif hasattr(ssl_context, 'verify_mode'):
            ssl_desc = f"ENABLED without cert verification (SSLContext, verify_mode={ssl_context.verify_mode})"
        else:
            ssl_desc = f"UNKNOWN ({type(ssl_context).__name__})"

        logger.info(
            f"{LOG_PREFIX} get_connection_config: SUCCESS - Config built:\n"
            f"  Connection: postgresql://{_mask_sensitive(username)}:****@{host}:{port}/{database}\n"
            f"  SSL: {ssl_desc}"
        )

        return config

    def _get_ssl_context(self) -> Any:
        """
        Get SSL context based on POSTGRES_SSLMODE and SSL_CERT_VERIFY.

        IMPORTANT: asyncpg does NOT parse ?sslmode= from connection URLs.
        Unlike psycopg2 which uses libpq, asyncpg requires explicit ssl parameter.

        This method returns the appropriate value for asyncpg's ssl parameter:
        - For direct asyncpg: pass to connect(ssl=...) or create_pool(ssl=...)
        - For SQLAlchemy async: pass in connect_args={"ssl": ...}

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

        logger.info(f"{LOG_PREFIX} _get_ssl_context: START - Determining SSL configuration for asyncpg")
        logger.info(
            f"{LOG_PREFIX} _get_ssl_context: NOTE - asyncpg does NOT parse ?sslmode= from URLs!\n"
            f"  This method returns a value to pass explicitly to asyncpg's ssl= parameter"
        )

        # Check if SSL should be disabled via environment variables
        # SSL_CERT_VERIFY=0 or NODE_TLS_REJECT_UNAUTHORIZED=0 means disable SSL
        ssl_cert_verify = os.getenv("SSL_CERT_VERIFY", "")
        node_tls = os.getenv("NODE_TLS_REJECT_UNAUTHORIZED", "")
        sslmode = os.getenv("POSTGRES_SSLMODE", "")

        logger.info(
            f"{LOG_PREFIX} _get_ssl_context: SSL-related env vars:\n"
            f"  SSL_CERT_VERIFY={ssl_cert_verify!r}\n"
            f"  NODE_TLS_REJECT_UNAUTHORIZED={node_tls!r}\n"
            f"  POSTGRES_SSLMODE={sslmode!r}"
        )

        # Priority 1: Check SSL_CERT_VERIFY and NODE_TLS_REJECT_UNAUTHORIZED
        if ssl_cert_verify == "0" or node_tls == "0":
            logger.info(
                f"{LOG_PREFIX} _get_ssl_context: SSL DISABLED via env var override\n"
                f"  Reason: SSL_CERT_VERIFY={ssl_cert_verify!r} or NODE_TLS_REJECT_UNAUTHORIZED={node_tls!r}\n"
                f"  Returning: False (no SSL connection)"
            )
            return False

        # Priority 2: Check POSTGRES_SSLMODE
        if not sslmode:
            # No SSL mode specified = no SSL (matches Fastify default behavior)
            logger.info(
                f"{LOG_PREFIX} _get_ssl_context: SSL DISABLED (default)\n"
                f"  Reason: POSTGRES_SSLMODE not set\n"
                f"  Returning: False (no SSL connection)"
            )
            return False

        # Normalize common values
        sslmode_lower = sslmode.lower()

        if sslmode_lower in ("true", "1", "yes", "require"):
            # require = use SSL but don't verify certificate
            # This is common for managed databases like DigitalOcean
            logger.info(
                f"{LOG_PREFIX} _get_ssl_context: Creating SSLContext for 'require' mode\n"
                f"  POSTGRES_SSLMODE={sslmode!r} -> SSL enabled WITHOUT cert verification"
            )
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            logger.info(
                f"{LOG_PREFIX} _get_ssl_context: SSL ENABLED without cert verification\n"
                f"  Returning: ssl.SSLContext(check_hostname=False, verify_mode=CERT_NONE)"
            )
            return ctx

        elif sslmode_lower in ("verify-ca", "verify-full"):
            # verify-ca/verify-full = use SSL with certificate verification
            logger.info(
                f"{LOG_PREFIX} _get_ssl_context: SSL ENABLED with cert verification\n"
                f"  POSTGRES_SSLMODE={sslmode!r}\n"
                f"  Returning: True (asyncpg will use default SSL with verification)"
            )
            return True

        elif sslmode_lower in ("false", "0", "no", "disable"):
            logger.info(
                f"{LOG_PREFIX} _get_ssl_context: SSL DISABLED explicitly\n"
                f"  POSTGRES_SSLMODE={sslmode!r}\n"
                f"  Returning: False (no SSL connection)"
            )
            return False

        elif sslmode_lower == "prefer":
            # prefer means try SSL first, fall back to non-SSL
            logger.info(
                f"{LOG_PREFIX} _get_ssl_context: SSL PREFER mode\n"
                f"  POSTGRES_SSLMODE={sslmode!r}\n"
                f"  Returning: 'prefer' (try SSL, fall back to non-SSL)"
            )
            return "prefer"

        # Unknown value, default to no SSL
        logger.warning(
            f"{LOG_PREFIX} _get_ssl_context: UNKNOWN sslmode value!\n"
            f"  POSTGRES_SSLMODE={sslmode!r} is not recognized\n"
            f"  Valid values: require, verify-ca, verify-full, prefer, disable\n"
            f"  Defaulting to: False (no SSL connection)"
        )
        return False

    async def get_async_client(self) -> Optional[Any]:
        """
        Get async PostgreSQL client (asyncpg pool).

        Returns:
            asyncpg connection pool or None if unavailable
        """
        logger.info(f"{LOG_PREFIX} get_async_client: START - Creating asyncpg connection pool")

        # Step 1: Import asyncpg
        try:
            import asyncpg
            logger.info(f"{LOG_PREFIX} get_async_client: asyncpg module imported successfully")
        except ImportError as e:
            logger.error(
                f"{LOG_PREFIX} get_async_client: FAILED - asyncpg not installed!\n"
                f"  Error: {e}\n"
                f"  Fix: pip install asyncpg"
            )
            return None

        # Step 2: Get connection URL
        logger.info(f"{LOG_PREFIX} get_async_client: Step 2 - Getting connection URL")
        connection_url = self.get_connection_url()

        if not connection_url:
            logger.error(
                f"{LOG_PREFIX} get_async_client: FAILED - No connection URL available\n"
                f"  Check POSTGRES_* env vars or DATABASE_URL"
            )
            return None

        # Step 3: Strip sslmode from URL (asyncpg ignores it)
        # We pass ssl as a separate parameter
        if "?" in connection_url:
            base_url = connection_url.split("?")[0]
            query_params = connection_url.split("?")[1]
            logger.info(
                f"{LOG_PREFIX} get_async_client: Stripped query params from URL\n"
                f"  Original query: ?{query_params}\n"
                f"  Reason: asyncpg does NOT parse ?sslmode= from URLs"
            )
        else:
            base_url = connection_url
            logger.info(f"{LOG_PREFIX} get_async_client: URL has no query params to strip")

        # Step 4: Get SSL context
        logger.info(f"{LOG_PREFIX} get_async_client: Step 4 - Getting SSL configuration")
        ssl_context = self._get_ssl_context()

        # Determine SSL description for logging
        if ssl_context is False:
            ssl_desc = "DISABLED (ssl=False)"
        elif ssl_context is True:
            ssl_desc = "ENABLED with cert verification (ssl=True)"
        elif ssl_context == "prefer":
            ssl_desc = "PREFER mode (ssl='prefer')"
        elif hasattr(ssl_context, 'verify_mode'):
            ssl_desc = f"ENABLED without cert verification (ssl=SSLContext)"
        else:
            ssl_desc = f"UNKNOWN ({type(ssl_context).__name__})"

        # Step 5: Create connection pool
        logger.info(
            f"{LOG_PREFIX} get_async_client: Step 5 - Creating asyncpg pool\n"
            f"  URL (masked): {_mask_sensitive(base_url)}\n"
            f"  SSL: {ssl_desc}\n"
            f"  Pool config: min_size=1, max_size=1, timeout=10"
        )

        try:
            pool = await asyncpg.create_pool(
                base_url,
                min_size=1,
                max_size=1,
                ssl=ssl_context,
                timeout=10,
            )
            logger.info(
                f"{LOG_PREFIX} get_async_client: SUCCESS - Connection pool created!\n"
                f"  Pool size: min=1, max=1"
            )
            return pool

        except asyncpg.InvalidPasswordError as e:
            logger.error(
                f"{LOG_PREFIX} get_async_client: FAILED - Invalid password!\n"
                f"  Error: {type(e).__name__}: {e}\n"
                f"  Check: POSTGRES_PASSWORD env var"
            )
            return None

        except asyncpg.InvalidCatalogNameError as e:
            logger.error(
                f"{LOG_PREFIX} get_async_client: FAILED - Database does not exist!\n"
                f"  Error: {type(e).__name__}: {e}\n"
                f"  Check: POSTGRES_DB env var"
            )
            return None

        except OSError as e:
            # Connection refused, host unreachable, etc.
            error_msg = str(e)
            if "SSL" in error_msg or "ssl" in error_msg:
                logger.error(
                    f"{LOG_PREFIX} get_async_client: FAILED - SSL connection error!\n"
                    f"  Error: {type(e).__name__}: {e}\n"
                    f"  Current SSL setting: {ssl_desc}\n"
                    f"  If server doesn't support SSL, set SSL_CERT_VERIFY=0 or POSTGRES_SSLMODE=disable"
                )
            else:
                logger.error(
                    f"{LOG_PREFIX} get_async_client: FAILED - Connection error!\n"
                    f"  Error: {type(e).__name__}: {e}\n"
                    f"  Check: POSTGRES_HOST and POSTGRES_PORT env vars"
                )
            return None

        except Exception as e:
            logger.error(
                f"{LOG_PREFIX} get_async_client: FAILED - Unexpected error!\n"
                f"  Error: {type(e).__name__}: {e}\n"
                f"  URL (masked): {_mask_sensitive(base_url)}\n"
                f"  SSL: {ssl_desc}"
            )
            return None

    def get_api_key(self) -> ApiKeyResult:
        """
        Return connection info as ApiKeyResult.

        For database connections, the api_key field contains the connection URL.

        Returns:
            ApiKeyResult with connection URL as api_key
        """
        logger.info(f"{LOG_PREFIX} get_api_key: START - Creating ApiKeyResult for PostgreSQL")

        connection_url = self.get_connection_url()

        # Get raw credentials for the result
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")

        logger.info(
            f"{LOG_PREFIX} get_api_key: Credentials:\n"
            f"  POSTGRES_USER={_mask_sensitive(user) if user else '<not set>'}\n"
            f"  POSTGRES_PASSWORD={'<set>' if password else '<not set>'}\n"
            f"  connection_url={'<resolved>' if connection_url else '<not resolved>'}"
        )

        if connection_url:
            logger.info(
                f"{LOG_PREFIX} get_api_key: SUCCESS - Connection URL resolved\n"
                f"  URL (masked): {_mask_sensitive(connection_url)}"
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
                f"{LOG_PREFIX} get_api_key: WARNING - No connection URL available\n"
                f"  has_credentials will be False"
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

        logger.info(
            f"{LOG_PREFIX} get_api_key: RESULT:\n"
            f"  has_credentials={result.has_credentials}\n"
            f"  is_placeholder={result.is_placeholder}\n"
            f"  auth_type={result.auth_type}"
        )
        return result
