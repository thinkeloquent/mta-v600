from typing import Dict, Optional
from pydantic import BaseModel, Field


class AgentProxyConfig(BaseModel):
    """Configuration for agent-based proxies (http_proxy/https_proxy env vars)."""
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None


class NetworkConfig(BaseModel):
    """
    Network configuration including proxy settings.
    Renamed from ProxyConfig to better reflect its scope.
    """
    default_environment: Optional[str] = "dev"
    proxy_urls: Dict[str, Optional[str]] = Field(default_factory=dict)
    ca_bundle: Optional[str] = None
    cert: Optional[str] = None
    cert_verify: bool = False
    agent_proxy: Optional[AgentProxyConfig] = None
