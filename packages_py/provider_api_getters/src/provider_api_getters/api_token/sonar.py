"""
Sonar API token getter.

This module provides API token resolution for SonarQube/SonarCloud APIs.
Supports multiple fallback environment variable names for flexibility.
Fallbacks are configured in server.{APP_ENV}.yaml under providers.sonar.env_api_key_fallbacks.

Authentication:
    SonarQube/SonarCloud uses Bearer token authentication.
    Token is passed in the Authorization header: "Bearer <token>"

API Documentation:
    SonarCloud: https://sonarcloud.io/web_api
    SonarQube: https://docs.sonarqube.org/latest/extension-guide/web-api/
"""
import logging
import os
from typing import Optional, Tuple

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Default fallback environment variable names for Sonar tokens
# These are used when no fallbacks are configured in YAML
SONAR_FALLBACK_ENV_VARS: Tuple[str, ...] = (
    "SONARQUBE_TOKEN",
    "SONARCLOUD_TOKEN",
    "SONAR_API_TOKEN",
)


class SonarApiToken(BaseApiToken):
    """
    API token getter for SonarQube/SonarCloud.

    SonarQube and SonarCloud use Bearer token authentication. This implementation
    supports multiple fallback environment variable names commonly used for
    Sonar tokens.

    Configuration:
        providers.sonar.base_url: "https://sonarcloud.io" or "https://your-sonar.example.com"
        providers.sonar.env_api_key: "SONAR_TOKEN"
        providers.sonar.env_api_key_fallbacks: ["SONARQUBE_TOKEN", "SONARCLOUD_TOKEN"]

    Environment Variables (checked in order from config):
        Primary: env_api_key (SONAR_TOKEN)
        Fallbacks: env_api_key_fallbacks (SONARQUBE_TOKEN, SONARCLOUD_TOKEN, SONAR_API_TOKEN)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Sonar."""
        return "sonar"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for Sonar.

        The /api/system/status endpoint returns the system status
        and is available without authentication for basic health checks.
        For authenticated health checks, /api/authentication/validate is used.
        """
        logger.debug("SonarApiToken.health_endpoint: Returning /api/authentication/validate")
        return "/api/authentication/validate"

    def _get_fallback_env_vars(self) -> Tuple[str, ...]:
        """
        Get the list of fallback environment variable names from config.

        Returns:
            Tuple of environment variable names to check (from config or default)
        """
        fallbacks = self._get_env_api_key_fallbacks()
        if fallbacks:
            return tuple(fallbacks)
        # Use default fallbacks when not configured
        return SONAR_FALLBACK_ENV_VARS

    def _lookup_with_fallbacks(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Lookup API key from environment with fallbacks.

        Checks the configured env_api_key first, then falls back to
        the standard Sonar environment variable names.

        Returns:
            Tuple of (api_key, source_env_var_name) or (None, None) if not found
        """
        logger.debug("SonarApiToken._lookup_with_fallbacks: Starting lookup with fallbacks")

        # First try the configured env key
        configured_key = self._get_env_api_key_name()
        if configured_key:
            logger.debug(
                f"SonarApiToken._lookup_with_fallbacks: "
                f"Checking configured env var '{configured_key}'"
            )
            api_key = os.getenv(configured_key)
            if api_key:
                logger.debug(
                    f"SonarApiToken._lookup_with_fallbacks: "
                    f"Found key in configured env var '{configured_key}'"
                )
                return api_key, configured_key
            else:
                logger.debug(
                    f"SonarApiToken._lookup_with_fallbacks: "
                    f"Configured env var '{configured_key}' is not set"
                )

        # Fall back to standard env var names
        fallback_vars = self._get_fallback_env_vars()
        logger.debug(
            f"SonarApiToken._lookup_with_fallbacks: "
            f"Checking {len(fallback_vars)} fallback env vars: {fallback_vars}"
        )

        for i, env_var in enumerate(fallback_vars):
            logger.debug(
                f"SonarApiToken._lookup_with_fallbacks: "
                f"Checking fallback [{i+1}/{len(fallback_vars)}]: '{env_var}'"
            )
            api_key = os.getenv(env_var)
            if api_key:
                logger.debug(
                    f"SonarApiToken._lookup_with_fallbacks: "
                    f"Found key in fallback env var '{env_var}' "
                    f"(length={len(api_key)}, masked={_mask_sensitive(api_key)})"
                )
                return api_key, env_var
            else:
                logger.debug(
                    f"SonarApiToken._lookup_with_fallbacks: "
                    f"Fallback env var '{env_var}' is not set"
                )

        logger.debug(
            "SonarApiToken._lookup_with_fallbacks: "
            "No API key found in any env var"
        )
        return None, None

    def get_api_key(self) -> ApiKeyResult:
        """
        Get Sonar API token from environment with fallbacks.

        Checks multiple environment variable names commonly used for
        Sonar tokens.

        Returns:
            ApiKeyResult configured for Sonar Bearer authentication
        """
        logger.debug("SonarApiToken.get_api_key: Starting API key resolution")

        api_key, source_var = self._lookup_with_fallbacks()

        if api_key:
            logger.debug(
                f"SonarApiToken.get_api_key: Found API key from '{source_var}' "
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
            configured_key = self._get_env_api_key_name()
            fallback_vars = self._get_fallback_env_vars()
            all_vars = (configured_key,) + fallback_vars if configured_key else fallback_vars
            logger.warning(
                "SonarApiToken.get_api_key: No API key found. "
                f"Ensure one of these environment variables is set: {all_vars}"
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="bearer",
                header_name="Authorization",
                email=None,
                raw_api_key=None,
            )

        logger.debug(
            f"SonarApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result
