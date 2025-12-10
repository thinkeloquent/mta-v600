"""
Akamai Edge API token getter.

This module provides API token resolution for Akamai Edge APIs.
Akamai uses EdgeGrid authentication, which requires:
- client_token
- client_secret
- access_token
- host

These can be provided via environment variables or .edgerc file.

API Documentation:
    https://techdocs.akamai.com/developer/docs/authenticate-with-edgegrid
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Default .edgerc file location
DEFAULT_EDGERC_PATH = Path.home() / ".edgerc"


@dataclass
class EdgeGridCredentials:
    """Akamai EdgeGrid credentials."""
    client_token: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    host: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if all required credentials are present."""
        return all([
            self.client_token,
            self.client_secret,
            self.access_token,
            self.host
        ])


class AkamaiApiToken(BaseApiToken):
    """
    API token getter for Akamai Edge APIs.

    Akamai uses EdgeGrid authentication which requires four credentials:
    - client_token: Client token from Akamai Control Center
    - client_secret: Client secret from Akamai Control Center
    - access_token: Access token from Akamai Control Center
    - host: Akamai API hostname (e.g., akab-xxx.luna.akamaiapis.net)

    Configuration:
        providers.akamai.base_url: null (derived from host)
        providers.akamai.env_client_token: "AKAMAI_CLIENT_TOKEN"
        providers.akamai.env_client_secret: "AKAMAI_CLIENT_SECRET"
        providers.akamai.env_access_token: "AKAMAI_ACCESS_TOKEN"
        providers.akamai.env_host: "AKAMAI_HOST"

    Environment Variables:
        AKAMAI_CLIENT_TOKEN: Client token
        AKAMAI_CLIENT_SECRET: Client secret
        AKAMAI_ACCESS_TOKEN: Access token
        AKAMAI_HOST: API hostname

    Alternative: .edgerc file
        If environment variables are not set, credentials can be read from
        ~/.edgerc file in INI format (default section).
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name for Akamai."""
        return "akamai"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint for Akamai.

        The /-/client-api/active-grants/implicit endpoint returns
        information about the current API client's grants.
        """
        logger.debug("AkamaiApiToken.health_endpoint: Returning /-/client-api/active-grants/implicit")
        return "/-/client-api/active-grants/implicit"

    def _get_env_var_name(self, key: str) -> Optional[str]:
        """Get environment variable name from config for a specific key."""
        provider_config = self._get_provider_config()
        if provider_config:
            return provider_config.get(f"env_{key}")
        return None

    def _get_credentials_from_env(self) -> EdgeGridCredentials:
        """Get EdgeGrid credentials from environment variables."""
        logger.debug("AkamaiApiToken._get_credentials_from_env: Checking environment variables")

        client_token_var = self._get_env_var_name("client_token") or "AKAMAI_CLIENT_TOKEN"
        client_secret_var = self._get_env_var_name("client_secret") or "AKAMAI_CLIENT_SECRET"
        access_token_var = self._get_env_var_name("access_token") or "AKAMAI_ACCESS_TOKEN"
        host_var = self._get_env_var_name("host") or "AKAMAI_HOST"

        credentials = EdgeGridCredentials(
            client_token=os.getenv(client_token_var),
            client_secret=os.getenv(client_secret_var),
            access_token=os.getenv(access_token_var),
            host=os.getenv(host_var),
        )

        if credentials.is_valid:
            logger.debug("AkamaiApiToken._get_credentials_from_env: Found valid credentials in environment")
        else:
            missing = []
            if not credentials.client_token:
                missing.append(client_token_var)
            if not credentials.client_secret:
                missing.append(client_secret_var)
            if not credentials.access_token:
                missing.append(access_token_var)
            if not credentials.host:
                missing.append(host_var)
            logger.debug(f"AkamaiApiToken._get_credentials_from_env: Missing env vars: {missing}")

        return credentials

    def _get_credentials_from_edgerc(self, section: str = "default") -> EdgeGridCredentials:
        """
        Get EdgeGrid credentials from .edgerc file.

        The .edgerc file is in INI format:
            [default]
            client_secret = xxxx
            host = akab-xxx.luna.akamaiapis.net
            access_token = akab-xxx
            client_token = akab-xxx
        """
        logger.debug(f"AkamaiApiToken._get_credentials_from_edgerc: Checking {DEFAULT_EDGERC_PATH}")

        if not DEFAULT_EDGERC_PATH.exists():
            logger.debug(f"AkamaiApiToken._get_credentials_from_edgerc: File not found: {DEFAULT_EDGERC_PATH}")
            return EdgeGridCredentials()

        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(DEFAULT_EDGERC_PATH)

            if section not in config:
                logger.debug(f"AkamaiApiToken._get_credentials_from_edgerc: Section [{section}] not found")
                return EdgeGridCredentials()

            credentials = EdgeGridCredentials(
                client_token=config.get(section, "client_token", fallback=None),
                client_secret=config.get(section, "client_secret", fallback=None),
                access_token=config.get(section, "access_token", fallback=None),
                host=config.get(section, "host", fallback=None),
            )

            if credentials.is_valid:
                logger.debug(f"AkamaiApiToken._get_credentials_from_edgerc: Found valid credentials in [{section}]")
            else:
                logger.debug(f"AkamaiApiToken._get_credentials_from_edgerc: Incomplete credentials in [{section}]")

            return credentials
        except Exception as e:
            logger.warning(f"AkamaiApiToken._get_credentials_from_edgerc: Error reading .edgerc: {e}")
            return EdgeGridCredentials()

    def get_credentials(self) -> EdgeGridCredentials:
        """
        Get EdgeGrid credentials from environment or .edgerc file.

        Priority:
        1. Environment variables
        2. .edgerc file [default] section
        """
        # Try environment variables first
        credentials = self._get_credentials_from_env()
        if credentials.is_valid:
            return credentials

        # Fall back to .edgerc file
        credentials = self._get_credentials_from_edgerc()
        return credentials

    def get_api_key(self) -> ApiKeyResult:
        """
        Get Akamai EdgeGrid credentials.

        For Akamai, the api_key field contains a JSON-encoded string with
        all four EdgeGrid credentials. The auth_type is "edgegrid".

        Returns:
            ApiKeyResult with EdgeGrid credentials
        """
        logger.debug("AkamaiApiToken.get_api_key: Starting credential resolution")

        credentials = self.get_credentials()

        if credentials.is_valid:
            import json
            # Store credentials as JSON in api_key field
            credentials_json = json.dumps({
                "client_token": credentials.client_token,
                "client_secret": credentials.client_secret,
                "access_token": credentials.access_token,
                "host": credentials.host,
            })

            logger.debug(
                f"AkamaiApiToken.get_api_key: Found credentials for host "
                f"{_mask_sensitive(credentials.host or '')}"
            )

            result = ApiKeyResult(
                api_key=credentials_json,
                auth_type="edgegrid",
                header_name="Authorization",  # EdgeGrid uses Authorization header
                email=None,
                raw_api_key=credentials.access_token,  # Use access_token as raw key
                username=credentials.client_token,  # Store client_token for reference
            )
        else:
            logger.warning(
                "AkamaiApiToken.get_api_key: No valid credentials found. "
                "Set AKAMAI_CLIENT_TOKEN, AKAMAI_CLIENT_SECRET, AKAMAI_ACCESS_TOKEN, "
                "AKAMAI_HOST environment variables or create ~/.edgerc file."
            )
            result = ApiKeyResult(
                api_key=None,
                auth_type="edgegrid",
                header_name="Authorization",
                email=None,
                raw_api_key=None,
            )

        logger.debug(
            f"AkamaiApiToken.get_api_key: Returning result "
            f"has_credentials={result.has_credentials}"
        )
        return result

    def get_base_url(self) -> Optional[str]:
        """
        Get the base URL for Akamai API.

        The base URL is derived from the host credential.
        """
        credentials = self.get_credentials()
        if credentials.host:
            # Ensure host has https:// prefix
            host = credentials.host
            if not host.startswith("https://"):
                host = f"https://{host}"
            return host
        return super().get_base_url()
