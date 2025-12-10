"""
Confluence API token getter.

This module provides API token resolution for the Confluence (Atlassian Cloud) API.
Uses Basic Authentication with email:token format.
"""
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive
from .auth_header_factory import AuthHeaderFactory

logger = logging.getLogger(__name__)

# Default environment variable names
DEFAULT_EMAIL_ENV_VAR = "CONFLUENCE_EMAIL"
DEFAULT_BASE_URL_ENV_VAR = "CONFLUENCE_BASE_URL"

# Fallback to Jira credentials (same Atlassian account)
FALLBACK_EMAIL_ENV_VAR = "JIRA_EMAIL"
FALLBACK_API_TOKEN_ENV_VAR = "JIRA_API_TOKEN"
FALLBACK_BASE_URL_ENV_VAR = "JIRA_BASE_URL"


class ConfluenceApiToken(BaseApiToken):
    """
    API token getter for Confluence (Atlassian Cloud).

    Confluence Cloud uses Basic Authentication with the format:
    Authorization: Basic base64(email:api_token)

    Configuration:
        providers.confluence.base_url: null (set via CONFLUENCE_BASE_URL)
        providers.confluence.env_api_key: "CONFLUENCE_API_TOKEN"
        providers.confluence.env_email: "CONFLUENCE_EMAIL"
        providers.confluence.health_endpoint: "/wiki/rest/api/user/current"

    Environment Variables:
        CONFLUENCE_API_TOKEN: API token from Atlassian account settings
        CONFLUENCE_EMAIL: Email address associated with the Atlassian account
        CONFLUENCE_BASE_URL: Base URL for the Confluence instance
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Confluence."""
        return "confluence"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for Confluence.

        The /rest/api/user/current endpoint returns the current user's
        information and is a reliable way to verify token validity.
        Note: base_url already includes /wiki path.
        """
        logger.debug("ConfluenceApiToken.health_endpoint: Returning /rest/api/user/current")
        return "/rest/api/user/current"

    def _get_email(self) -> Optional[str]:
        """
        Get Confluence email from environment.

        Uses base class _lookup_email() which reads from env_email in YAML config.
        Falls back to DEFAULT_EMAIL_ENV_VAR, then FALLBACK_EMAIL_ENV_VAR (JIRA_EMAIL)
        since both are Atlassian products using the same credentials.

        Returns:
            Email address or None if not found
        """
        logger.debug("ConfluenceApiToken._get_email: Getting email from environment")

        # Try base class lookup (from env_email in config)
        email = self._lookup_email()

        if email:
            logger.debug(
                f"ConfluenceApiToken._get_email: Found email via base class lookup: "
                f"'{email[:3]}***@***' (masked)"
            )
            return email

        # Fall back to default env var
        logger.debug(
            f"ConfluenceApiToken._get_email: Base class lookup returned None, "
            f"trying default env var '{DEFAULT_EMAIL_ENV_VAR}'"
        )
        email = os.getenv(DEFAULT_EMAIL_ENV_VAR)

        if email:
            logger.debug(
                f"ConfluenceApiToken._get_email: Found email in default env var "
                f"'{DEFAULT_EMAIL_ENV_VAR}': '{email[:3]}***@***' (masked)"
            )
            return email

        # Fallback to JIRA_EMAIL (same Atlassian account)
        logger.debug(
            f"ConfluenceApiToken._get_email: Default env var not set, "
            f"trying fallback '{FALLBACK_EMAIL_ENV_VAR}'"
        )
        email = os.getenv(FALLBACK_EMAIL_ENV_VAR)

        if email:
            logger.debug(
                f"ConfluenceApiToken._get_email: Found email in fallback env var "
                f"'{FALLBACK_EMAIL_ENV_VAR}': '{email[:3]}***@***' (masked)"
            )
        else:
            logger.debug(
                f"ConfluenceApiToken._get_email: Neither default nor "
                f"fallback env vars are set"
            )

        return email

    def _lookup_env_api_key(self) -> Optional[str]:
        """
        Lookup API token from environment variable.

        Checks CONFLUENCE_API_TOKEN first, then falls back to JIRA_API_TOKEN
        since both are Atlassian products using the same credentials.

        Returns:
            API token value or None if not found
        """
        logger.debug("ConfluenceApiToken._lookup_env_api_key: Looking up API token")

        # First try the standard lookup (CONFLUENCE_API_TOKEN)
        api_token = super()._lookup_env_api_key()

        if api_token:
            return api_token

        # Fallback to JIRA_API_TOKEN (same Atlassian account)
        logger.debug(
            f"ConfluenceApiToken._lookup_env_api_key: Primary env var not set, "
            f"trying fallback '{FALLBACK_API_TOKEN_ENV_VAR}'"
        )
        api_token = os.getenv(FALLBACK_API_TOKEN_ENV_VAR)

        if api_token:
            logger.debug(
                f"ConfluenceApiToken._lookup_env_api_key: Found API token in fallback env var "
                f"'{FALLBACK_API_TOKEN_ENV_VAR}' (length={len(api_token)})"
            )
        else:
            logger.debug(
                f"ConfluenceApiToken._lookup_env_api_key: Fallback env var "
                f"'{FALLBACK_API_TOKEN_ENV_VAR}' is also not set"
            )

        return api_token

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
        logger.debug("ConfluenceApiToken._encode_basic_auth: Encoding credentials via AuthHeaderFactory")

        if not email or not token:
            logger.error(
                "ConfluenceApiToken._encode_basic_auth: "
                f"Invalid inputs - email_empty={not email}, token_empty={not token}"
            )
            raise ValueError("Both email and token are required for Basic Auth encoding")

        auth_header = AuthHeaderFactory.create_basic(email, token)

        logger.debug(
            f"ConfluenceApiToken._encode_basic_auth: "
            f"Encoded credentials (length={len(auth_header.header_value)})"
        )

        return auth_header.header_value

    def get_api_key(self) -> ApiKeyResult:
        """
        Get Confluence API token with Basic Auth (email:token).

        Returns:
            ApiKeyResult configured for Basic Authentication
        """
        logger.debug("ConfluenceApiToken.get_api_key: Starting API key resolution")

        api_token = self._lookup_env_api_key()
        email = self._get_email()

        # Log the state of both required credentials
        logger.debug(
            f"ConfluenceApiToken.get_api_key: Credential state - "
            f"has_token={api_token is not None}, has_email={email is not None}"
        )

        if api_token and email:
            logger.debug(
                "ConfluenceApiToken.get_api_key: Both email and token found, "
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
                    f"ConfluenceApiToken.get_api_key: Successfully created Basic Auth result "
                    f"for user '{email[:3]}***@***'"
                )
            except ValueError as e:
                logger.error(
                    f"ConfluenceApiToken.get_api_key: Failed to encode credentials: {e}"
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
                "ConfluenceApiToken.get_api_key: API token found but email is missing. "
                "Set CONFLUENCE_EMAIL environment variable."
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
                "ConfluenceApiToken.get_api_key: Email found but API token is missing. "
                "Set CONFLUENCE_API_TOKEN environment variable."
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
                "ConfluenceApiToken.get_api_key: Neither email nor token found. "
                "Set both CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN environment variables."
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
            f"ConfluenceApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result

    def get_base_url(self) -> Optional[str]:
        """
        Get Confluence base URL, checking env vars with fallback to JIRA_BASE_URL.

        Resolution order:
        1. Static config 'base_url'
        2. CONFLUENCE_BASE_URL env var
        3. JIRA_BASE_URL + '/wiki' (since Confluence is typically at /wiki path)

        Returns:
            Base URL string or None if not configured
        """
        logger.debug("ConfluenceApiToken.get_base_url: Getting base URL")

        # First try the standard config resolution
        base_url = super().get_base_url()

        if base_url:
            logger.debug(
                f"ConfluenceApiToken.get_base_url: Found base URL from config: '{base_url}'"
            )
            return base_url

        # Fall back to CONFLUENCE_BASE_URL env var
        logger.debug(
            f"ConfluenceApiToken.get_base_url: Checking env var '{DEFAULT_BASE_URL_ENV_VAR}'"
        )
        base_url = os.getenv(DEFAULT_BASE_URL_ENV_VAR)

        if base_url:
            logger.debug(
                f"ConfluenceApiToken.get_base_url: Found base URL from env var: '{base_url}'"
            )
            return base_url

        # Fallback: derive from JIRA_BASE_URL (append /wiki)
        logger.debug(
            f"ConfluenceApiToken.get_base_url: Checking fallback env var "
            f"'{FALLBACK_BASE_URL_ENV_VAR}'"
        )
        jira_base_url = os.getenv(FALLBACK_BASE_URL_ENV_VAR)

        if jira_base_url:
            # Remove trailing slash and append /wiki
            base_url = jira_base_url.rstrip("/") + "/wiki"
            logger.debug(
                f"ConfluenceApiToken.get_base_url: Derived base URL from JIRA_BASE_URL: "
                f"'{base_url}'"
            )
            return base_url

        logger.warning(
            f"ConfluenceApiToken.get_base_url: No base URL configured. "
            f"Set {DEFAULT_BASE_URL_ENV_VAR} or {FALLBACK_BASE_URL_ENV_VAR} environment variable."
        )

        return None

    def get_network_config(self) -> Dict[str, Any]:
        """
        Get provider-specific network/proxy configuration.

        Reads from YAML config fields:
        - proxy_url: Proxy URL for requests
        - ca_bundle: CA bundle path for SSL verification
        - cert: Client certificate path
        - cert_verify: SSL certificate verification flag
        - agent_proxy.http_proxy: HTTP proxy for agent
        - agent_proxy.https_proxy: HTTPS proxy for agent

        Returns:
            Dictionary with network configuration values
        """
        logger.debug("ConfluenceApiToken.get_network_config: Getting network configuration")

        provider_config = self._get_provider_config()

        # Get agent_proxy nested config
        agent_proxy = provider_config.get("agent_proxy", {}) or {}

        config = {
            "proxy_url": provider_config.get("proxy_url"),
            "ca_bundle": provider_config.get("ca_bundle"),
            "cert": provider_config.get("cert"),
            "cert_verify": provider_config.get("cert_verify", False),
            "agent_proxy": {
                "http_proxy": agent_proxy.get("http_proxy"),
                "https_proxy": agent_proxy.get("https_proxy"),
            },
        }

        logger.debug(
            f"ConfluenceApiToken.get_network_config: Resolved config - "
            f"proxy_url={config['proxy_url']}, "
            f"ca_bundle={config['ca_bundle']}, "
            f"cert={config['cert']}, "
            f"cert_verify={config['cert_verify']}, "
            f"agent_proxy={config['agent_proxy']}"
        )

        return config

    def _get_service_config(self) -> Dict[str, Any]:
        """
        Get service configuration from static config.

        Returns:
            Service configuration dictionary from .services.{provider_name}
        """
        logger.debug(
            f"ConfluenceApiToken._get_service_config: Getting service config for '{self.provider_name}'"
        )

        try:
            config = self.config_store.get_nested("services", self.provider_name)
            if config is None:
                logger.debug(
                    f"ConfluenceApiToken._get_service_config: No service config found, returning empty dict"
                )
                return {}
            logger.debug(
                f"ConfluenceApiToken._get_service_config: Found service config with keys: {list(config.keys())}"
            )
            return config
        except Exception as e:
            logger.error(
                f"ConfluenceApiToken._get_service_config: Exception while getting config: {e}"
            )
            return {}

    def get_service_config(self) -> Dict[str, Any]:
        """
        Get downstream service configuration.

        Returns the entire service configuration dictionary from .services.confluence
        which can contain arbitrary key-value pairs for downstream service config.

        Example YAML:
            services:
              confluence:
                headers:
                  X-Atlassian-Token: "no-check"
                default_expand: "body.storage,version"
                pagination:
                  limit: 25

        Returns:
            Dictionary with all service configuration values
        """
        logger.debug("ConfluenceApiToken.get_service_config: Getting service configuration")

        service_config = self._get_service_config()

        logger.debug(
            f"ConfluenceApiToken.get_service_config: Returning config with "
            f"{len(service_config)} keys: {list(service_config.keys())}"
        )

        return service_config

    def get_env_by_name(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get environment variable value by name from service config.

        Looks up env_{name} in the service config to get the environment variable name,
        then resolves the actual value from the environment.

        Example:
            YAML config:
                services:
                  confluence:
                    env_space_key: "CONFLUENCE_SPACE_KEY"

            Code:
                space_key = provider.get_env_by_name("space_key")
                # Reads env var name from config: "CONFLUENCE_SPACE_KEY"
                # Returns os.getenv("CONFLUENCE_SPACE_KEY")

        Args:
            name: The name suffix (without 'env_' prefix)
            default: Default value if env var is not set

        Returns:
            Environment variable value or default
        """
        logger.debug(f"ConfluenceApiToken.get_env_by_name: Looking up env_{name}")

        service_config = self._get_service_config()
        env_key = f"env_{name}"
        env_var_name = service_config.get(env_key)

        if not env_var_name:
            logger.debug(
                f"ConfluenceApiToken.get_env_by_name: No '{env_key}' found in service config, "
                f"returning default: {default}"
            )
            return default

        value = os.getenv(env_var_name, default)

        logger.debug(
            f"ConfluenceApiToken.get_env_by_name: Resolved {env_key}='{env_var_name}' -> "
            f"value={'<set>' if value else '<not set>'}"
        )

        return value

    def get_headers(self) -> Dict[str, str]:
        """
        Get default headers from service configuration.

        Returns:
            Dictionary of default headers for API requests
        """
        logger.debug("ConfluenceApiToken.get_headers: Getting default headers")

        service_config = self._get_service_config()
        headers = service_config.get("headers", {}) or {}

        logger.debug(
            f"ConfluenceApiToken.get_headers: Found {len(headers)} headers: {list(headers.keys())}"
        )

        return headers

    def get_endpoints(self) -> Dict[str, str]:
        """
        Get API endpoints from service configuration.

        Returns:
            Dictionary of endpoint paths
        """
        logger.debug("ConfluenceApiToken.get_endpoints: Getting endpoints")

        service_config = self._get_service_config()
        endpoints = service_config.get("endpoints", {}) or {}

        logger.debug(
            f"ConfluenceApiToken.get_endpoints: Found {len(endpoints)} endpoints: {list(endpoints.keys())}"
        )

        return endpoints

    def get_pagination_defaults(self) -> Dict[str, Any]:
        """
        Get pagination defaults from service configuration.

        Returns:
            Dictionary with pagination settings (limit, start, etc.)
        """
        logger.debug("ConfluenceApiToken.get_pagination_defaults: Getting pagination defaults")

        service_config = self._get_service_config()
        pagination = service_config.get("pagination", {}) or {}

        logger.debug(
            f"ConfluenceApiToken.get_pagination_defaults: Found pagination config: {pagination}"
        )

        return pagination
