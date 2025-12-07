"""
Abstract base class for HTTP client adapters.

Defines the interface that all adapters must implement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from ..models import ProxyConfig, DispatcherResult


class BaseAdapter(ABC):
    """
    Abstract adapter for different HTTP libraries.

    Subclasses must implement methods for creating sync and async clients,
    as well as generating configuration dictionaries.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Adapter name (e.g., 'httpx', 'requests', 'aiohttp').

        Returns:
            String identifier for this adapter.
        """
        ...

    @property
    @abstractmethod
    def supports_sync(self) -> bool:
        """
        Whether this adapter supports synchronous clients.

        Returns:
            True if sync clients are supported.
        """
        ...

    @property
    @abstractmethod
    def supports_async(self) -> bool:
        """
        Whether this adapter supports asynchronous clients.

        Returns:
            True if async clients are supported.
        """
        ...

    @abstractmethod
    def create_sync_client(self, config: ProxyConfig) -> DispatcherResult:
        """
        Create a synchronous HTTP client.

        Args:
            config: Proxy configuration to apply.

        Returns:
            DispatcherResult containing the client and configuration.

        Raises:
            NotImplementedError: If sync is not supported.
        """
        ...

    @abstractmethod
    def create_async_client(self, config: ProxyConfig) -> DispatcherResult:
        """
        Create an asynchronous HTTP client.

        Args:
            config: Proxy configuration to apply.

        Returns:
            DispatcherResult containing the client and configuration.

        Raises:
            NotImplementedError: If async is not supported.
        """
        ...

    @abstractmethod
    def get_proxy_dict(self, config: ProxyConfig) -> Dict[str, Any]:
        """
        Get proxy configuration as dict for manual client creation.

        Args:
            config: Proxy configuration.

        Returns:
            Dictionary of kwargs suitable for the library's client constructor.
        """
        ...
