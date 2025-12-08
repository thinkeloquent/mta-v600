"""
Elasticsearch connection getter.

Returns an Elasticsearch connection URL or client instance.

Environment Variables:
    ELASTIC_DB_USERNAME: Elasticsearch username
    ELASTIC_DB_ACCESS_KEY: Elasticsearch password/access key
    ELASTIC_DB_HOST: Elasticsearch host (default: localhost)
    ELASTIC_DB_PORT: Elasticsearch port (default: 9200)
"""
import logging
import os
from typing import Any, Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Default environment variable names
DEFAULT_CONNECTION_URL_ENV_VAR = "ELASTIC_DB_URL"


class ElasticsearchApiToken(BaseApiToken):
    """
    Connection getter for Elasticsearch.

    Returns connection URL information rather than API key.
    Supports both connection URL and individual component configuration.

    Configuration:
        providers.elasticsearch.env_connection_url: "ELASTIC_DB_URL"

    Environment Variables:
        ELASTIC_DB_URL: Full Elasticsearch connection URL
        ELASTIC_DB_HOST: Elasticsearch host (default: localhost)
        ELASTIC_DB_PORT: Elasticsearch port (default: 9200)
        ELASTIC_DB_USERNAME: Elasticsearch username
        ELASTIC_DB_ACCESS_KEY: Elasticsearch password/access key
        ELASTIC_DB_TLS: Enable TLS (default: false, auto-enabled for ports 443, 9243)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Elasticsearch."""
        return "elasticsearch"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for Elasticsearch.

        The /_cluster/health endpoint is the standard health check for Elasticsearch.
        """
        logger.debug("ElasticsearchApiToken.health_endpoint: Returning /_cluster/health")
        return "/_cluster/health"

    def _build_connection_url(self) -> str:
        """
        Build connection URL from individual environment variables.

        Uses https:// when ELASTIC_DB_TLS=true or port is 443/9243.

        Returns:
            Connection URL string
        """
        logger.debug("ElasticsearchApiToken._build_connection_url: Building URL from components")

        host = os.getenv("ELASTIC_DB_HOST", "localhost")
        port = os.getenv("ELASTIC_DB_PORT", "9200")
        username = os.getenv("ELASTIC_DB_USERNAME")
        password = os.getenv("ELASTIC_DB_ACCESS_KEY")

        # Determine if TLS should be used
        # - Explicit ELASTIC_DB_TLS=true
        # - Known TLS ports (443, 9243 is Elastic Cloud, 25060 is DigitalOcean)
        elastic_tls = os.getenv("ELASTIC_DB_TLS", "").lower() in ("true", "1", "yes")
        tls_ports = {"443", "9243", "25060"}
        use_tls = elastic_tls or port in tls_ports

        scheme = "https" if use_tls else "http"

        logger.debug(
            f"ElasticsearchApiToken._build_connection_url: Components - "
            f"host={host}, port={port}, "
            f"username={username is not None}, password={'***' if password else None}, "
            f"use_tls={use_tls}, scheme={scheme}"
        )

        if username and password:
            url = f"{scheme}://{username}:{password}@{host}:{port}"
            logger.debug(
                f"ElasticsearchApiToken._build_connection_url: Built URL with username and password "
                f"(masked={_mask_sensitive(url)})"
            )
        elif password:
            # Some setups use API key as password without username
            url = f"{scheme}://:{password}@{host}:{port}"
            logger.debug(
                f"ElasticsearchApiToken._build_connection_url: Built URL with password only "
                f"(masked={_mask_sensitive(url)})"
            )
        else:
            url = f"{scheme}://{host}:{port}"
            logger.debug(
                f"ElasticsearchApiToken._build_connection_url: Built URL without auth "
                f"(url={url})"
            )

        return url

    def get_connection_url(self) -> str:
        """
        Get Elasticsearch connection URL.

        First checks for ELASTIC_DB_URL env var, then builds from components.

        Returns:
            Connection URL string
        """
        logger.debug("ElasticsearchApiToken.get_connection_url: Starting connection URL resolution")

        # Get env var name from config
        provider_config = self._get_provider_config()
        env_url = provider_config.get("env_connection_url", DEFAULT_CONNECTION_URL_ENV_VAR)

        logger.debug(
            f"ElasticsearchApiToken.get_connection_url: Checking env var '{env_url}'"
        )

        url = os.getenv(env_url)

        if url:
            logger.debug(
                f"ElasticsearchApiToken.get_connection_url: Found URL in env var '{env_url}' "
                f"(masked={_mask_sensitive(url)})"
            )
            return url
        else:
            logger.debug(
                f"ElasticsearchApiToken.get_connection_url: Env var '{env_url}' not set, "
                "building from components"
            )

        # Build from components
        url = self._build_connection_url()

        logger.debug(
            "ElasticsearchApiToken.get_connection_url: Built URL from components"
        )

        return url

    def get_connection_config(self) -> dict[str, Any]:
        """
        Get connection configuration dict for elasticsearch-py client.

        Returns:
            Configuration dict with hosts and auth info
        """
        logger.debug("ElasticsearchApiToken.get_connection_config: Building connection config")

        host = os.getenv("ELASTIC_DB_HOST", "localhost")
        port = os.getenv("ELASTIC_DB_PORT", "9200")
        username = os.getenv("ELASTIC_DB_USERNAME")
        password = os.getenv("ELASTIC_DB_ACCESS_KEY")

        # Determine if TLS should be used
        elastic_tls = os.getenv("ELASTIC_DB_TLS", "").lower() in ("true", "1", "yes")
        tls_ports = {"443", "9243", "25060"}
        use_tls = elastic_tls or port in tls_ports

        scheme = "https" if use_tls else "http"
        node = f"{scheme}://{host}:{port}"

        config: dict[str, Any] = {
            "hosts": [node],
            # Skip product verification to support OpenSearch and other ES-compatible servers
            "verify_certs": True,
            "meta_header": False,
        }

        if username and password:
            config["basic_auth"] = (username, password)
            logger.debug(
                f"ElasticsearchApiToken.get_connection_config: Built config with basic auth "
                f"(node={node}, username={username})"
            )
        elif password:
            # API key authentication
            config["api_key"] = password
            logger.debug(
                f"ElasticsearchApiToken.get_connection_config: Built config with API key auth "
                f"(node={node})"
            )
        else:
            logger.debug(
                f"ElasticsearchApiToken.get_connection_config: Built config without auth "
                f"(node={node})"
            )

        return config

    def get_sync_client(self) -> Optional[Any]:
        """
        Get sync Elasticsearch client.

        Returns:
            Elasticsearch client instance or None if unavailable
        """
        logger.debug("ElasticsearchApiToken.get_sync_client: Getting sync Elasticsearch client")

        try:
            from elasticsearch import Elasticsearch
            logger.debug("ElasticsearchApiToken.get_sync_client: elasticsearch module imported successfully")
        except ImportError:
            logger.warning(
                "ElasticsearchApiToken.get_sync_client: elasticsearch not installed. "
                "Install with: pip install elasticsearch"
            )
            return None

        config = self.get_connection_config()

        logger.debug("ElasticsearchApiToken.get_sync_client: Creating Elasticsearch client")

        try:
            client = Elasticsearch(**config)
            logger.debug(
                "ElasticsearchApiToken.get_sync_client: Elasticsearch client created successfully"
            )
            return client
        except Exception as e:
            logger.error(
                f"ElasticsearchApiToken.get_sync_client: Failed to create client: {type(e).__name__}: {e}"
            )
            return None

    async def get_async_client(self) -> Optional[Any]:
        """
        Get async Elasticsearch client.

        Returns:
            AsyncElasticsearch client instance or None if unavailable
        """
        logger.debug("ElasticsearchApiToken.get_async_client: Getting async Elasticsearch client")

        try:
            from elasticsearch import AsyncElasticsearch
            logger.debug("ElasticsearchApiToken.get_async_client: elasticsearch async module imported successfully")
        except ImportError:
            logger.warning(
                "ElasticsearchApiToken.get_async_client: elasticsearch[async] not installed. "
                "Install with: pip install elasticsearch[async]"
            )
            return None

        config = self.get_connection_config()

        logger.debug("ElasticsearchApiToken.get_async_client: Creating async Elasticsearch client")

        try:
            client = AsyncElasticsearch(**config)
            logger.debug(
                "ElasticsearchApiToken.get_async_client: Async Elasticsearch client created successfully"
            )
            return client
        except Exception as e:
            logger.error(
                f"ElasticsearchApiToken.get_async_client: Failed to create client: {type(e).__name__}: {e}"
            )
            return None

    def get_api_key(self) -> ApiKeyResult:
        """
        Return connection info as ApiKeyResult.

        For database connections, the api_key field contains the connection URL.

        Returns:
            ApiKeyResult with connection URL as api_key
        """
        logger.debug("ElasticsearchApiToken.get_api_key: Starting API key resolution")

        connection_url = self.get_connection_url()

        if connection_url:
            logger.debug(
                f"ElasticsearchApiToken.get_api_key: Found connection URL "
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
                "ElasticsearchApiToken.get_api_key: No connection URL available"
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="connection_string",
                header_name="",
                client=None,
            )

        logger.debug(
            f"ElasticsearchApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result
