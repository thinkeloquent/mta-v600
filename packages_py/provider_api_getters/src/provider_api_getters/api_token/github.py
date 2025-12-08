"""
GitHub API token getter.
"""
import os
from .base import BaseApiToken, ApiKeyResult


class GithubApiToken(BaseApiToken):
    """API token getter for GitHub."""

    # Fallback environment variable names for GitHub token
    FALLBACK_ENV_VARS = ["GITHUB_TOKEN", "GH_TOKEN", "GITHUB_ACCESS_TOKEN", "GITHUB_PAT"]

    @property
    def provider_name(self) -> str:
        return "github"

    @property
    def health_endpoint(self) -> str:
        return "/user"

    def get_api_key(self) -> ApiKeyResult:
        """Get GitHub API token from environment with fallbacks."""
        api_key = self._lookup_env_api_key()

        if not api_key:
            for env_var in self.FALLBACK_ENV_VARS:
                api_key = os.getenv(env_var)
                if api_key:
                    break

        return ApiKeyResult(
            api_key=api_key,
            auth_type="bearer",
            header_name="Authorization",
        )
