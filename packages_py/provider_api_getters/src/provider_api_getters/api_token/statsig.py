from typing import Optional
import os
import logging
from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Default environment variable for Statsig API key
DEFAULT_STATSIG_API_KEY_ENV = "STATSIG_API_KEY"


class StatsigApiToken(BaseApiToken):
    """
    Statsig API Token provider.

    Expected Configuration:
    - base_url: The API base URL (default: https://statsigapi.net/console/v1)
    - env_api_key: Name of environment variable for token (default: STATSIG_API_KEY)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "statsig"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint.
        
        Using /gates to verify connectivity and auth.
        """
        return "/gates"

    def get_base_url(self) -> Optional[str]:
        """Get the base URL for Statsig."""
        logger.debug(f"{self.__class__.__name__}.get_base_url: Getting base URL")
        
        # Try config first
        base_url = super().get_base_url()
        
        # Default if not configured
        if not base_url:
            base_url = "https://statsigapi.net/console/v1"
            logger.debug(f"Using default base URL: {base_url}")
            
        return base_url

    def get_api_key(self) -> ApiKeyResult:
        """Get API credentials for Statsig."""
        logger.debug(f"{self.__class__.__name__}.get_api_key: Starting resolution")

        # Try config-specified env var first
        api_key = self._lookup_env_api_key()

        # Fall back to default env var
        if not api_key:
            api_key = os.getenv(DEFAULT_STATSIG_API_KEY_ENV)

        if api_key:
            logger.debug(
                f"{self.__class__.__name__}.get_api_key: Found API key "
                f"(length={len(api_key)}, masked={_mask_sensitive(api_key)})"
            )
            return ApiKeyResult(
                api_key=api_key,
                auth_type="custom_header",
                header_name="statsig-api-key",
                raw_api_key=api_key,
            )

        logger.warning(
            f"{self.__class__.__name__}.get_api_key: No API key found. "
            f"Ensure {DEFAULT_STATSIG_API_KEY_ENV} environment variable is set."
        )
        return ApiKeyResult(
            api_key=None,
            auth_type="custom_header",
            header_name="statsig-api-key",
            raw_api_key=None,
            is_placeholder=False,
        )
