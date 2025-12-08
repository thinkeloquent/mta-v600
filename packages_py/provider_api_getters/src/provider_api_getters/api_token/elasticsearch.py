"""
Elasticsearch API token getter (placeholder).

This module provides a placeholder implementation for Elasticsearch integration.
Elasticsearch integration is not yet implemented.
"""
import logging
from typing import Optional

from .base import BaseApiToken, ApiKeyResult

logger = logging.getLogger(__name__)


class ElasticsearchApiToken(BaseApiToken):
    """
    API token getter for Elasticsearch (placeholder - not implemented).

    This is a placeholder class that returns a not-implemented result.
    Elasticsearch integration will be implemented in a future version.

    Configuration:
        providers.elasticsearch.placeholder: true
        providers.elasticsearch.message: "Elasticsearch integration not implemented"
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

    def get_api_key(self) -> ApiKeyResult:
        """
        Return placeholder result for Elasticsearch.

        Since Elasticsearch integration is not implemented, this always returns
        a placeholder result with an explanatory message.

        Returns:
            ApiKeyResult marked as placeholder with explanatory message
        """
        logger.debug("ElasticsearchApiToken.get_api_key: Starting placeholder resolution")

        provider_config = self._get_provider_config()

        is_placeholder = provider_config.get("placeholder", True)
        message = provider_config.get("message", "Elasticsearch integration not implemented")

        logger.debug(
            f"ElasticsearchApiToken.get_api_key: Config - "
            f"is_placeholder={is_placeholder}, message='{message}'"
        )

        if is_placeholder:
            logger.info(
                f"ElasticsearchApiToken.get_api_key: Returning placeholder result - {message}"
            )
            result = ApiKeyResult(
                api_key=None,
                is_placeholder=True,
                placeholder_message=message,
            )
        else:
            # If placeholder is explicitly set to False, treat as not configured
            logger.warning(
                "ElasticsearchApiToken.get_api_key: Elasticsearch is not a placeholder but "
                "no implementation exists. Returning empty result."
            )
            result = ApiKeyResult(
                api_key=None,
                is_placeholder=False,
                placeholder_message=None,
            )

        logger.debug(
            f"ElasticsearchApiToken.get_api_key: Returning result "
            f"is_placeholder={result.is_placeholder}"
        )
        return result
