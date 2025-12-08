"""
RFC 7234 compliant HTTP response caching.

Supports Cache-Control, ETag, Last-Modified, Vary, and stale-while-revalidate.
"""
from .types import (
    CacheControlDirectives,
    CacheEntryMetadata,
    CachedResponse,
    CacheFreshness,
    CacheLookupResult,
    RevalidationResult,
    CacheResponseStore,
    CacheResponseConfig,
    CacheResponseEventType,
    CacheResponseEvent,
    CacheResponseEventListener,
    BackgroundRevalidator,
)
from .parser import (
    parse_cache_control,
    build_cache_control,
    extract_etag,
    extract_last_modified,
    parse_date_header,
    calculate_expiration,
    determine_freshness,
    is_cacheable_status,
    is_cacheable_method,
    should_cache,
    needs_revalidation,
    parse_vary,
    is_vary_uncacheable,
    extract_vary_headers,
    match_vary_headers,
    get_header_value,
    normalize_headers,
)
from .cache import (
    ResponseCache,
    create_response_cache,
    DEFAULT_CACHE_RESPONSE_CONFIG,
    merge_cache_response_config,
)
from .stores import (
    MemoryCacheStore,
    MemoryCacheStats,
    create_memory_cache_store,
)


__all__ = [
    # Types
    "CacheControlDirectives",
    "CacheEntryMetadata",
    "CachedResponse",
    "CacheFreshness",
    "CacheLookupResult",
    "RevalidationResult",
    "CacheResponseStore",
    "CacheResponseConfig",
    "CacheResponseEventType",
    "CacheResponseEvent",
    "CacheResponseEventListener",
    "BackgroundRevalidator",
    # Parser utilities
    "parse_cache_control",
    "build_cache_control",
    "extract_etag",
    "extract_last_modified",
    "parse_date_header",
    "calculate_expiration",
    "determine_freshness",
    "is_cacheable_status",
    "is_cacheable_method",
    "should_cache",
    "needs_revalidation",
    "parse_vary",
    "is_vary_uncacheable",
    "extract_vary_headers",
    "match_vary_headers",
    "get_header_value",
    "normalize_headers",
    # Cache manager
    "ResponseCache",
    "create_response_cache",
    "DEFAULT_CACHE_RESPONSE_CONFIG",
    "merge_cache_response_config",
    # Stores
    "MemoryCacheStore",
    "MemoryCacheStats",
    "create_memory_cache_store",
]

__version__ = "1.0.0"
