"""
Configuration for fetch_client.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Union
from urllib.parse import urlparse
import json

from .types import AuthType, RequestContext
from console_print import print_auth_trace

LOG_PREFIX = f"[AUTH:{__file__}]"


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
    Basic auth family (Authorization: Basic <base64>):
    - basic: Auto-compute Basic <base64((username|email):(password|token))>
    - basic_email_token: Basic <base64(email:token)> - Atlassian APIs
    - basic_token: Basic <base64(username:token)>
    - basic_email: Basic <base64(email:password)>

    Bearer auth family (Authorization: Bearer <value>):
    - bearer: Auto-compute Bearer <PAT|OAuth|JWT|base64(...)>
    - bearer_oauth: Bearer <OAuth2.0_token>
    - bearer_jwt: Bearer <JWT_token>
    - bearer_username_token: Bearer <base64(username:token)>
    - bearer_username_password: Bearer <base64(username:password)>
    - bearer_email_token: Bearer <base64(email:token)>
    - bearer_email_password: Bearer <base64(email:password)>

    Custom/API Key auth:
    - x-api-key: api_key in X-API-Key header
    - custom: raw string in custom header (specified by header_name)
    - custom_header: api_key in custom header (specified by header_name)

    HMAC auth (stub for future implementation):
    - hmac: AWS Signature, GCP HMAC, HTTP Signatures, Webhooks

    Properties:
    - raw_api_key: Original token/key value (input field)
    - api_key: Computed auth header value based on type (e.g., "Basic <base64>")
    """

    type: AuthType
    raw_api_key: Optional[str] = None   # Original token/key value
    username: Optional[str] = None      # For basic/bearer_username_* types
    email: Optional[str] = None         # For *_email* types
    password: Optional[str] = None      # For *_password types
    header_name: Optional[str] = None   # For custom/custom_header types
    get_api_key_for_request: Optional[Callable[[RequestContext], Optional[str]]] = None

    def __post_init__(self):
        """Validate auth config on initialization."""
        # Detect if raw_api_key looks like a URL (common misconfiguration)
        if self.raw_api_key and self.raw_api_key.startswith(("http://", "https://")):
            import logging
            logger = logging.getLogger("fetch_client.config")
            logger.error(
                f"AuthConfig: raw_api_key appears to be a URL (starts with http). "
                f"This is likely a misconfiguration. Expected an API key/token, "
                f"got: {self.raw_api_key[:30]}..."
            )

    @property
    def api_key(self) -> Optional[str]:
        """Return the computed auth header value based on type.

        For basic auth: Returns "Basic <base64(identifier:secret)>"
        For bearer auth: Returns "Bearer <token>" or "Bearer <base64(...)>"
        For x-api-key/custom: Returns the raw value
        """
        print_auth_trace("GET self.raw_api_key", "config.py:85", self.raw_api_key)
        if self.raw_api_key is None:
            return None
        return format_auth_header_value(self, self.raw_api_key)

    def __repr__(self) -> str:
        """Safe repr that masks sensitive values."""
        return (
            f"AuthConfig(type={self.type!r}, "
            f"raw_api_key={_mask_sensitive(self.raw_api_key)!r}, "
            f"username={self.username!r}, "
            f"email={self.email!r}, "
            f"password={_mask_sensitive(self.password)!r}, "
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
    valid_types = {
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
    }

    if auth.type not in valid_types:
        raise ValueError(f"Invalid auth type: {auth.type}. Must be one of: {sorted(valid_types)}")

    # Validation rules per type
    if auth.type == "basic":
        # Auto-compute: need (username OR email) AND (password OR raw_api_key)
        has_identifier = auth.username or auth.email
        has_secret = auth.password or auth.raw_api_key
        if not has_identifier or not has_secret:
            raise ValueError("basic auth requires (username OR email) AND (password OR raw_api_key)")

    elif auth.type == "basic_email_token":
        if not auth.email:
            raise ValueError("email is required for basic_email_token auth type")
        if not auth.raw_api_key:
            raise ValueError("raw_api_key is required for basic_email_token auth type")

    elif auth.type == "basic_token":
        if not auth.username:
            raise ValueError("username is required for basic_token auth type")
        if not auth.raw_api_key:
            raise ValueError("raw_api_key is required for basic_token auth type")

    elif auth.type == "basic_email":
        if not auth.email:
            raise ValueError("email is required for basic_email auth type")
        if not auth.password:
            raise ValueError("password is required for basic_email auth type")

    elif auth.type == "bearer":
        # Auto-compute: need raw_api_key OR ((username OR email) AND (password OR raw_api_key))
        has_identifier = auth.username or auth.email
        has_secret = auth.password or auth.raw_api_key
        has_credentials = has_identifier and has_secret
        if not auth.raw_api_key and not has_credentials:
            raise ValueError("bearer auth requires raw_api_key OR ((username OR email) AND (password OR raw_api_key))")

    elif auth.type in ("bearer_oauth", "bearer_jwt"):
        if not auth.raw_api_key:
            raise ValueError(f"raw_api_key is required for {auth.type} auth type")

    elif auth.type == "bearer_username_token":
        if not auth.username:
            raise ValueError("username is required for bearer_username_token auth type")
        if not auth.raw_api_key:
            raise ValueError("raw_api_key is required for bearer_username_token auth type")

    elif auth.type == "bearer_username_password":
        if not auth.username:
            raise ValueError("username is required for bearer_username_password auth type")
        if not auth.password:
            raise ValueError("password is required for bearer_username_password auth type")

    elif auth.type == "bearer_email_token":
        if not auth.email:
            raise ValueError("email is required for bearer_email_token auth type")
        if not auth.raw_api_key:
            raise ValueError("raw_api_key is required for bearer_email_token auth type")

    elif auth.type == "bearer_email_password":
        if not auth.email:
            raise ValueError("email is required for bearer_email_password auth type")
        if not auth.password:
            raise ValueError("password is required for bearer_email_password auth type")

    elif auth.type == "x-api-key":
        if not auth.raw_api_key:
            raise ValueError("raw_api_key is required for x-api-key auth type")

    elif auth.type in ("custom", "custom_header"):
        if not auth.header_name:
            raise ValueError(f"header_name is required for {auth.type} auth type")
        if not auth.raw_api_key:
            raise ValueError(f"raw_api_key is required for {auth.type} auth type")

    elif auth.type == "hmac":
        # HMAC validation is a stub - will be expanded with AuthConfigHMAC
        raise ValueError("hmac auth type requires AuthConfigHMAC class (not yet implemented)")


def get_auth_header_name(auth: AuthConfig) -> str:
    """Get auth header name based on auth type."""
    # Basic auth family - all use Authorization header
    if auth.type in ("basic", "basic_email_token", "basic_token", "basic_email"):
        return "Authorization"

    # Bearer auth family - all use Authorization header
    if auth.type in (
        "bearer", "bearer_oauth", "bearer_jwt",
        "bearer_username_token", "bearer_username_password",
        "bearer_email_token", "bearer_email_password",
    ):
        return "Authorization"

    # X-API-Key header
    if auth.type == "x-api-key":
        return "X-API-Key"

    # Custom header
    if auth.type in ("custom", "custom_header"):
        return auth.header_name or "Authorization"

    # HMAC - varies by type, default to Authorization
    if auth.type == "hmac":
        return "Authorization"

    return "Authorization"


def format_auth_header_value(auth: AuthConfig, api_key: str) -> str:
    """Format auth header value based on auth type.

    Auto-compute defaults:
    - basic: Detects identifier (email OR username) and secret (password OR api_key)
    - bearer: If has identifier+secret, encodes as base64; otherwise uses api_key as-is

    Guard against double-encoding:
    - If api_key already starts with "Basic " or "Bearer ", return as-is
    - This prevents malformed headers like "Bearer Basic <base64>" when
      pre-encoded values are passed through

    Logs encoding method with masked input/output for debugging.
    """
    import logging
    from fetch_auth_encoding import encode_auth

    logger = logging.getLogger("fetch_client.config")

    def mask_value(val: str) -> str:
        """Mask value for logging, showing first 10 chars."""
        return _mask_sensitive(val, 10)

    # Guard: if api_key already has a scheme prefix, return as-is to prevent double-encoding
    # This handles cases where api_token layer returns pre-encoded values like "Basic <base64>"
    if api_key and (api_key.startswith("Basic ") or api_key.startswith("Bearer ")):
        logger.info(
            f"{LOG_PREFIX} format_auth_header_value: Pre-encoded value detected "
            f"(starts with scheme prefix), returning as-is: {mask_value(api_key)}"
        )
        return api_key

    # === Basic Auth Family ===
    if auth.type in ("basic", "basic_email_token", "basic_token", "basic_email"):
        # Map specific types to generic Basic credentials
        identifier = auth.email or auth.username or ""
        secret = auth.password or api_key
        
        # Use fetch-auth-encoding
        headers = encode_auth("basic", username=identifier, password=secret)
        return headers["Authorization"]

    # === Bearer Auth Family ===
    elif auth.type == "bearer":
        # Auto-compute: detect if credentials need base64 encoding
        identifier = auth.email or auth.username
        if identifier:
             # Has identifier → encode as base64(identifier:secret)
             secret = auth.password or api_key
             headers = encode_auth("bearer_username_password", username=identifier, password=secret)
             return headers["Authorization"]
        else:
             # No identifier → use api_key as-is (PAT, OAuth, JWT)
             headers = encode_auth("bearer", token=api_key)
             return headers["Authorization"]

    elif auth.type in ("bearer_oauth", "bearer_jwt"):
         headers = encode_auth("bearer", token=api_key)
         return headers["Authorization"]

    elif auth.type in (
        "bearer_username_token",
        "bearer_username_password",
        "bearer_email_token",
        "bearer_email_password"
    ):
         identifier = auth.email or auth.username or ""
         secret = auth.password or api_key
         headers = encode_auth("bearer_username_password", username=identifier, password=secret)
         return headers["Authorization"]

    # === Custom/API Key ===
    elif auth.type == "x-api-key":
        return api_key

    elif auth.type in ("custom", "custom_header"):
        return api_key

    # === HMAC (stub) ===
    elif auth.type == "hmac":
        # HMAC requires separate handling with AuthConfigHMAC
        raise ValueError("hmac auth type requires AuthConfigHMAC class (not yet implemented)")

    logger.warning(
        f"{LOG_PREFIX} format_auth_header_value: Unknown auth type '{auth.type}', "
        f"returning api_key as-is"
    )
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
