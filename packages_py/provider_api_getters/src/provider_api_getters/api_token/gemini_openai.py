"""
Gemini/OpenAI API token getter.

Supports OpenAI-compatible APIs including:
- Google Gemini (via OpenAI compatibility layer)
- OpenAI
- Other OpenAI-compatible endpoints
"""
from .base import BaseApiToken, ApiKeyResult


class GeminiOpenAIApiToken(BaseApiToken):
    """API token getter for Gemini/OpenAI-compatible APIs."""

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def health_endpoint(self) -> str:
        return "/models"

    def get_api_key(self) -> ApiKeyResult:
        """Get API key for Gemini/OpenAI-compatible API."""
        api_key = self._lookup_env_api_key()
        return ApiKeyResult(
            api_key=api_key,
            auth_type="bearer",
            header_name="Authorization",
        )
