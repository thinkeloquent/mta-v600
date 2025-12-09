"""
Rally API token getter (placeholder).

This module provides a placeholder implementation for Rally integration.
Rally integration is not yet implemented.
"""
import logging
from typing import Optional

from .base import BaseApiToken, ApiKeyResult

logger = logging.getLogger(__name__)


class RallyApiToken(BaseApiToken):
    """
    API token getter for Rally (placeholder - not implemented).

    This is a placeholder class that returns a not-implemented result.
    Rally integration will be implemented in a future version.

    Configuration:
        providers.rally.placeholder: true
        providers.rally.message: "Rally integration not implemented"
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Rally."""
        return "rally"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for Rally.

        Returns a placeholder endpoint since Rally is not implemented.
        """
        logger.debug("RallyApiToken.health_endpoint: Returning placeholder endpoint /")
        return "/"

    def get_api_key(self) -> ApiKeyResult:
        """
        Return placeholder result for Rally.

        Since Rally integration is not implemented, this always returns
        a placeholder result with an explanatory message.

        Returns:
            ApiKeyResult marked as placeholder with explanatory message
        """
        logger.debug("RallyApiToken.get_api_key: Starting placeholder resolution")

        provider_config = self._get_provider_config()

        is_placeholder = provider_config.get("placeholder", True)
        message = provider_config.get("message", "Rally integration not implemented")

        logger.debug(
            f"RallyApiToken.get_api_key: Config - "
            f"is_placeholder={is_placeholder}, message='{message}'"
        )

        if is_placeholder:
            logger.info(
                f"RallyApiToken.get_api_key: Returning placeholder result - {message}"
            )
            result = ApiKeyResult(
                api_key=None,
                is_placeholder=True,
                placeholder_message=message,
                email=None,
                raw_api_key=None,
            )
        else:
            # If placeholder is explicitly set to False, treat as not configured
            logger.warning(
                "RallyApiToken.get_api_key: Rally is not a placeholder but "
                "no implementation exists. Returning empty result."
            )
            result = ApiKeyResult(
                api_key=None,
                is_placeholder=False,
                placeholder_message=None,
                email=None,
                raw_api_key=None,
            )

        logger.debug(
            f"RallyApiToken.get_api_key: Returning result "
            f"is_placeholder={result.is_placeholder}"
        )
        return result
