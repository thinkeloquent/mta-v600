"""
Rally API token getter (placeholder).
"""
from .base import BaseApiToken, ApiKeyResult


class RallyApiToken(BaseApiToken):
    """API token getter for Rally (placeholder - not implemented)."""

    @property
    def provider_name(self) -> str:
        return "rally"

    @property
    def health_endpoint(self) -> str:
        return "/"

    def get_api_key(self) -> ApiKeyResult:
        """Return placeholder result."""
        provider_config = self._get_provider_config()
        message = provider_config.get("message", "Rally integration not implemented")

        return ApiKeyResult(
            api_key=None,
            is_placeholder=True,
            placeholder_message=message,
        )
