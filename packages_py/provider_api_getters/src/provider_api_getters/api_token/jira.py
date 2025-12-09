"""
Jira API token getter.

This module provides API token resolution for the Jira/Atlassian Cloud API.
Uses Basic Authentication with email:token format.
"""
import logging
import os
from typing import Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive
from .auth_header_factory import AuthHeaderFactory

logger = logging.getLogger(__name__)

# Default environment variable names
DEFAULT_EMAIL_ENV_VAR = "JIRA_EMAIL"
DEFAULT_BASE_URL_ENV_VAR = "JIRA_BASE_URL"


class JiraApiToken(BaseApiToken):
    """
    API token getter for Jira (Atlassian Cloud).

    Jira Cloud uses Basic Authentication with the format:
    Authorization: Basic base64(email:api_token)

    Configuration:
        providers.jira.base_url: null (set via JIRA_BASE_URL)
        providers.jira.env_api_key: "JIRA_API_TOKEN"
        providers.jira.env_email: "JIRA_EMAIL"
        providers.jira.health_endpoint: "/rest/api/2/myself"

    Environment Variables:
        JIRA_API_TOKEN: API token from Atlassian account settings
        JIRA_EMAIL: Email address associated with the Atlassian account
        JIRA_BASE_URL: Base URL for the Jira instance (e.g., https://company.atlassian.net)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Jira."""
        return "jira"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for Jira.

        The /rest/api/2/myself endpoint returns the current user's information
        and is a reliable way to verify token validity.
        """
        logger.debug("JiraApiToken.health_endpoint: Returning /rest/api/2/myself")
        return "/rest/api/2/myself"

    def _get_email(self) -> Optional[str]:
        """
        Get Jira email from environment.

        Uses base class _lookup_email() which reads from env_email in YAML config.
        Falls back to DEFAULT_EMAIL_ENV_VAR if not in config.

        Returns:
            Email address or None if not found
        """
        logger.debug("JiraApiToken._get_email: Getting email from environment")

        # Try base class lookup (from env_email in config)
        email = self._lookup_email()

        if email:
            logger.debug(
                f"JiraApiToken._get_email: Found email via base class lookup: "
                f"'{email[:3]}***@***' (masked)"
            )
            return email

        # Fall back to default env var if not in config
        logger.debug(
            f"JiraApiToken._get_email: Base class lookup returned None, "
            f"trying default env var '{DEFAULT_EMAIL_ENV_VAR}'"
        )
        email = os.getenv(DEFAULT_EMAIL_ENV_VAR)

        if email:
            logger.debug(
                f"JiraApiToken._get_email: Found email in default env var "
                f"'{DEFAULT_EMAIL_ENV_VAR}': '{email[:3]}***@***' (masked)"
            )
        else:
            logger.debug(
                f"JiraApiToken._get_email: Default env var '{DEFAULT_EMAIL_ENV_VAR}' is not set"
            )

        return email

    def _encode_basic_auth(self, email: str, token: str) -> str:
        """
        Encode email and token for Basic Authentication.

        Uses AuthHeaderFactory for RFC-compliant encoding.

        Args:
            email: The email address
            token: The API token

        Returns:
            Base64-encoded credentials string with 'Basic ' prefix
        """
        logger.debug("JiraApiToken._encode_basic_auth: Encoding credentials via AuthHeaderFactory")

        if not email or not token:
            logger.error(
                "JiraApiToken._encode_basic_auth: "
                f"Invalid inputs - email_empty={not email}, token_empty={not token}"
            )
            raise ValueError("Both email and token are required for Basic Auth encoding")

        auth_header = AuthHeaderFactory.create_basic(email, token)

        logger.debug(
            f"JiraApiToken._encode_basic_auth: "
            f"Encoded credentials (length={len(auth_header.header_value)})"
        )

        return auth_header.header_value

    def get_api_key(self) -> ApiKeyResult:
        """
        Get Jira API token with Basic Auth (email:token).

        Returns:
            ApiKeyResult configured for Basic Authentication
        """
        logger.debug("JiraApiToken.get_api_key: Starting API key resolution")

        api_token = self._lookup_env_api_key()
        email = self._get_email()

        # Log the state of both required credentials
        logger.debug(
            f"JiraApiToken.get_api_key: Credential state - "
            f"has_token={api_token is not None}, has_email={email is not None}"
        )

        if api_token and email:
            logger.debug(
                "JiraApiToken.get_api_key: Both email and token found, "
                "encoding Basic Auth credentials"
            )
            try:
                encoded_auth = self._encode_basic_auth(email, api_token)
                result = ApiKeyResult(
                    api_key=encoded_auth,
                    auth_type="basic",
                    header_name="Authorization",
                    username=email,
                    email=email,
                    raw_api_key=api_token,
                )
                logger.debug(
                    f"JiraApiToken.get_api_key: Successfully created Basic Auth result "
                    f"for user '{email[:3]}***@***'"
                )
            except ValueError as e:
                logger.error(
                    f"JiraApiToken.get_api_key: Failed to encode credentials: {e}"
                )
                result = ApiKeyResult(
                    api_key=None,
                    auth_type="basic",
                    header_name="Authorization",
                    username=email,
                    email=email,
                    raw_api_key=api_token,
                )
        elif api_token and not email:
            logger.warning(
                "JiraApiToken.get_api_key: API token found but email is missing. "
                "Set JIRA_EMAIL environment variable."
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="basic",
                header_name="Authorization",
                username=None,
                email=None,
                raw_api_key=api_token,
            )
        elif email and not api_token:
            logger.warning(
                "JiraApiToken.get_api_key: Email found but API token is missing. "
                "Set JIRA_API_TOKEN environment variable."
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="basic",
                header_name="Authorization",
                username=email,
                email=email,
                raw_api_key=None,
            )
        else:
            logger.warning(
                "JiraApiToken.get_api_key: Neither email nor token found. "
                "Set both JIRA_EMAIL and JIRA_API_TOKEN environment variables."
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="basic",
                header_name="Authorization",
                username=None,
                email=None,
                raw_api_key=None,
            )

        logger.debug(
            f"JiraApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result

    def get_base_url(self) -> Optional[str]:
        """
        Get Jira base URL, checking env var if not in config.

        Returns:
            Base URL string or None if not configured
        """
        logger.debug("JiraApiToken.get_base_url: Getting base URL")

        # First try the standard config resolution
        base_url = super().get_base_url()

        if base_url:
            logger.debug(
                f"JiraApiToken.get_base_url: Found base URL from config: '{base_url}'"
            )
            return base_url

        # Fall back to JIRA_BASE_URL env var
        logger.debug(
            f"JiraApiToken.get_base_url: Checking fallback env var '{DEFAULT_BASE_URL_ENV_VAR}'"
        )
        base_url = os.getenv(DEFAULT_BASE_URL_ENV_VAR)

        if base_url:
            logger.debug(
                f"JiraApiToken.get_base_url: Found base URL from env var: '{base_url}'"
            )
        else:
            logger.warning(
                f"JiraApiToken.get_base_url: No base URL configured. "
                f"Set {DEFAULT_BASE_URL_ENV_VAR} environment variable."
            )

        return base_url
