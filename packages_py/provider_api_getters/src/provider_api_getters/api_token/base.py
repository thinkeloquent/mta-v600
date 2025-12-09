"""
Base class for API token getters.

This module provides the foundational classes for provider API token resolution
with comprehensive defensive programming, validation, and observability.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union
import logging
import os

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


# Valid auth types
VALID_AUTH_TYPES = frozenset({"bearer", "x-api-key", "basic", "custom", "connection_string"})


@dataclass
class ApiKeyResult:
    """
    Result from API key resolution.

    Attributes:
        api_key: The resolved API key or token (may be None if not found)
        auth_type: Authentication type (bearer, x-api-key, basic, custom, connection_string)
        header_name: HTTP header name for the authentication
        username: Username for basic auth scenarios
        client: Pre-configured client instance (for DB connections)
        is_placeholder: True if this provider is not yet implemented
        placeholder_message: Human-readable message for placeholder providers
    """

    api_key: Optional[str] = None
    auth_type: str = "bearer"
    header_name: str = "Authorization"
    username: Optional[str] = None
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

    def get_overwrite_config(self) -> Optional[Dict[str, Any]]:
        """
        Get the overwrite_config block for this provider.

        Returns:
            Overwrite config dictionary or None if not configured
        """
        logger.debug(f"{self.__class__.__name__}.get_overwrite_config: Getting overwrite config")

        provider_config = self._get_provider_config()
        overwrite = provider_config.get("overwrite_config")

        if overwrite:
            logger.debug(
                f"{self.__class__.__name__}.get_overwrite_config: "
                f"Found overwrite_config with keys: {list(overwrite.keys())}"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}.get_overwrite_config: No overwrite_config found"
            )

        return overwrite

    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """
        Get provider-specific proxy configuration from overwrite_config.

        Returns:
            Proxy config dictionary or None if not configured
        """
        logger.debug(
            f"{self.__class__.__name__}.get_proxy_config: "
            "Getting proxy config from overwrite_config"
        )

        overwrite = self.get_overwrite_config()
        proxy_config = overwrite.get("proxy") if overwrite else None

        if proxy_config:
            logger.debug(
                f"{self.__class__.__name__}.get_proxy_config: "
                f"Found proxy config with keys: {list(proxy_config.keys())}"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}.get_proxy_config: "
                "No proxy config in overwrite_config"
            )

        return proxy_config

    def get_client_config(self) -> Optional[Dict[str, Any]]:
        """
        Get provider-specific client configuration from overwrite_config.

        Returns:
            Client config dictionary or None if not configured
        """
        logger.debug(
            f"{self.__class__.__name__}.get_client_config: "
            "Getting client config from overwrite_config"
        )

        overwrite = self.get_overwrite_config()
        client_config = overwrite.get("client") if overwrite else None

        if client_config:
            logger.debug(
                f"{self.__class__.__name__}.get_client_config: "
                f"Found client config with keys: {list(client_config.keys())}"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}.get_client_config: "
                "No client config in overwrite_config"
            )

        return client_config

    def get_headers_config(self) -> Optional[Dict[str, str]]:
        """
        Get provider-specific headers configuration from overwrite_config.

        Returns:
            Headers config dictionary or None if not configured
        """
        logger.debug(
            f"{self.__class__.__name__}.get_headers_config: "
            "Getting headers config from overwrite_config"
        )

        overwrite = self.get_overwrite_config()
        headers_config = overwrite.get("headers") if overwrite else None

        if headers_config:
            logger.debug(
                f"{self.__class__.__name__}.get_headers_config: "
                f"Found headers config with keys: {list(headers_config.keys())}"
            )
        else:
            logger.debug(
                f"{self.__class__.__name__}.get_headers_config: "
                "No headers config in overwrite_config"
            )

        return headers_config

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
