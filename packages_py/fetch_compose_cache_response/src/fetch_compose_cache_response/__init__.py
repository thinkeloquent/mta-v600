"""
Cache response transport wrapper for httpx's compose pattern.

RFC 7234 compliant HTTP response caching with:
- Cache-Control directive parsing and compliance
- ETag and Last-Modified conditional request support
- Vary header handling
- Stale-while-revalidate pattern
"""
from cache_response import (
    CacheControlDirectives,
    CacheEntryMetadata,
    CachedResponse,
    CacheFreshness,
    CacheLookupResult,
    CacheResponseStore,
    CacheResponseConfig,
    CacheResponseEventType,
    CacheResponseEvent,
    CacheResponseEventListener,
    BackgroundRevalidator,
    ResponseCache,
    create_response_cache,
    parse_cache_control,
    MemoryCacheStore,
    create_memory_cache_store,
)
from .transport import CacheResponseTransport, SyncCacheResponseTransport
from .factory import (
    compose_transport,
    compose_sync_transport,
    create_cache_response_transport,
    create_cache_response_sync_transport,
    create_cache_response_client,
    create_cache_response_sync_client,
)


__all__ = [
    # Re-exported types from base package
    "CacheControlDirectives",
    "CacheEntryMetadata",
    "CachedResponse",
    "CacheFreshness",
    "CacheLookupResult",
    "CacheResponseStore",
    "CacheResponseConfig",
    "CacheResponseEventType",
    "CacheResponseEvent",
    "CacheResponseEventListener",
    "BackgroundRevalidator",
    "ResponseCache",
    "create_response_cache",
    "parse_cache_control",
    "MemoryCacheStore",
    "create_memory_cache_store",
    # Transport wrappers
    "CacheResponseTransport",
    "SyncCacheResponseTransport",
    # Factory functions
    "compose_transport",
    "compose_sync_transport",
    "create_cache_response_transport",
    "create_cache_response_sync_transport",
    "create_cache_response_client",
    "create_cache_response_sync_client",
]

__version__ = "1.0.0"
