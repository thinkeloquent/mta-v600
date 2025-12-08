"""
Jira API token getter.
"""
import os
import base64
from .base import BaseApiToken, ApiKeyResult


class JiraApiToken(BaseApiToken):
    """API token getter for Jira (Atlassian Cloud)."""

    @property
    def provider_name(self) -> str:
        return "jira"

    @property
    def health_endpoint(self) -> str:
        return "/rest/api/2/myself"

    def _get_email(self) -> str | None:
        """Get Jira email from config or environment."""
        provider_config = self._get_provider_config()
        env_email = provider_config.get("env_email", "JIRA_EMAIL")
        return os.getenv(env_email)

    def get_api_key(self) -> ApiKeyResult:
        """Get Jira API token with Basic Auth (email:token)."""
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
        """Get Jira base URL, checking env var if not in config."""
        base_url = super().get_base_url()
        if not base_url:
            base_url = os.getenv("JIRA_BASE_URL")
        return base_url
