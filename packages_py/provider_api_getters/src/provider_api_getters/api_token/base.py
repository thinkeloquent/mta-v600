"""
Base class for API token getters.

This module provides the foundational classes for provider API token resolution
with comprehensive defensive programming, validation, and observability.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .auth_header_factory import AuthHeader
import logging
import os

# Import token registry for dynamic token resolution
from ..token_resolver import token_registry

# Import auth header factory - lazy import to avoid circular dependency
# Will be imported on first use in get_auth_header() method

logger = logging.getLogger(__name__)


def _mask_sensitive(value: Optional[str], visible_chars: int = 10) -> str:
    """Mask sensitive values for safe logging."""
    if value is None:
        return "<None>"
    if not isinstance(value, str):
        return "<invalid-type>"
    if len(value) <= visible_chars:
        return "*" * len(value)
    return value[:visible_chars] + "*" * (len(value) - visible_chars)


# Public alias for external use
mask_sensitive = _mask_sensitive


@dataclass
class RequestContext:
    """
    Context passed to get_api_key_for_request for dynamic token resolution.

    Attributes:
        request: The HTTP request object (FastAPI Request, Fastify Request, etc.)
        app_state: Application state object for accessing shared resources
        tenant_id: Identifier for multi-tenant token resolution
        user_id: User identifier for user-scoped tokens
        extra: Additional context data for custom resolution logic
    """

    request: Optional[Any] = None
    app_state: Optional[Any] = None
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize context after initialization."""
        logger.debug(
            "RequestContext.__post_init__: Initializing context "
            f"tenant_id={self.tenant_id}, user_id={self.user_id}, "
            f"has_request={self.request is not None}, "
            f"has_app_state={self.app_state is not None}, "
            f"extra_keys={list(self.extra.keys()) if self.extra else []}"
        )

        if self.extra is None:
            logger.debug("RequestContext.__post_init__: extra was None, defaulting to empty dict")
            self.extra = {}

        if self.tenant_id is not None and not isinstance(self.tenant_id, str):
            logger.warning(
                f"RequestContext.__post_init__: tenant_id is not a string, "
                f"got {type(self.tenant_id).__name__}, converting to str"
            )
            self.tenant_id = str(self.tenant_id)

        if self.user_id is not None and not isinstance(self.user_id, str):
            logger.warning(
                f"RequestContext.__post_init__: user_id is not a string, "
                f"got {type(self.user_id).__name__}, converting to str"
            )
            self.user_id = str(self.user_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        logger.debug("RequestContext.to_dict: Converting context to dictionary")
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "has_request": self.request is not None,
            "has_app_state": self.app_state is not None,
            "extra_keys": list(self.extra.keys()) if self.extra else [],
        }


# Valid auth types - comprehensive authentication type system
VALID_AUTH_TYPES = frozenset({
    # Basic auth family
    "basic", "basic_email_token", "basic_token", "basic_email",
    # Bearer auth family
    "bearer", "bearer_oauth", "bearer_jwt",
    "bearer_username_token", "bearer_username_password",
    "bearer_email_token", "bearer_email_password",
    # Custom/API Key
    "x-api-key", "custom", "custom_header",
    # HMAC (stub)
    "hmac",
    # Connection string (for databases)
    "connection_string",
})


@dataclass
class ApiKeyResult:
    """
    Result from API key resolution.

    Attributes:
        api_key: The resolved API key or token (may be encoded for basic auth)
        auth_type: Authentication type (bearer, x-api-key, basic, custom, connection_string)
        header_name: HTTP header name for the authentication
        username: Username for basic auth scenarios (alias for email)
        email: Email address for basic auth scenarios
        raw_api_key: The raw/unencoded API key or token
        client: Pre-configured client instance (for DB connections)
        is_placeholder: True if this provider is not yet implemented
        placeholder_message: Human-readable message for placeholder providers
    """

    api_key: Optional[str] = None
    auth_type: str = "bearer"
    header_name: str = "Authorization"
    username: Optional[str] = None
    email: Optional[str] = None
    raw_api_key: Optional[str] = None
    client: Optional[Any] = None
    is_placeholder: bool = False
    placeholder_message: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate result after initialization."""
        logger.debug(
            f"ApiKeyResult.__post_init__: Initializing result "
            f"auth_type={self.auth_type}, header_name={self.header_name}, "
            f"has_api_key={self.api_key is not None}, "
            f"has_client={self.client is not None}, "
            f"is_placeholder={self.is_placeholder}"
        )

        if self.auth_type not in VALID_AUTH_TYPES:
            logger.warning(
                f"ApiKeyResult.__post_init__: Invalid auth_type '{self.auth_type}', "
                f"expected one of {VALID_AUTH_TYPES}"
            )

        if not self.header_name:
            logger.debug("ApiKeyResult.__post_init__: header_name is empty, defaulting to Authorization")
            self.header_name = "Authorization"

        if self.is_placeholder and self.api_key is not None:
            logger.warning(
                "ApiKeyResult.__post_init__: is_placeholder=True but api_key is set, "
                "this is inconsistent"
            )

    @property
    def has_credentials(self) -> bool:
        """
        Check if valid credentials are available.

        Returns:
            True if credentials are available for authentication
        """
        logger.debug(
            f"ApiKeyResult.has_credentials: Checking credentials "
            f"is_placeholder={self.is_placeholder}, "
            f"has_client={self.client is not None}, "
            f"has_api_key={self.api_key is not None}"
        )

        if self.is_placeholder:
            logger.debug("ApiKeyResult.has_credentials: is_placeholder=True, returning False")
            return False

        if self.client is not None:
            logger.debug("ApiKeyResult.has_credentials: client is set, returning True")
            return True

        result = self.api_key is not None
        logger.debug(f"ApiKeyResult.has_credentials: api_key check result={result}")
        return result

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert result to dictionary for serialization.

        Args:
            include_sensitive: If True, include masked api_key value

        Returns:
            Dictionary representation of the result
        """
        logger.debug(f"ApiKeyResult.to_dict: Converting to dict, include_sensitive={include_sensitive}")

        result = {
            "auth_type": self.auth_type,
            "header_name": self.header_name,
            "has_api_key": self.api_key is not None,
            "has_username": self.username is not None,
            "has_client": self.client is not None,
            "is_placeholder": self.is_placeholder,
            "placeholder_message": self.placeholder_message,
            "has_credentials": self.has_credentials,
        }

        if include_sensitive:
            result["api_key_masked"] = _mask_sensitive(self.api_key)
            if self.username:
                result["username"] = self.username

        return result

    def get_auth_header(self) -> "AuthHeader":
        """
        Get an AuthHeader instance from this result.

        Uses the AuthHeaderFactory to create an RFC-compliant Authorization header
        based on the auth_type and credentials in this result.

        Returns:
            AuthHeader instance for use in HTTP requests
        """
        logger.debug(
            f"ApiKeyResult.get_auth_header: Creating auth header "
            f"auth_type={self.auth_type}, has_api_key={self.api_key is not None}"
        )

        if not self.api_key and not self.client:
            logger.warning(
                "ApiKeyResult.get_auth_header: No api_key or client available, "
                "returning null-safe header"
            )

        # Lazy import to avoid circular dependency
        from .auth_header_factory import AuthHeaderFactory

        return AuthHeaderFactory.from_api_key_result(self)


