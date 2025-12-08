"""
Confluence API token getter.
"""
import os
import base64
from .base import BaseApiToken, ApiKeyResult


class ConfluenceApiToken(BaseApiToken):
    """API token getter for Confluence (Atlassian Cloud)."""

    @property
    def provider_name(self) -> str:
        return "confluence"

    @property
    def health_endpoint(self) -> str:
        return "/wiki/rest/api/user/current"

    def _get_email(self) -> str | None:
        """Get Confluence email from config or environment."""
        provider_config = self._get_provider_config()
        env_email = provider_config.get("env_email", "CONFLUENCE_EMAIL")
        return os.getenv(env_email)

    def get_api_key(self) -> ApiKeyResult:
        """Get Confluence API token with Basic Auth (email:token)."""
        api_token = self._lookup_env_api_key()
        email = self._get_email()

        if api_token and email:
            credentials = f"{email}:{api_token}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return ApiKeyResult(
                api_key=f"Basic {encoded}",
                auth_type="basic",
                header_name="Authorization",
                username=email,
            )

        return ApiKeyResult(
            api_key=None,
            auth_type="basic",
            header_name="Authorization",
            username=email,
        )

    def get_base_url(self) -> str | None:
        """Get Confluence base URL, checking env var if not in config."""
        base_url = super().get_base_url()
        if not base_url:
            base_url = os.getenv("CONFLUENCE_BASE_URL")
        return base_url
