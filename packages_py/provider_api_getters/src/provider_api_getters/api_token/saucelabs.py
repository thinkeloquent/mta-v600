"""
SauceLabs API token getter.

This module provides API token resolution for the SauceLabs API.
SauceLabs uses Basic authentication with username:access_key.
Fallbacks are configured in server.{APP_ENV}.yaml under providers.saucelabs.
"""
import base64
import logging
import os
from typing import Tuple, Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)


class SaucelabsApiToken(BaseApiToken):
    """
    API token getter for SauceLabs.

    SauceLabs uses Basic authentication with username and access key.
    The credentials are combined as username:access_key and base64 encoded.

    Configuration:
        providers.saucelabs.base_url: "https://api.us-west-1.saucelabs.com"
        providers.saucelabs.env_username: "SAUCE_USERNAME"
        providers.saucelabs.env_username_fallbacks: ["SAUCELABS_USERNAME"]
        providers.saucelabs.env_api_key: "SAUCE_ACCESS_KEY"
        providers.saucelabs.env_api_key_fallbacks: ["SAUCELABS_ACCESS_KEY"]

    Environment Variables (checked in order from config):
        Username: env_username (SAUCE_USERNAME), then env_username_fallbacks
        Access Key: env_api_key (SAUCE_ACCESS_KEY), then env_api_key_fallbacks
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for SauceLabs."""
        return "saucelabs"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for SauceLabs.

        The /rest/v1/users/{username} endpoint returns user info
        and verifies credentials are valid.
        """
        username, _ = self._lookup_username()
        if username:
            endpoint = f"/rest/v1/users/{username}"
            logger.debug(f"SaucelabsApiToken.health_endpoint: Returning {endpoint}")
            return endpoint
        # Fallback - will fail but provide meaningful error
        logger.debug("SaucelabsApiToken.health_endpoint: No username found, returning placeholder")
        return "/rest/v1/users/:username"

    def _get_username_env_vars(self) -> Tuple[str, ...]:
        """
        Get username environment variable names from config.

        Returns:
            Tuple of (primary, ...fallbacks) environment variable names
        """
        provider_config = self._get_provider_config()
        primary = provider_config.get("env_username")
        fallbacks = provider_config.get("env_username_fallbacks", [])

        if primary:
            return (primary,) + tuple(fallbacks)
        return tuple(fallbacks)

    def _lookup_username(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Lookup SauceLabs username from environment.

        Returns:
            Tuple of (username, source_env_var_name) or (None, None) if not found
        """
        env_vars = self._get_username_env_vars()
        for env_var in env_vars:
            username = os.getenv(env_var)
            if username:
                logger.debug(
                    f"SaucelabsApiToken._lookup_username: "
                    f"Found username in '{env_var}'"
                )
                return username, env_var
        return None, None

    def _get_access_key_env_vars(self) -> Tuple[str, ...]:
        """
        Get access key environment variable names from config.

        Returns:
            Tuple of (primary, ...fallbacks) environment variable names
        """
        primary = self._get_env_api_key_name()
        fallbacks = self._get_env_api_key_fallbacks()

        if primary:
            return (primary,) + tuple(fallbacks)
        return tuple(fallbacks)

    def _lookup_access_key(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Lookup SauceLabs access key from environment.

        Returns:
            Tuple of (access_key, source_env_var_name) or (None, None) if not found
        """
        env_vars = self._get_access_key_env_vars()
        for env_var in env_vars:
            access_key = os.getenv(env_var)
            if access_key:
                logger.debug(
                    f"SaucelabsApiToken._lookup_access_key: "
                    f"Found access key in '{env_var}'"
                )
                return access_key, env_var
        return None, None

    def get_api_key(self) -> ApiKeyResult:
        """
        Get SauceLabs credentials from environment.

        SauceLabs uses Basic auth with username:access_key format.

        Returns:
            ApiKeyResult configured for SauceLabs Basic authentication
        """
        logger.debug("SaucelabsApiToken.get_api_key: Starting API key resolution")

        username, username_var = self._lookup_username()
        access_key, access_key_var = self._lookup_access_key()

        if username and access_key:
            # Combine as username:access_key and base64 encode for Basic auth
            combined_key = f"{username}:{access_key}"
            encoded_credentials = base64.b64encode(combined_key.encode()).decode()
            basic_auth_value = f"Basic {encoded_credentials}"
            logger.debug(
                f"SaucelabsApiToken.get_api_key: Found credentials from "
                f"'{username_var}' and '{access_key_var}' "
                f"(masked={_mask_sensitive(combined_key)})"
            )
            result = ApiKeyResult(
                api_key=basic_auth_value,
                auth_type="basic",
                header_name="Authorization",
            )
        else:
            missing = []
            if not username:
                username_vars = self._get_username_env_vars()
                missing.append(f"username ({username_vars})")
            if not access_key:
                access_key_vars = self._get_access_key_env_vars()
                missing.append(f"access_key ({access_key_vars})")
            logger.warning(
                f"SaucelabsApiToken.get_api_key: Missing credentials: {', '.join(missing)}"
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="basic",
                header_name="Authorization",
            )

        logger.debug(
            f"SaucelabsApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result
