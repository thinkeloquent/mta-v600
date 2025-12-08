"""
Figma API token getter.

This module provides API token resolution for the Figma API.
Figma uses the X-Figma-Token header for authentication.
"""
import logging
from typing import Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)


class FigmaApiToken(BaseApiToken):
    """
    API token getter for Figma.

    Figma uses a custom header 'X-Figma-Token' for authentication.
    The token is typically a personal access token generated from
    Figma account settings.

    Configuration:
        providers.figma.base_url: "https://api.figma.com/v1"
        providers.figma.env_api_key: "FIGMA_TOKEN"

    Environment Variables:
        FIGMA_TOKEN: Personal access token from Figma
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Figma."""
        return "figma"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for Figma.

        The /v1/me endpoint returns the current user's information
        and is a reliable way to verify token validity.
        """
        logger.debug("FigmaApiToken.health_endpoint: Returning /v1/me")
        return "/v1/me"

    def get_api_key(self) -> ApiKeyResult:
        """
        Get Figma API token from environment.

        Returns:
            ApiKeyResult configured for Figma's X-Figma-Token header
        """
        logger.debug("FigmaApiToken.get_api_key: Starting API key resolution")

        api_key = self._lookup_env_api_key()

        if api_key:
            logger.debug(
                f"FigmaApiToken.get_api_key: Found API key "
                f"(length={len(api_key)}, masked={_mask_sensitive(api_key)})"
            )
            result = ApiKeyResult(
                api_key=api_key,
                auth_type="x-api-key",
                header_name="X-Figma-Token",
            )
        else:
            logger.warning(
                "FigmaApiToken.get_api_key: No API key found. "
                "Ensure FIGMA_TOKEN environment variable is set."
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="x-api-key",
                header_name="X-Figma-Token",
            )

        logger.debug(
            f"FigmaApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result
