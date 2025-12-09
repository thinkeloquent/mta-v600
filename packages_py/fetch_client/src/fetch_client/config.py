"""
Configuration for fetch_client.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Union
from urllib.parse import urlparse
import json

from .types import AuthType, RequestContext


def _mask_sensitive(value: Optional[str], visible_chars: int = 10) -> str:
    """Mask sensitive value for safe logging."""
    if value is None:
        return "<None>"
    if len(value) <= visible_chars:
        return "*" * len(value)
    return value[:visible_chars] + "*" * (len(value) - visible_chars)


@dataclass
class AuthConfig:
    """Authentication configuration.

    Auth types:
    - bearer: "Bearer <api_key>" (standard bearer token)
    - bearer_user: "Bearer <base64(username:api_key)>" (bearer with basic-style encoding)
    - x-api-key: api_key in X-API-Key header
    - custom: raw api_key in custom header (specified by header_name)
    """

    type: AuthType
    api_key: Optional[str] = None
    username: Optional[str] = None  # Required for bearer_user type
    header_name: Optional[str] = None
    get_api_key_for_request: Optional[Callable[[RequestContext], Optional[str]]] = None

    def __repr__(self) -> str:
        """Safe repr that masks api_key."""
        return (
            f"AuthConfig(type={self.type!r}, "
            f"api_key={_mask_sensitive(self.api_key)!r}, "
            f"username={self.username!r}, "
            f"header_name={self.header_name!r}, "
            f"has_callback={self.get_api_key_for_request is not None})"
        )


@dataclass
class TimeoutConfig:
    """Timeout configuration in seconds."""

    connect: float = 5.0
    read: float = 30.0
    write: float = 10.0


@dataclass
class ClientConfig:
    """Client configuration."""

    base_url: str
    httpx_client: Optional[Any] = None
    auth: Optional[AuthConfig] = None
    timeout: Union[TimeoutConfig, float, None] = None
    headers: Dict[str, str] = field(default_factory=dict)
    content_type: str = "application/json"


# Default values
DEFAULT_TIMEOUT = TimeoutConfig()
DEFAULT_CONTENT_TYPE = "application/json"


class DefaultSerializer:
    """Default JSON serializer."""

    def serialize(self, data: Any) -> str:
        """Serialize data to JSON string."""
        return json.dumps(data)

    def deserialize(self, text: str) -> Any:
        """Deserialize JSON string to data."""
        return json.loads(text)


default_serializer = DefaultSerializer()


def normalize_timeout(timeout: Union[TimeoutConfig, float, None]) -> TimeoutConfig:
    """Normalize timeout config."""
    if timeout is None:
        return DEFAULT_TIMEOUT
    if isinstance(timeout, (int, float)):
        return TimeoutConfig(connect=timeout, read=timeout, write=timeout)
    return timeout


def validate_config(config: ClientConfig) -> None:
    """Validate client configuration."""
    if not config.base_url:
        raise ValueError("base_url is required")

    try:
        parsed = urlparse(config.base_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid base_url: {config.base_url}")
    except Exception as e:
        raise ValueError(f"Invalid base_url: {config.base_url}") from e

    if config.auth:
        validate_auth_config(config.auth)


def validate_auth_config(auth: AuthConfig) -> None:
    """Validate auth configuration."""
    valid_types = {"bearer", "bearer_user", "x-api-key", "custom"}

    if auth.type not in valid_types:
        raise ValueError(f"Invalid auth type: {auth.type}. Must be one of: {valid_types}")

    if auth.type == "custom" and not auth.header_name:
        raise ValueError("header_name is required for custom auth type")

    if auth.type == "bearer_user" and not auth.username:
        raise ValueError("username is required for bearer_user auth type")


def get_auth_header_name(auth: AuthConfig) -> str:
    """Get auth header name based on auth type."""
    if auth.type == "bearer":
        return "Authorization"
    elif auth.type == "bearer_user":
        return "Authorization"
    elif auth.type == "x-api-key":
        return "x-api-key"
    elif auth.type == "custom":
        return auth.header_name or "Authorization"
    return "Authorization"


def format_auth_header_value(auth: AuthConfig, api_key: str) -> str:
    """Format auth header value based on auth type.

    For bearer_user type, encodes username:api_key as base64.
    """
    import base64

    if auth.type == "bearer":
        return f"Bearer {api_key}"
    elif auth.type == "bearer_user":
        # Encode username:api_key as base64 for bearer_user
        credentials = f"{auth.username}:{api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Bearer {encoded}"
    return api_key


@dataclass
class ResolvedConfig:
    """Resolved client configuration with defaults applied."""

    base_url: str
    timeout: TimeoutConfig
    headers: Dict[str, str]
    content_type: str
    auth: Optional[AuthConfig]
    serializer: DefaultSerializer


def resolve_config(config: ClientConfig) -> ResolvedConfig:
    """Resolve client configuration with defaults."""
    validate_config(config)

    return ResolvedConfig(
        base_url=config.base_url,
        timeout=normalize_timeout(config.timeout),
        headers=dict(config.headers),
        content_type=config.content_type or DEFAULT_CONTENT_TYPE,
        auth=config.auth,
        serializer=default_serializer,
    )
