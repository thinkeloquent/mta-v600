"""
ServiceNow API token getter.
"""
import logging
import os
from typing import Optional

from .base import BaseApiToken, ApiKeyResult, _mask_sensitive

logger = logging.getLogger(__name__)

# Default environment variable for ServiceNow password/token
DEFAULT_SERVICENOW_PASSWORD_ENV = "SERVICENOW_PASSWORD"
DEFAULT_SERVICENOW_USERNAME_ENV = "SERVICENOW_USERNAME"
DEFAULT_SERVICENOW_INSTANCE_ENV = "SERVICENOW_INSTANCE"


class ServicenowApiToken(BaseApiToken):
    """
    API token getter for ServiceNow.

    Uses Basic authentication (username:password).

    Configuration:
        providers.servicenow.base_url: "https://{instance}.service-now.com"
        providers.servicenow.env_api_key: "SERVICENOW_PASSWORD"
        providers.servicenow.username: "admin"

    Environment Variables:
        SERVICENOW_PASSWORD: Password for ServiceNow user
        SERVICENOW_USERNAME: Username for ServiceNow user
        SERVICENOW_INSTANCE: Instance name (e.g. dev12345)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "servicenow"

    @property
    def health_endpoint(self) -> str:
        """
        Return the health check endpoint.
        
        Using sys_user table with limit 1 is a standard connectivity check.
        """
        return "/api/now/table/sys_user?sysparm_limit=1"

    def get_base_url(self) -> Optional[str]:
        """Get the base URL for ServiceNow."""
        logger.debug(f"{self.__class__.__name__}.get_base_url: Getting base URL")

        # Try config first
        base_url = super().get_base_url()

        # If not in config, try constructing from instance name env var
        if not base_url:
            instance = os.getenv(DEFAULT_SERVICENOW_INSTANCE_ENV)
            if instance:
                base_url = f"https://{instance}.service-now.com"
                logger.debug(f"Constructed base URL from instance: {base_url}")

        return base_url

    def get_api_key(self) -> ApiKeyResult:
        """Get API credentials for ServiceNow."""
        logger.debug(f"{self.__class__.__name__}.get_api_key: Starting resolution")

        # Get password (api key)
        password = self._lookup_env_api_key()
        if not password:
             password = os.getenv(DEFAULT_SERVICENOW_PASSWORD_ENV)

        # Get username from config or env
        provider_config = self._get_provider_config()
        username = provider_config.get("username") or os.getenv(DEFAULT_SERVICENOW_USERNAME_ENV)

        if password and username:
            return ApiKeyResult(
                api_key=password,
                auth_type="basic",  # fetch_client handles basic auth joining
                header_name="Authorization",
                email=username,     # storing username in email field for basic auth
                raw_api_key=password,
            )
        
        logger.warning("ServiceNow credentials incomplete (need username and password)")
        return ApiKeyResult(
            api_key=None,
            auth_type="basic",
            header_name="Authorization",
            email=None,
            raw_api_key=None,
        )
