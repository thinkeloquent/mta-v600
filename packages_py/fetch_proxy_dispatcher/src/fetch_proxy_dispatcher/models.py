"""
Configuration dataclasses for fetch_proxy_dispatcher.

Uses standard library dataclasses for configuration models.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union, List, Literal, ItemsView, TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

# Type aliases
ClientType = Literal["dev", "stay_alive", "do_not_stay_alive"]


@dataclass
class ProxyConfig:
    """Resolved proxy configuration."""
    proxy_url: Optional[str] = None
    verify_ssl: bool = False
    timeout: float = 30.0
    trust_env: bool = False  # We handle env ourselves
    cert: Optional[Union[str, tuple]] = None  # Client cert: path or (cert, key) tuple
    ca_bundle: Optional[str] = None  # CA bundle path for SSL verification


class ProxyUrlConfig:
    """
    Per-environment proxy URLs with user-definable environment names.

    Accepts arbitrary environment names as keyword arguments.
    Environment lookup is case-sensitive.

    Example:
        >>> config = ProxyUrlConfig(
        ...     Live="http://proxy.company.com:8080",
        ...     STAGING="http://qa-proxy.company.com:8080",
        ... )
        >>> config.get("Live")
        'http://proxy.company.com:8080'

        >>> # Legacy usage still works
        >>> config = ProxyUrlConfig(PROD="http://proxy:8080", DEV="http://dev-proxy:8080")
    """

    def __init__(self, **kwargs: Optional[str]) -> None:
        """
        Initialize with arbitrary environment-to-URL mappings.

        Args:
            **kwargs: Environment name to proxy URL mappings.
                      Keys are environment names (case-sensitive).
                      Values are proxy URLs or None.
        """
        self._urls: Dict[str, Optional[str]] = kwargs

    def get(self, environment: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get proxy URL for an environment (case-sensitive).

        Args:
            environment: Environment name to look up.
            default: Default value if environment not found.

        Returns:
            Proxy URL for the environment or default.
        """
        return self._urls.get(environment, default)

    def __getattr__(self, name: str) -> Optional[str]:
        """
        Allow attribute-style access for backward compatibility.

        Example:
            config.PROD  # Same as config.get("PROD")
        """
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return self._urls.get(name)

    def environments(self) -> List[str]:
        """
        Get list of configured environment names.

        Returns:
            List of environment names that have URLs configured.
        """
        return list(self._urls.keys())

    def items(self) -> ItemsView[str, Optional[str]]:
        """Get all environment-URL pairs."""
        return self._urls.items()

    def __repr__(self) -> str:
        pairs = ", ".join(f"{k}={v!r}" for k, v in self._urls.items())
        return f"ProxyUrlConfig({pairs})"


@dataclass
class AgentProxyConfig:
    """Agent proxy override configuration."""
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None


@dataclass
class FactoryConfig:
    """Configuration for ProxyDispatcherFactory."""
    proxy_urls: Optional[ProxyUrlConfig] = None
    agent_proxy: Optional[AgentProxyConfig] = None
    default_environment: Optional[str] = None  # Accepts any user-defined environment name
    cert: Optional[Union[str, tuple]] = None  # Client cert: path or (cert, key) tuple
    ca_bundle: Optional[str] = None  # CA bundle path for SSL verification
    cert_verify: Optional[bool] = None  # SSL cert verification (None = use default False)


@dataclass
class DispatcherResult:
    """
    Result containing client and configuration.

    Attributes:
        client: Configured httpx.Client or httpx.AsyncClient
        config: The ProxyConfig used to create the client
        proxy_dict: Raw kwargs dict for manual client creation
    """
    client: Union["httpx.Client", "httpx.AsyncClient"]
    config: ProxyConfig
    proxy_dict: Dict[str, Any]
