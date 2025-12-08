"""
Types for RFC 7234 HTTP response caching.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


@dataclass
class CacheControlDirectives:
    """Parsed Cache-Control directives."""

    no_store: bool = False
    """Response must not be cached."""

    no_cache: bool = False
    """Response must be revalidated before use."""

    max_age: Optional[int] = None
    """Maximum age in seconds."""

    s_maxage: Optional[int] = None
    """Shared cache maximum age in seconds."""

    private: bool = False
    """Response is private (user-specific)."""

    public: bool = False
    """Response is public (can be cached by shared caches)."""

    must_revalidate: bool = False
    """Response must be revalidated if stale."""

    proxy_revalidate: bool = False
    """Proxy must revalidate if stale."""

    no_transform: bool = False
    """Response must not be transformed."""

    stale_while_revalidate: Optional[int] = None
    """Response can be served stale while revalidating."""

    stale_if_error: Optional[int] = None
    """Response can be served stale if error occurs."""

    immutable: bool = False
    """Response will not change."""


@dataclass
class CacheEntryMetadata:
    """Cache entry metadata."""

    url: str
    """Request URL."""

    method: str
    """Request method."""

    status_code: int
    """Response status code."""

    headers: Dict[str, str]
    """Response headers."""

    cached_at: float
    """When the response was cached (Unix timestamp)."""

    expires_at: float
    """When the cache entry expires (Unix timestamp)."""

    etag: Optional[str] = None
    """ETag for conditional requests."""

    last_modified: Optional[str] = None
    """Last-Modified date for conditional requests."""

    cache_control: Optional[str] = None
    """Original Cache-Control header."""

    directives: Optional[CacheControlDirectives] = None
    """Parsed Cache-Control directives."""

    vary: Optional[str] = None
    """Vary header value."""

    vary_headers: Optional[Dict[str, str]] = None
    """Request headers used for Vary matching."""


@dataclass
class CachedResponse:
    """Cached response entry."""

    metadata: CacheEntryMetadata
    """Cache entry metadata."""

    body: Optional[bytes] = None
    """Response body."""


class CacheFreshness(str, Enum):
    """Cache freshness status."""

    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"


@dataclass
class CacheLookupResult:
    """Result of cache lookup."""

    found: bool
    """Whether a cached response was found."""

    response: Optional[CachedResponse] = None
    """The cached response if found."""

    freshness: Optional[CacheFreshness] = None
    """Freshness status of the cached response."""

    should_revalidate: bool = False
    """Whether conditional request should be made."""

    etag: Optional[str] = None
    """ETag for If-None-Match header."""

    last_modified: Optional[str] = None
    """Last-Modified for If-Modified-Since header."""


@dataclass
class RevalidationResult:
    """Revalidation result."""

    valid: bool
    """Whether the cached response is still valid."""

    response: Optional[CachedResponse] = None
    """Updated response if not valid."""


class CacheResponseStore(ABC):
    """Cache store interface."""

    @abstractmethod
    async def get(self, key: str) -> Optional[CachedResponse]:
        """Get a cached response by key."""
        pass

    @abstractmethod
    async def set(self, key: str, response: CachedResponse) -> None:
        """Store a response."""
        pass

    @abstractmethod
    async def has(self, key: str) -> bool:
        """Check if a key exists."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a cached response."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached responses."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get current size of store."""
        pass

    @abstractmethod
    async def keys(self) -> List[str]:
        """Get all keys (for cleanup)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the store and release resources."""
        pass


@dataclass
class CacheResponseConfig:
    """Configuration for cache response."""

    methods: List[str] = field(default_factory=lambda: ["GET", "HEAD"])
    """Methods to cache. Default: ['GET', 'HEAD']."""

    cacheable_statuses: List[int] = field(
        default_factory=lambda: [200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501]
    )
    """Status codes to cache."""

    default_ttl_seconds: float = 0
    """Default TTL in seconds when no Cache-Control. Default: 0 (no caching)."""

    max_ttl_seconds: float = 86400
    """Maximum TTL in seconds. Default: 86400 (24 hours)."""

    respect_no_cache: bool = True
    """Whether to respect no-cache directive. Default: True."""

    respect_no_store: bool = True
    """Whether to respect no-store directive. Default: True."""

    respect_private: bool = True
    """Whether to respect private directive. Default: True (honor it)."""

    stale_while_revalidate: bool = True
    """Enable stale-while-revalidate. Default: True."""

    stale_if_error: bool = True
    """Enable stale-if-error. Default: True."""

    include_query_in_key: bool = True
    """Whether to include query string in cache key. Default: True."""

    key_generator: Optional[Callable[[str, str, Optional[Dict[str, str]]], str]] = None
    """Custom cache key generator."""

    vary_headers: List[str] = field(default_factory=list)
    """Headers to include in Vary-based cache key."""


class CacheResponseEventType(str, Enum):
    """Event types for cache operations."""

    CACHE_HIT = "cache:hit"
    CACHE_MISS = "cache:miss"
    CACHE_STORE = "cache:store"
    CACHE_EXPIRE = "cache:expire"
    CACHE_REVALIDATE = "cache:revalidate"
    CACHE_STALE_SERVE = "cache:stale-serve"
    CACHE_BYPASS = "cache:bypass"


@dataclass
class CacheResponseEvent:
    """Cache event."""

    type: CacheResponseEventType
    key: str
    url: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None


CacheResponseEventListener = Callable[[CacheResponseEvent], None]
"""Event listener type."""

BackgroundRevalidator = Callable[[str, Optional[Dict[str, str]]], None]
"""Background revalidation callback (async version)."""
