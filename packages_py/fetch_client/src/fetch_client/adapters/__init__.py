"""
Protocol adapters for fetch_client.
"""
from .rest_adapter import AsyncRestAdapter, SyncRestAdapter

__all__ = [
    "AsyncRestAdapter",
    "SyncRestAdapter",
]
