"""Type definitions for static configuration management.

Provides Pydantic models for configuration validation and type safety.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConfigScope(str, Enum):
    """Defines the valid configuration levels."""
    GLOBAL = "global"
    SERVICE = "service"
    TENANT = "tenant"


class ConfigProperty(BaseModel):
    """Represents a property at a specific scope."""
    scope: ConfigScope = ConfigScope.GLOBAL
    value: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResolutionContext(BaseModel):
    """Specifies the context for a property lookup."""
    tenant_id: Optional[str] = None
    service_id: Optional[str] = None


class ProviderConfig(BaseModel):
    """Configuration for an external API provider.

    Auth type selection determines how credentials are used:
    - basic: Auto-compute Basic <base64((username|email):(password|token))>
    - basic_email_token: Basic <base64(email:token)> - Atlassian APIs
    - basic_token: Basic <base64(username:token)>
    - basic_email: Basic <base64(email:password)>
    - bearer: Auto-compute Bearer <PAT|OAuth|JWT|base64(...)>
    - bearer_oauth: Bearer <OAuth2.0_token>
    - bearer_jwt: Bearer <JWT_token>
    - bearer_username_token: Bearer <base64(username:token)>
    - bearer_username_password: Bearer <base64(username:password)>
    - bearer_email_token: Bearer <base64(email:token)>
    - bearer_email_password: Bearer <base64(email:password)>
    - x-api-key: api_key in X-API-Key header
    - custom: raw string in custom header
    - custom_header: api_key in custom header
    - hmac: AWS Signature, GCP HMAC, HTTP Signatures, Webhooks
    """

    # Base configuration
    base_url: Optional[str] = None
    model: Optional[str] = None
    health_endpoint: Optional[str] = None

    # Auth type selection
    api_auth_type: Optional[str] = None  # One of the AuthType values

    # Primary API key / token
    env_api_key: Optional[str] = None
    env_api_key_fallbacks: List[str] = Field(default_factory=list)

    # Username-based auth
    env_username: Optional[str] = None
    env_username_fallbacks: List[str] = Field(default_factory=list)

    # Email-based auth
    env_email: Optional[str] = None
    env_email_fallbacks: List[str] = Field(default_factory=list)

    # Password-based auth
    env_password: Optional[str] = None
    env_password_fallbacks: List[str] = Field(default_factory=list)

    # PAT/OAuth/JWT specific
    env_pat: Optional[str] = None
    env_jwt: Optional[str] = None
    env_oauth_token: Optional[str] = None

    # Base URL from environment
    env_base_url: Optional[str] = None

    # Custom header name (for custom/custom_header types)
    custom_header_name: Optional[str] = None

    # Token resolver type
    token_resolver: Optional[str] = None  # static, startup, request

    # Provider-specific config overrides
    # These fields (proxy, client, headers) correspond to overrides in server.yaml
    # They are not explicitly defined here as typed fields to allow for
    # simple dictionary access or they can be added if strict typing is desired.
    # For now, we rely on the dynamic loading which puts them in the provider config dict.
    # However, if we want them to be part of the model, we should add them.
    # Given the previous pattern was a dict, let's leave them flexible or add them.
    # Since YamlConfig constructs this, and extra fields might be ignored or stored,
    # let's explicitly add them as Optional fields for better type safety if possible,
    # or just remove the overwrite_root_config field as it's no longer used.
    # The safest bet for pydantic models that allow extra fields is to just remove the old one.
    # If the model configuration allows extra, then proxy/client at root will work.
    # Let's check if the model allows extra. It inherits form BaseModel. default is 'ignore' or 'extra'.
    # Assuming standard pydantic behavior, let's just remove the field.


class ClientConfig(BaseModel):
    """HTTP client configuration."""
    timeout_seconds: float = 60.0
    timeout_ms: int = 60000
    keep_alive_timeout_seconds: float = 5.0
    keep_alive_timeout_ms: int = 5000
    max_connections: int = 10


class DisplayConfig(BaseModel):
    """Display configuration for output formatting."""
    separator_char: str = "="
    thin_separator_char: str = "-"
    separator_length: int = 60


class AgentProxyConfig(BaseModel):
    """Agent proxy settings."""
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None


class ProxyConfig(BaseModel):
    """Proxy configuration."""
    default_environment: str = "dev"
    proxy_urls: Dict[str, str] = Field(default_factory=dict)
    ca_bundle: Optional[str] = None
    cert: Optional[str] = None
    cert_verify: bool = False
    agent_proxy: AgentProxyConfig = Field(default_factory=AgentProxyConfig)


class ServerConfig(BaseModel):
    """Root configuration model for server.{APP_ENV}.yaml files."""
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)
    default_provider: str = "gemini"
    client: ClientConfig = Field(default_factory=ClientConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
