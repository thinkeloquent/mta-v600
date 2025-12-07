"""
HTTP client adapters for fetch_proxy_dispatcher.

Provides abstract base class and implementations for different HTTP libraries.
"""
from .base import BaseAdapter
from .adapter_httpx import HttpxAdapter

__all__ = [
    "BaseAdapter",
    "HttpxAdapter",
]
