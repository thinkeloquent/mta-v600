"""
Cache request transport wrapper for httpx's compose pattern.
"""
from cache_request import (
    IdempotencyConfig,
    SingleflightConfig,
    RequestFingerprint,
    StoredResponse,
    CacheRequestStore,
    SingleflightStore,
    CacheRequestEventType,
    CacheRequestEvent,
    CacheRequestEventListener,
)
from .transport import CacheRequestTransport, SyncCacheRequestTransport
from .factory import (
    compose_transport,
    compose_sync_transport,
    create_cache_request_transport,
    create_cache_request_sync_transport,
    create_cache_request_client,
    create_cache_request_sync_client,
)


__all__ = [
    # Re-exported types from base package
    "IdempotencyConfig",
    "SingleflightConfig",
    "RequestFingerprint",
    "StoredResponse",
    "CacheRequestStore",
    "SingleflightStore",
    "CacheRequestEventType",
    "CacheRequestEvent",
    "CacheRequestEventListener",
    # Transport wrappers
    "CacheRequestTransport",
    "SyncCacheRequestTransport",
    # Factory functions
    "compose_transport",
    "compose_sync_transport",
    "create_cache_request_transport",
    "create_cache_request_sync_transport",
    "create_cache_request_client",
    "create_cache_request_sync_client",
]

__version__ = "1.0.0"
