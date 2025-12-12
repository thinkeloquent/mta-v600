"""
Utilities for resolving proxy configuration.
"""
from .resolver import resolve_proxy_url
from .types import NetworkConfig, AgentProxyConfig

__all__ = ["resolve_proxy_url", "NetworkConfig", "AgentProxyConfig"]
