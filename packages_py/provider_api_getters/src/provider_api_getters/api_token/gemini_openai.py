"""
Gemini/OpenAI API token getter.

Supports OpenAI-compatible APIs including:
- Google Gemini (via OpenAI compatibility layer)
- OpenAI
- Other OpenAI-compatible endpoints
"""
import logging
import os
from typing import Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Default environment variable for Gemini API key
DEFAULT_GEMINI_API_KEY_ENV = "GEMINI_API_KEY"

# Default base URL for Gemini OpenAI-compatible API
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiOpenAIApiToken(BaseApiToken):
    """
    API token getter for Gemini/OpenAI-compatible APIs.

    Uses Bearer token authentication standard to OpenAI-compatible APIs.

    Configuration:
        providers.gemini_openai.base_url: "https://generativelanguage.googleapis.com/v1beta/openai"
        providers.gemini_openai.env_api_key: "GEMINI_API_KEY"

    Environment Variables:
        GEMINI_API_KEY: API key for Google Gemini
        OPENAI_API_KEY: Fallback API key for OpenAI-compatible services
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Gemini OpenAI-compatible API."""
        return "gemini_openai"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for Gemini/OpenAI-compatible APIs.

        The models endpoint returns the list of available models
        and is a reliable way to verify API key validity.

        Note: Use relative path (without leading /) to preserve base_url path.
        """
        logger.debug("GeminiOpenAIApiToken.health_endpoint: Returning models (relative)")
        return "models"

    def get_base_url(self) -> Optional[str]:
        """
        Get the base URL for Gemini API.

        Resolution order:
        1. Config-specified base_url (from providers.gemini.base_url)
        2. Default Gemini OpenAI-compatible base URL

        Returns:
            Base URL string
        """
        logger.debug("GeminiOpenAIApiToken.get_base_url: Getting base URL")

        # Try config first
        base_url = super().get_base_url()

        # Fall back to default
        if not base_url:
            logger.debug(
                f"GeminiOpenAIApiToken.get_base_url: Config lookup failed, "
                f"using default: {DEFAULT_GEMINI_BASE_URL}"
            )
            base_url = DEFAULT_GEMINI_BASE_URL

        logger.debug(f"GeminiOpenAIApiToken.get_base_url: Resolved to '{base_url}'")
        return base_url

    def get_api_key(self) -> ApiKeyResult:
        """
        Get API key for Gemini/OpenAI-compatible API.

        Resolution order:
        1. Config-specified env var (from providers.gemini.env_api_key)
        2. Default GEMINI_API_KEY environment variable

        Returns:
            ApiKeyResult configured for Bearer authentication
        """
        logger.debug("GeminiOpenAIApiToken.get_api_key: Starting API key resolution")

        # Try config-specified env var first
        api_key = self._lookup_env_api_key()

        # Fall back to default GEMINI_API_KEY
        if not api_key:
            logger.debug(
                f"GeminiOpenAIApiToken.get_api_key: Config lookup failed, "
                f"trying default env var '{DEFAULT_GEMINI_API_KEY_ENV}'"
            )
            api_key = os.getenv(DEFAULT_GEMINI_API_KEY_ENV)

        if api_key:
            logger.debug(
                f"GeminiOpenAIApiToken.get_api_key: Found API key "
                f"(length={len(api_key)}, masked={_mask_sensitive(api_key)})"
            )
            result = ApiKeyResult(
                api_key=api_key,
                auth_type="bearer",
                header_name="Authorization",
                email=None,
                raw_api_key=api_key,
            )
        else:
            logger.warning(
                "GeminiOpenAIApiToken.get_api_key: No API key found. "
                f"Ensure {DEFAULT_GEMINI_API_KEY_ENV} environment variable is set."
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="bearer",
                header_name="Authorization",
                email=None,
                raw_api_key=None,
            )

        logger.debug(
            f"GeminiOpenAIApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result
