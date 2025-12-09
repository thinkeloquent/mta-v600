"""
API token getters for external providers.

Each provider has its own class that handles API key resolution:
- Simple ENV variable lookup
- Computed values based on request context (OAuth, per-tenant, etc.)
"""
from .base import BaseApiToken, ApiKeyResult, RequestContext
from .auth_header_factory import AuthHeaderFactory, AuthHeader, AuthScheme, CONFIG_AUTH_TYPE_MAP
from .figma import FigmaApiToken
from .github import GithubApiToken
from .jira import JiraApiToken
from .confluence import ConfluenceApiToken
from .gemini_openai import GeminiOpenAIApiToken
from .postgres import PostgresApiToken
from .redis import RedisApiToken
from .rally import RallyApiToken
from .elasticsearch import ElasticsearchApiToken
from .saucelabs import SaucelabsApiToken

# Registry mapping provider names to their token classes
PROVIDER_REGISTRY: dict[str, type[BaseApiToken]] = {
    "figma": FigmaApiToken,
    "github": GithubApiToken,
    "jira": JiraApiToken,
    "confluence": ConfluenceApiToken,
    "gemini": GeminiOpenAIApiToken,
    "gemini_openai": GeminiOpenAIApiToken,
    "openai": GeminiOpenAIApiToken,
    "postgres": PostgresApiToken,
    "redis": RedisApiToken,
    "rally": RallyApiToken,
    "elasticsearch": ElasticsearchApiToken,
    "saucelabs": SaucelabsApiToken,
}


def get_api_token_class(provider_name: str) -> type[BaseApiToken] | None:
    """Get the API token class for a provider name."""
    return PROVIDER_REGISTRY.get(provider_name.lower())


__all__ = [
    "BaseApiToken",
    "ApiKeyResult",
    "RequestContext",
    "AuthHeaderFactory",
    "AuthHeader",
    "AuthScheme",
    "CONFIG_AUTH_TYPE_MAP",
    "FigmaApiToken",
    "GithubApiToken",
    "JiraApiToken",
    "ConfluenceApiToken",
    "GeminiOpenAIApiToken",
    "PostgresApiToken",
    "RedisApiToken",
    "RallyApiToken",
    "ElasticsearchApiToken",
    "SaucelabsApiToken",
    "get_api_token_class",
    "PROVIDER_REGISTRY",
]