class BaseApiToken(ABC):
    """
    Base class for all provider API token getters.

    This abstract class provides the foundation for implementing provider-specific
    API token resolution. Subclasses must implement:
    - provider_name: The provider identifier
    - get_api_key(): Simple environment variable lookup

    Optionally override:
    - health_endpoint: Custom health check endpoint
    - get_api_key_for_request(): Dynamic token resolution based on request context
    - get_base_url(): Custom base URL resolution
    """

    def __init__(self, config_store: Optional[Any] = None) -> None:
        """
        Initialize the API token getter.

        Args:
            config_store: Optional ConfigStore instance. If not provided,
                         will be lazy-loaded from static_config module.
        """
        logger.debug(
            f"{self.__class__.__name__}.__init__: Initializing with "
            f"config_store={'provided' if config_store else 'None (will lazy-load)'}"
        )
        self._config_store = config_store
        self._config_cache: Optional[Dict[str, Any]] = None

    @property
    def config_store(self) -> Any:
        """
        Get config store, lazy-loading if not set.

        Returns:
            The ConfigStore instance for accessing static configuration.
        """
        if self._config_store is None:
            logger.debug(
                f"{self.__class__.__name__}.config_store: No config_store set, "
                "lazy-loading from static_config module"
            )
            try:
                from static_config import config
                self._config_store = config
                logger.debug(
                    f"{self.__class__.__name__}.config_store: Successfully loaded "
                    f"static_config, initialized={config.is_initialized() if hasattr(config, 'is_initialized') else 'unknown'}"
                )
            except ImportError as e:
                logger.error(
                    f"{self.__class__.__name__}.config_store: Failed to import static_config: {e}"
                )
                raise
        else:
            logger.debug(f"{self.__class__.__name__}.config_store: Using provided config_store")

        return self._config_store

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        The provider name as defined in static config.

        Returns:
            Provider identifier string (e.g., 'figma', 'github', 'jira')
        """
        pass

    @property
    def health_endpoint(self) -> str:
        """
        The endpoint to use for health checks.

        Returns:
            Health check endpoint path (default: '/')
        """
        logger.debug(f"{self.__class__.__name__}.health_endpoint: Getting health endpoint")

        provider_config = self._get_provider_config()
        endpoint = provider_config.get("health_endpoint", "/")

        logger.debug(
            f"{self.__class__.__name__}.health_endpoint: Resolved endpoint='{endpoint}' "
            f"(from_config={'health_endpoint' in provider_config})"
        )

        return endpoint

    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Get provider configuration from static config with caching.

        Returns:
            Provider configuration dictionary, empty dict if not found
        """
        logger.debug(
            f"{self.__class__.__name__}._get_provider_config: "
            f"Getting config for provider '{self.provider_name}'"
        )

        if self._config_cache is not None:
            logger.debug(
                f"{self.__class__.__name__}._get_provider_config: Returning cached config"
            )
            return self._config_cache

        try:
            config = self.config_store.get_nested("providers", self.provider_name)

            if config is None:
                logger.warning(
                    f"{self.__class__.__name__}._get_provider_config: "
                    f"No config found for provider '{self.provider_name}', returning empty dict"
                )
                self._config_cache = {}
            else:
                logger.debug(
                    f"{self.__class__.__name__}._get_provider_config: "
                    f"Found config with keys: {list(config.keys())}"
                )
                self._config_cache = config

            return self._config_cache

        except Exception as e:
            logger.error(
                f"{self.__class__.__name__}._get_provider_config: "
                f"Exception while getting config: {type(e).__name__}: {e}",
                exc_info=True
            )
            self._config_cache = {}
            return self._config_cache

    def _get_env_api_key_name(self) -> Optional[str]:
        """
        Get the environment variable name for the API key.

        Returns:
            Environment variable name or None if not configured
        """
        logger.debug(f"{self.__class__.__name__}._get_env_api_key_name: Getting env key name")

        provider_config = self._get_provider_config()
        env_key_name = provider_config.get("env_api_key")

        if env_key_name:
            logger.debug(
                f"{self.__class__.__name__}._get_env_api_key_name: "
                f"Found env_api_key='{env_key_name}'"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}._get_env_api_key_name: "
                "No env_api_key configured"
            )

        return env_key_name

    def _get_env_api_key_fallbacks(self) -> list[str]:
        """
        Get the fallback environment variable names for the API key.

        Returns:
            List of fallback environment variable names (empty if not configured)
        """
        logger.debug(f"{self.__class__.__name__}._get_env_api_key_fallbacks: Getting fallback env vars")

        provider_config = self._get_provider_config()
        fallbacks = provider_config.get("env_api_key_fallbacks", [])

        if fallbacks:
            logger.debug(
                f"{self.__class__.__name__}._get_env_api_key_fallbacks: "
                f"Found {len(fallbacks)} fallbacks: {fallbacks}"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}._get_env_api_key_fallbacks: "
                "No fallbacks configured"
            )

        return fallbacks if fallbacks else []

    def _get_base_url(self) -> Optional[str]:
        """
        Get the base URL from config or environment.

        Resolution order:
        1. Static config 'base_url' value
        2. Environment variable specified in 'env_base_url'

        Returns:
            Base URL string or None if not configured
        """
        logger.debug(f"{self.__class__.__name__}._get_base_url: Getting base URL")

        provider_config = self._get_provider_config()

        base_url = provider_config.get("base_url")
        if base_url:
            logger.debug(
                f"{self.__class__.__name__}._get_base_url: "
                f"Using base_url from config: '{base_url}'"
            )
            return base_url

        env_base_url = provider_config.get("env_base_url")
        if env_base_url:
            base_url = os.getenv(env_base_url)
            if base_url:
                logger.debug(
                    f"{self.__class__.__name__}._get_base_url: "
                    f"Using base_url from env var '{env_base_url}': '{base_url}'"
                )
            else:
                logger.debug(
                    f"{self.__class__.__name__}._get_base_url: "
                    f"Env var '{env_base_url}' is not set"
                )
            return base_url

        logger.debug(
            f"{self.__class__.__name__}._get_base_url: "
            "No base_url or env_base_url configured, returning None"
        )
        return None

    def _lookup_env_api_key(self) -> Optional[str]:
        """
        Lookup API key from environment variable.

        Returns:
            API key value or None if not found
        """
        logger.debug(f"{self.__class__.__name__}._lookup_env_api_key: Looking up API key")

        env_key_name = self._get_env_api_key_name()

        if not env_key_name:
            logger.debug(
                f"{self.__class__.__name__}._lookup_env_api_key: "
                "No env_api_key configured, returning None"
            )
            return None

        api_key = os.getenv(env_key_name)

        if api_key:
            logger.debug(
                f"{self.__class__.__name__}._lookup_env_api_key: "
                f"Found API key in env var '{env_key_name}' "
                f"(length={len(api_key)}, masked={_mask_sensitive(api_key)})"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}._lookup_env_api_key: "
                f"Env var '{env_key_name}' is not set or empty"
            )

        return api_key

    def _get_env_email_name(self) -> Optional[str]:
        """
        Get the environment variable name for the email/username.

        Returns:
            Environment variable name or None if not configured
        """
        logger.debug(f"{self.__class__.__name__}._get_env_email_name: Getting env email name")

        provider_config = self._get_provider_config()
        env_email_name = provider_config.get("env_email")

        if env_email_name:
            logger.debug(
                f"{self.__class__.__name__}._get_env_email_name: "
                f"Found env_email='{env_email_name}'"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}._get_env_email_name: "
                "No env_email configured"
            )

        return env_email_name

    def _lookup_email(self) -> Optional[str]:
        """
        Lookup email/username from environment variable.

        Returns:
            Email/username value or None if not found
        """
        logger.debug(f"{self.__class__.__name__}._lookup_email: Looking up email")

        env_email_name = self._get_env_email_name()

        if not env_email_name:
            logger.debug(
                f"{self.__class__.__name__}._lookup_email: "
                "No env_email configured, returning None"
            )
            return None

        email = os.getenv(env_email_name)

        if email:
            logger.debug(
                f"{self.__class__.__name__}._lookup_email: "
                f"Found email in env var '{env_email_name}'"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}._lookup_email: "
                f"Env var '{env_email_name}' is not set or empty"
            )

        return email

    def _lookup_raw_api_key(self) -> Optional[str]:
        """
        Lookup raw API key from environment variable.

        This is identical to _lookup_env_api_key but named for semantic clarity
        when used alongside _lookup_email for basic auth scenarios.

        Returns:
            Raw API key value or None if not found
        """
        logger.debug(f"{self.__class__.__name__}._lookup_raw_api_key: Looking up raw API key")
        return self._lookup_env_api_key()

    # =========================================================================
    # New credential getter methods for comprehensive auth support
    # =========================================================================

    def _get_env_username_name(self) -> Optional[str]:
        """Get the environment variable name for the username."""
        logger.debug(f"{self.__class__.__name__}._get_env_username_name: Getting env username name")
        provider_config = self._get_provider_config()
        return provider_config.get("env_username")

    def _get_env_username_fallbacks(self) -> list[str]:
        """Get fallback environment variable names for the username."""
        provider_config = self._get_provider_config()
        return provider_config.get("env_username_fallbacks", [])

    def _lookup_username(self) -> Optional[str]:
        """
        Lookup username from environment variable.

        Resolution order:
        1. env_username from config
        2. env_username_fallbacks from config

        Returns:
            Username value or None if not found
        """
        logger.debug(f"{self.__class__.__name__}._lookup_username: Looking up username")

        env_username_name = self._get_env_username_name()
        if env_username_name:
            username = os.getenv(env_username_name)
            if username:
                logger.debug(f"{self.__class__.__name__}._lookup_username: Found in {env_username_name}")
                return username

        for fallback in self._get_env_username_fallbacks():
            username = os.getenv(fallback)
            if username:
                logger.debug(f"{self.__class__.__name__}._lookup_username: Found in fallback {fallback}")
                return username

        logger.debug(f"{self.__class__.__name__}._lookup_username: Not found")
        return None

    def _get_env_password_name(self) -> Optional[str]:
        """Get the environment variable name for the password."""
        logger.debug(f"{self.__class__.__name__}._get_env_password_name: Getting env password name")
        provider_config = self._get_provider_config()
        return provider_config.get("env_password")

    def _get_env_password_fallbacks(self) -> list[str]:
        """Get fallback environment variable names for the password."""
        provider_config = self._get_provider_config()
        return provider_config.get("env_password_fallbacks", [])

    def _lookup_password(self) -> Optional[str]:
        """
        Lookup password from environment variable.

        Resolution order:
        1. env_password from config
        2. env_password_fallbacks from config

        Returns:
            Password value or None if not found
        """
        logger.debug(f"{self.__class__.__name__}._lookup_password: Looking up password")

        env_password_name = self._get_env_password_name()
        if env_password_name:
            password = os.getenv(env_password_name)
            if password:
                logger.debug(f"{self.__class__.__name__}._lookup_password: Found in {env_password_name}")
                return password

        for fallback in self._get_env_password_fallbacks():
            password = os.getenv(fallback)
            if password:
                logger.debug(f"{self.__class__.__name__}._lookup_password: Found in fallback {fallback}")
                return password

        logger.debug(f"{self.__class__.__name__}._lookup_password: Not found")
        return None

    def _lookup_pat(self) -> Optional[str]:
        """
        Lookup Personal Access Token from environment variable.

        Resolution order:
        1. env_pat from config
        2. Falls back to env_api_key

        Returns:
            PAT value or None if not found
        """
        logger.debug(f"{self.__class__.__name__}._lookup_pat: Looking up PAT")

        provider_config = self._get_provider_config()
        env_pat_name = provider_config.get("env_pat")

        if env_pat_name:
            pat = os.getenv(env_pat_name)
            if pat:
                logger.debug(f"{self.__class__.__name__}._lookup_pat: Found in {env_pat_name}")
                return pat

        # Fall back to env_api_key
        return self._lookup_env_api_key()

    def _lookup_jwt(self) -> Optional[str]:
        """
        Lookup JWT token from environment variable.

        Resolution order:
        1. env_jwt from config
        2. Falls back to env_api_key

        Returns:
            JWT value or None if not found
        """
        logger.debug(f"{self.__class__.__name__}._lookup_jwt: Looking up JWT")

        provider_config = self._get_provider_config()
        env_jwt_name = provider_config.get("env_jwt")

        if env_jwt_name:
            jwt = os.getenv(env_jwt_name)
            if jwt:
                logger.debug(f"{self.__class__.__name__}._lookup_jwt: Found in {env_jwt_name}")
                return jwt

        # Fall back to env_api_key
        return self._lookup_env_api_key()

    def _lookup_oauth_token(self) -> Optional[str]:
        """
        Lookup OAuth token from environment variable.

        Resolution order:
        1. env_oauth_token from config
        2. Falls back to env_api_key

        Returns:
            OAuth token value or None if not found
        """
        logger.debug(f"{self.__class__.__name__}._lookup_oauth_token: Looking up OAuth token")

        provider_config = self._get_provider_config()
        env_oauth_name = provider_config.get("env_oauth_token")

        if env_oauth_name:
            oauth_token = os.getenv(env_oauth_name)
            if oauth_token:
                logger.debug(f"{self.__class__.__name__}._lookup_oauth_token: Found in {env_oauth_name}")
                return oauth_token

        # Fall back to env_api_key
        return self._lookup_env_api_key()

    def _get_custom_header_name(self) -> Optional[str]:
        """Get the custom header name from config."""
        logger.debug(f"{self.__class__.__name__}._get_custom_header_name: Getting custom header name")
        provider_config = self._get_provider_config()
        return provider_config.get("custom_header_name")

    # =========================================================================
    # Public getter methods for credential types
    # =========================================================================

    def get_email(self) -> Optional[str]:
        """Get email from environment."""
        return self._lookup_email()

    def get_username(self) -> Optional[str]:
        """Get username from environment."""
        return self._lookup_username()

    def get_password(self) -> Optional[str]:
        """Get password from environment."""
        return self._lookup_password()

    def get_token(self) -> Optional[str]:
        """Get token (alias for api_key) from environment."""
        return self._lookup_env_api_key()

    def get_pat(self) -> Optional[str]:
        """Get Personal Access Token from environment."""
        return self._lookup_pat()

    def get_jwt(self) -> Optional[str]:
        """Get JWT token from environment."""
        return self._lookup_jwt()

    def get_oauth_token(self) -> Optional[str]:
        """Get OAuth token from environment."""
        return self._lookup_oauth_token()

    # =========================================================================
    # Generic configuration getters (headers, env vars)
    # =========================================================================

    def get_headers(self) -> Dict[str, str]:
        """
        Get default HTTP headers from provider configuration.

        Reads the 'headers' field from the provider config in YAML.

        Example YAML:
            providers:
              confluence:
                headers:
                  Content-Type: "application/json"
                  X-Atlassian-Token: "no-check"

        Returns:
            Dictionary of default headers for API requests
        """
        logger.debug(f"{self.__class__.__name__}.get_headers: Getting default headers")

        provider_config = self._get_provider_config()
        headers = provider_config.get("headers", {}) or {}

        logger.debug(
            f"{self.__class__.__name__}.get_headers: Found {len(headers)} headers: {list(headers.keys())}"
        )

        return headers

    def get_env_by_name(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get environment variable value by name from provider config.

        Looks up env_{name} in the provider config to get the environment variable name,
        then resolves the actual value from the environment.

        Example YAML:
            providers:
              confluence:
                env_space_key: "CONFLUENCE_SPACE_KEY"
                env_parent_page_id: "CONFLUENCE_PARENT_PAGE_ID"

        Code:
            provider = ConfluenceApiToken(static_config)
            space_key = provider.get_env_by_name("space_key")
            # Reads env var name from config: "CONFLUENCE_SPACE_KEY"
            # Returns os.getenv("CONFLUENCE_SPACE_KEY")

        Args:
            name: The name suffix (without 'env_' prefix)
            default: Default value if env var is not set

        Returns:
            Environment variable value or default
        """
        logger.debug(f"{self.__class__.__name__}.get_env_by_name: Looking up env_{name}")

        provider_config = self._get_provider_config()
        env_key = f"env_{name}"
        env_var_name = provider_config.get(env_key)

        if not env_var_name:
            logger.debug(
                f"{self.__class__.__name__}.get_env_by_name: No '{env_key}' found in provider config, "
                f"returning default: {default}"
            )
            return default

        value = os.getenv(env_var_name, default)

        logger.debug(
            f"{self.__class__.__name__}.get_env_by_name: Resolved {env_key}='{env_var_name}' -> "
            f"value={'<set>' if value else '<not set>'}"
        )

        return value

    @abstractmethod
    def get_api_key(self) -> ApiKeyResult:
        """
        Simple API key lookup from environment variable.

        Uses static_config.providers.{provider_name}.env_api_key to determine
        which environment variable contains the API key.

        Returns:
            ApiKeyResult with resolved credentials
        """
        pass

    def get_api_key_for_request(self, context: RequestContext) -> ApiKeyResult:
        """
        Computed API key based on request context.

        Override this method for:
        - OAuth token resolution
        - Per-tenant token resolution
        - User-scoped token resolution
        - Dynamic token refresh

        Args:
            context: Request context with optional tenant/user info

        Returns:
            ApiKeyResult with resolved credentials
        """
        logger.debug(
            f"{self.__class__.__name__}.get_api_key_for_request: "
            f"Called with context={context.to_dict()}"
        )

        if context.tenant_id:
            logger.debug(
                f"{self.__class__.__name__}.get_api_key_for_request: "
                f"tenant_id={context.tenant_id} provided but base implementation "
                "does not support per-tenant tokens"
            )

        if context.user_id:
            logger.debug(
                f"{self.__class__.__name__}.get_api_key_for_request: "
                f"user_id={context.user_id} provided but base implementation "
                "does not support per-user tokens"
            )

        result = self.get_api_key()
        logger.debug(
            f"{self.__class__.__name__}.get_api_key_for_request: "
            f"Returning result from get_api_key(): {result.to_dict()}"
        )
        return result

    async def get_api_key_async(self) -> ApiKeyResult:
        """
        Async API key resolution with registry integration.

        Resolution priority:
        1. Token registry (Option A: set_api_token, Option C: register_resolver)
        2. Subclass get_api_key() implementation (env var lookup)

        Returns:
            ApiKeyResult with resolved credentials
        """
        logger.debug(
            f"{self.__class__.__name__}.get_api_key_async: "
            "Starting async API key resolution"
        )

        provider_config = self._get_provider_config()

        # 1. Check token registry (Option A/B/C)
        try:
            registry_token = await token_registry.get_token(
                self.provider_name,
                None,
                provider_config
            )

            if registry_token:
                logger.debug(
                    f"{self.__class__.__name__}.get_api_key_async: "
                    f"Found token from registry (length={len(registry_token)})"
                )
                return ApiKeyResult(
                    api_key=registry_token,
                    auth_type=self.get_auth_type(),
                    header_name=self.get_header_name(),
                )
        except Exception as e:
            logger.error(
                f"{self.__class__.__name__}.get_api_key_async: "
                f"Registry lookup failed: {e}"
            )

        # 2. Fall back to subclass implementation (env var lookup)
        logger.debug(
            f"{self.__class__.__name__}.get_api_key_async: "
            "No registry token, falling back to get_api_key()"
        )
        return self.get_api_key()

    async def get_api_key_for_request_async(
        self, context: RequestContext
    ) -> ApiKeyResult:
        """
        Async API key resolution for request context.

        Used for per-request token resolution (token_resolver: "request").

        Args:
            context: Request context with optional tenant/user info

        Returns:
            ApiKeyResult with resolved credentials
        """
        logger.debug(
            f"{self.__class__.__name__}.get_api_key_for_request_async: "
            "Starting async request API key resolution"
        )

        if context and context.tenant_id:
            logger.debug(
                f"{self.__class__.__name__}.get_api_key_for_request_async: "
                f"tenant_id={context.tenant_id}"
            )

        if context and context.user_id:
            logger.debug(
                f"{self.__class__.__name__}.get_api_key_for_request_async: "
                f"user_id={context.user_id}"
            )

        provider_config = self._get_provider_config()

        # 1. Check token registry with context (for per-request tokens)
        try:
            registry_token = await token_registry.get_token(
                self.provider_name,
                context,
                provider_config
            )

            if registry_token:
                logger.debug(
                    f"{self.__class__.__name__}.get_api_key_for_request_async: "
                    f"Found token from registry (length={len(registry_token)})"
                )
                return ApiKeyResult(
                    api_key=registry_token,
                    auth_type=self.get_auth_type(),
                    header_name=self.get_header_name(),
                )
        except Exception as e:
            logger.error(
                f"{self.__class__.__name__}.get_api_key_for_request_async: "
                f"Registry lookup failed: {e}"
            )

        # 2. Fall back to subclass implementation
        logger.debug(
            f"{self.__class__.__name__}.get_api_key_for_request_async: "
            "No registry token, falling back to get_api_key_for_request()"
        )
        return self.get_api_key_for_request(context)

    def get_base_url(self) -> Optional[str]:
        """
        Get the base URL for this provider.

        Returns:
            Base URL string or None if not configured
        """
        logger.debug(f"{self.__class__.__name__}.get_base_url: Getting base URL")
        result = self._get_base_url()
        logger.debug(
            f"{self.__class__.__name__}.get_base_url: "
            f"Returning base_url={'<set>' if result else 'None'}"
        )
        return result

    @property
    def _default_auth_type(self) -> str:
        """
        Default auth type for this provider.
        Subclasses can override to set provider-specific defaults.

        Returns:
            Default auth type string (e.g., 'bearer', 'basic')
        """
        return "bearer"

    @property
    def _default_header_name(self) -> str:
        """
        Default header name for auth.
        Subclasses can override for custom headers.

        Returns:
            Default header name string
        """
        return "Authorization"

    def get_auth_type(self) -> str:
        """
        Get the auth type for this provider.

        Resolution priority:
        1. YAML config: providers.{name}.api_auth_type
        2. Subclass default: _default_auth_type property

        Returns:
            Auth type (bearer, basic, x-api-key, custom, connection_string)
        """
        logger.debug(f"{self.__class__.__name__}.get_auth_type: Getting auth type")

        # 1. Check YAML config
        provider_config = self._get_provider_config()
        config_auth_type = provider_config.get("api_auth_type")

        if config_auth_type:
            # Validate auth type
            if config_auth_type not in VALID_AUTH_TYPES:
                logger.warning(
                    f"{self.__class__.__name__}.get_auth_type: Invalid api_auth_type "
                    f"'{config_auth_type}' in config, expected one of {VALID_AUTH_TYPES}, "
                    f"falling back to default '{self._default_auth_type}'"
                )
                return self._default_auth_type

            logger.debug(
                f"{self.__class__.__name__}.get_auth_type: Using api_auth_type from config: "
                f"'{config_auth_type}'"
            )
            return config_auth_type

        # 2. Fall back to provider default
        logger.debug(
            f"{self.__class__.__name__}.get_auth_type: No api_auth_type in config, "
            f"using provider default: '{self._default_auth_type}'"
        )
        return self._default_auth_type

    def get_header_name(self) -> str:
        """
        Get the header name for auth.

        Resolution based on auth type:
        - bearer/bearer_*: Authorization
        - basic/basic_*: Authorization
        - x-api-key: X-Api-Key
        - custom/custom_header: custom header name from config or default

        Returns:
            Header name string
        """
        logger.debug(f"{self.__class__.__name__}.get_header_name: Getting header name")

        auth_type = self.get_auth_type()

        # Basic auth family - all use Authorization header
        basic_types = {"basic", "basic_email_token", "basic_token", "basic_email"}

        # Bearer auth family - all use Authorization header
        bearer_types = {
            "bearer", "bearer_oauth", "bearer_jwt",
            "bearer_username_token", "bearer_username_password",
            "bearer_email_token", "bearer_email_password",
        }

        if auth_type in basic_types or auth_type in bearer_types:
            header_name = "Authorization"
        elif auth_type == "x-api-key":
            header_name = "X-Api-Key"
        elif auth_type in ("custom", "custom_header"):
            # Use custom header name from config or fall back to default
            custom_header = self._get_custom_header_name()
            header_name = custom_header or self._default_header_name
        else:  # connection_string, hmac, etc.
            header_name = self._default_header_name

        logger.debug(
            f"{self.__class__.__name__}.get_header_name: auth_type='{auth_type}' -> "
            f"header_name='{header_name}'"
        )
        return header_name

    def compute_auth_header_value(
        self,
        raw_api_key: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Optional[str]:
        """
        Compute the formatted auth header value based on auth type.

        This method handles all auth type variants:
        - basic: Base64(identifier:secret) where identifier is email OR username
        - basic_email_token: Base64(email:token)
        - basic_token: Base64(username:token)
        - basic_email: Base64(email:password)
        - bearer: Token as-is OR Base64(identifier:secret) if identifier provided
        - bearer_email_token: Bearer Base64(email:token)
        - bearer_username_token: Bearer Base64(username:token)
        - bearer_email_password: Bearer Base64(email:password)
        - bearer_username_password: Bearer Base64(username:password)
        - bearer_oauth, bearer_jwt: Bearer <token>
        - x-api-key, custom, custom_header: Token as-is

        Logs the encoding method with masked input/output for debugging.

        Args:
            raw_api_key: The raw API key/token
            email: Email address (for basic_email_token, bearer_email_token, etc.)
            username: Username (for basic_token, bearer_username_token, etc.)
            password: Password (for basic_email, bearer_email_password, etc.)

        Returns:
            Formatted auth header value or None if credentials are insufficient
        """
        from fetch_auth_encoding import encode_auth

        auth_type = self.get_auth_type()
        class_name = self.__class__.__name__

        logger.debug(
            f"{class_name}.compute_auth_header_value: Computing header for auth_type='{auth_type}'"
        )

        def mask_value(val: Optional[str]) -> str:
            """Mask value for logging, showing first 10 chars."""
            return _mask_sensitive(val, 10)

        def encode_basic(identifier: str, secret: str) -> str:
            """Encode credentials as Basic auth header."""
            headers = encode_auth("basic", username=identifier, password=secret)
            result = headers["Authorization"]
            logger.info(
                f"[AUTH] {class_name}.compute_auth_header_value: "
                f"Encoding Basic auth - identifier={mask_value(identifier)}, "
                f"secret={mask_value(secret)} -> output={mask_value(result)}"
            )
            return result

        def encode_bearer_base64(identifier: str, secret: str) -> str:
            """Encode credentials as Bearer auth header with base64."""
            # Use 'bearer_username_password' (or similar) to get "Bearer base64(u:p)"
            # Strategy: we want "Bearer base64(identifier:secret)"
            # fetch_auth_encoding has 'bearer_username_password' which does exactly this.
            headers = encode_auth("bearer_username_password", username=identifier, password=secret)
            result = headers["Authorization"]
            logger.info(
                f"[AUTH] {class_name}.compute_auth_header_value: "
                f"Encoding Bearer base64 - identifier={mask_value(identifier)}, "
                f"secret={mask_value(secret)} -> output={mask_value(result)}"
            )
            return result

        def bearer_token(token: str) -> str:
            """Format Bearer token header."""
            headers = encode_auth("bearer", token=token)
            result = headers["Authorization"]
            logger.info(
                f"[AUTH] {class_name}.compute_auth_header_value: "
                f"Bearer token - input={mask_value(token)} -> output={mask_value(result)}"
            )
            return result

        # Guard: if raw_api_key already has scheme prefix, return as-is
        if raw_api_key and (raw_api_key.startswith("Basic ") or raw_api_key.startswith("Bearer ")):
            logger.info(
                f"[AUTH] {class_name}.compute_auth_header_value: "
                f"Pre-encoded value detected (starts with scheme prefix), returning as-is: "
                f"{mask_value(raw_api_key)}"
            )
            return raw_api_key

        # === Basic Auth Family ===
        if auth_type == "basic":
            # Auto-compute: detect identifier (email or username) and secret (password or token)
            identifier = email or username
            secret = password or raw_api_key
            if not identifier or not secret:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"basic auth requires identifier AND secret, got "
                    f"identifier={identifier is not None}, secret={secret is not None}"
                )
                return None
            return encode_basic(identifier, secret)

        if auth_type == "basic_email_token":
            if not email or not raw_api_key:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"basic_email_token requires email AND rawApiKey, got "
                    f"email={email is not None}, rawApiKey={raw_api_key is not None}"
                )
                return None
            return encode_basic(email, raw_api_key)

        if auth_type == "basic_token":
            if not username or not raw_api_key:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"basic_token requires username AND rawApiKey, got "
                    f"username={username is not None}, rawApiKey={raw_api_key is not None}"
                )
                return None
            return encode_basic(username, raw_api_key)

        if auth_type == "basic_email":
            if not email or not password:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"basic_email requires email AND password, got "
                    f"email={email is not None}, password={password is not None}"
                )
                return None
            return encode_basic(email, password)

        # === Bearer Auth Family ===
        if auth_type == "bearer":
            # Auto-compute: detect if credentials need base64 encoding
            identifier = email or username
            if identifier:
                # Has identifier → encode as base64(identifier:secret)
                secret = password or raw_api_key
                if not secret:
                    logger.warning(
                        f"[AUTH] {class_name}.compute_auth_header_value: "
                        f"bearer with identifier requires secret, got secret=None"
                    )
                    return None
                return encode_bearer_base64(identifier, secret)
            elif raw_api_key:
                # No identifier → use raw_api_key as-is (PAT, OAuth, JWT)
                return bearer_token(raw_api_key)
            else:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"bearer auth requires rawApiKey OR (identifier AND secret)"
                )
                return None

        if auth_type in ("bearer_oauth", "bearer_jwt"):
            if not raw_api_key:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"{auth_type} requires rawApiKey"
                )
                return None
            return bearer_token(raw_api_key)

        if auth_type == "bearer_username_token":
            if not username or not raw_api_key:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"bearer_username_token requires username AND rawApiKey, got "
                    f"username={username is not None}, rawApiKey={raw_api_key is not None}"
                )
                return None
            return encode_bearer_base64(username, raw_api_key)

        if auth_type == "bearer_username_password":
            if not username or not password:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"bearer_username_password requires username AND password, got "
                    f"username={username is not None}, password={password is not None}"
                )
                return None
            return encode_bearer_base64(username, password)

        if auth_type == "bearer_email_token":
            if not email or not raw_api_key:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"bearer_email_token requires email AND rawApiKey, got "
                    f"email={email is not None}, rawApiKey={raw_api_key is not None}"
                )
                return None
            return encode_bearer_base64(email, raw_api_key)

        if auth_type == "bearer_email_password":
            if not email or not password:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"bearer_email_password requires email AND password, got "
                    f"email={email is not None}, password={password is not None}"
                )
                return None
            return encode_bearer_base64(email, password)

        # === Custom/API Key ===
        if auth_type == "x-api-key":
            if not raw_api_key:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"x-api-key requires rawApiKey"
                )
                return None
            logger.info(
                f"[AUTH] {class_name}.compute_auth_header_value: "
                f"x-api-key - input={mask_value(raw_api_key)} -> output={mask_value(raw_api_key)}"
            )
            return raw_api_key

        if auth_type in ("custom", "custom_header"):
            if not raw_api_key:
                logger.warning(
                    f"[AUTH] {class_name}.compute_auth_header_value: "
                    f"{auth_type} requires rawApiKey"
                )
                return None
            logger.info(
                f"[AUTH] {class_name}.compute_auth_header_value: "
                f"{auth_type} - input={mask_value(raw_api_key)} -> output={mask_value(raw_api_key)}"
            )
            return raw_api_key

        # === HMAC (stub) ===
        if auth_type == "hmac":
            logger.warning(
                f"[AUTH] {class_name}.compute_auth_header_value: "
                f"hmac auth type not yet implemented"
            )
            return None

        # === Connection string (no header) ===
        if auth_type == "connection_string":
            logger.debug(
                f"[AUTH] {class_name}.compute_auth_header_value: "
                f"connection_string does not use auth headers"
            )
            return None

        # Unknown auth type - fall back to raw_api_key
        logger.warning(
            f"[AUTH] {class_name}.compute_auth_header_value: "
            f"Unknown auth_type '{auth_type}', returning rawApiKey as-is"
        )
        return raw_api_key

    def get_token_resolver_type(self) -> str:
        """
        Get the token resolver type for this provider.

        Returns:
            Token resolver type (static, startup, request)
        """
        logger.debug(
            f"{self.__class__.__name__}.get_token_resolver_type: Getting token resolver type"
        )

        provider_config = self._get_provider_config()
        resolver_type = provider_config.get("token_resolver", "static")

        # Validate resolver type
        valid_types = {"static", "startup", "request"}
        if resolver_type not in valid_types:
            logger.warning(
                f"{self.__class__.__name__}.get_token_resolver_type: Invalid token_resolver "
                f"'{resolver_type}' in config, expected one of {valid_types}, "
                f"defaulting to 'static'"
            )
            return "static"

        logger.debug(
            f"{self.__class__.__name__}.get_token_resolver_type: Resolved "
            f"token_resolver='{resolver_type}'"
        )
        return resolver_type

    def get_runtime_import(self, platform: str = "fastapi") -> Optional[str]:
        """
        Get the runtime_import configuration for this provider.

        Supports two formats:
        - Object: { fastify: "path.mjs", fastapi: "module.path" }
        - String: "module.path" (single platform)

        Args:
            platform: Platform key ('fastify' or 'fastapi')

        Returns:
            Import path for the platform or None
        """
        logger.debug(
            f"{self.__class__.__name__}.get_runtime_import: Getting runtime_import "
            f"for platform='{platform}'"
        )

        provider_config = self._get_provider_config()
        runtime_import = provider_config.get("runtime_import")

        if not runtime_import:
            logger.debug(
                f"{self.__class__.__name__}.get_runtime_import: No runtime_import configured"
            )
            return None

        import_path = None

        if isinstance(runtime_import, dict) and runtime_import.get(platform):
            import_path = runtime_import[platform]
            logger.debug(
                f"{self.__class__.__name__}.get_runtime_import: Found platform-specific "
                f"import: '{import_path}'"
            )
        elif isinstance(runtime_import, str):
            import_path = runtime_import
            logger.debug(
                f"{self.__class__.__name__}.get_runtime_import: Found string import "
                f"(single platform): '{import_path}'"
            )

        return import_path



    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """
        Get provider-specific proxy configuration.

        Returns:
            Proxy config dictionary or None if not configured
        """
        logger.debug(
            f"{self.__class__.__name__}.get_proxy_config: "
            "Getting proxy config from provider config"
        )

        provider_config = self._get_provider_config()
        proxy_config = provider_config.get("proxy")

        if proxy_config:
            logger.debug(
                f"{self.__class__.__name__}.get_proxy_config: "
                f"Found proxy config with keys: {list(proxy_config.keys())}"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}.get_proxy_config: "
                "No proxy config in provider config"
            )

        return proxy_config

    def get_client_config(self) -> Optional[Dict[str, Any]]:
        """
        Get provider-specific client configuration.

        Returns:
            Client config dictionary or None if not configured
        """
        logger.debug(
            f"{self.__class__.__name__}.get_client_config: "
            "Getting client config from provider config"
        )

        provider_config = self._get_provider_config()
        client_config = provider_config.get("client")

        if client_config:
            logger.debug(
                f"{self.__class__.__name__}.get_client_config: "
                f"Found client config with keys: {list(client_config.keys())}"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}.get_client_config: "
                "No client config in provider config"
            )

        return client_config

    def get_headers_config(self) -> Optional[Dict[str, str]]:
        """
        Get provider-specific headers configuration.

        Returns:
            Headers config dictionary or None if not configured
        """
        logger.debug(
            f"{self.__class__.__name__}.get_headers_config: "
            "Getting headers config from provider config"
        )

        provider_config = self._get_provider_config()
        headers_config = provider_config.get("headers")

        if headers_config:
            logger.debug(
                f"{self.__class__.__name__}.get_headers_config: "
                f"Found headers config with keys: {list(headers_config.keys())}"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}.get_headers_config: "
                "No headers config in provider config"
            )

        return headers_config

    def get_network_config(self) -> Dict[str, Any]:
        """
        Get provider-specific network/proxy configuration.

        Reads from provider YAML config fields:
        - proxy_url: Proxy URL for requests
        - ca_bundle: CA bundle path for SSL verification
        - cert: Client certificate path
        - cert_verify: SSL certificate verification flag (defaults to True)
        - agent_proxy.http_proxy: HTTP proxy for agent
        - agent_proxy.https_proxy: HTTPS proxy for agent

        Returns:
            Dictionary with network configuration values
        """
        logger.debug(
            f"{self.__class__.__name__}.get_network_config: Getting network configuration"
        )

        provider_config = self._get_provider_config()

        # Get agent_proxy nested config
        agent_proxy = provider_config.get("agent_proxy", {}) or {}

        config = {
            "proxy_url": provider_config.get("proxy_url"),
            "ca_bundle": provider_config.get("ca_bundle"),
            "cert": provider_config.get("cert"),
            "cert_verify": provider_config.get("cert_verify", True),
            "agent_proxy": {
                "http_proxy": agent_proxy.get("http_proxy"),
                "https_proxy": agent_proxy.get("https_proxy"),
            },
        }

        logger.debug(
            f"{self.__class__.__name__}.get_network_config: Resolved config - "
            f"proxy_url={config['proxy_url']}, "
            f"ca_bundle={config['ca_bundle']}, "
            f"cert={config['cert']}, "
            f"cert_verify={config['cert_verify']}, "
            f"agent_proxy={config['agent_proxy']}"
        )

        return config

    def validate(self) -> Dict[str, Any]:
        """
        Validate the provider configuration.

        Returns:
            Dictionary with validation results
        """
        logger.debug(f"{self.__class__.__name__}.validate: Starting validation")

        issues = []
        warnings = []

        provider_config = self._get_provider_config()
        if not provider_config:
            issues.append(f"No configuration found for provider '{self.provider_name}'")

        base_url = self.get_base_url()
        if not base_url:
            issues.append("No base_url configured")

        api_key_result = self.get_api_key()
        if not api_key_result.has_credentials and not api_key_result.is_placeholder:
            issues.append("No API credentials available")

        if api_key_result.is_placeholder:
            warnings.append(f"Provider is placeholder: {api_key_result.placeholder_message}")

        result = {
            "provider": self.provider_name,
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "has_base_url": base_url is not None,
            "has_credentials": api_key_result.has_credentials,
            "is_placeholder": api_key_result.is_placeholder,
            "validated_at": datetime.now().isoformat(),
        }

        logger.debug(
            f"{self.__class__.__name__}.validate: Completed validation "
            f"valid={result['valid']}, issues={len(issues)}, warnings={len(warnings)}"
        )

        return result

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        logger.debug(f"{self.__class__.__name__}.clear_cache: Clearing configuration cache")
        self._config_cache = None
