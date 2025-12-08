"""
Provider API token getters and health check utilities.

This package provides:
- api_token: Class-based token getters for each provider
- fetch_client: Factory for creating pre-configured HTTP clients
- health_check: Provider health checking utilities
"""
from .api_token import (
    BaseApiToken,
    ApiKeyResult,
    RequestContext,
    FigmaApiToken,
    GithubApiToken,
    JiraApiToken,
    ConfluenceApiToken,
    GeminiOpenAIApiToken,
    PostgresApiToken,
    RedisApiToken,
    RallyApiToken,
    ElasticsearchApiToken,
    get_api_token_class,
    PROVIDER_REGISTRY,
)
from .fetch_client import (
    ProviderClientFactory,
    get_provider_client,
)
from .health_check import (
    ProviderHealthChecker,
    ProviderConnectionResponse,
    check_provider_connection,
)

__all__ = [
    # Base types
    "BaseApiToken",
    "ApiKeyResult",
    "RequestContext",
    # Provider token classes
    "FigmaApiToken",
    "GithubApiToken",
    "JiraApiToken",
    "ConfluenceApiToken",
    "GeminiOpenAIApiToken",
    "PostgresApiToken",
    "RedisApiToken",
    "RallyApiToken",
    "ElasticsearchApiToken",
    # Registry
    "get_api_token_class",
    "PROVIDER_REGISTRY",
    # Fetch client factory
    "ProviderClientFactory",
    "get_provider_client",
    # Health check
    "ProviderHealthChecker",
    "ProviderConnectionResponse",
    "check_provider_connection",
]

__version__ = "1.0.0"
