"""
Types for cache_request package.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, Optional, TypeVar, Dict, List
import asyncio

T = TypeVar("T")


@dataclass
class IdempotencyConfig:
    """Configuration for idempotency key generation and management."""

    header_name: str = "Idempotency-Key"
    """Header name for the idempotency key."""

    ttl_seconds: float = 86400  # 24 hours
    """TTL for cached responses in seconds."""

    auto_generate: bool = True
    """Whether to auto-generate keys for applicable methods."""

    methods: List[str] = field(default_factory=lambda: ["POST", "PATCH"])
    """HTTP methods that require idempotency keys."""

    key_generator: Optional[Callable[[], str]] = None
    """Custom key generator function."""


@dataclass
class SingleflightConfig:
    """Configuration for request coalescing (singleflight)."""

    ttl_seconds: float = 30  # 30 seconds
    """TTL for in-flight request tracking in seconds."""

    methods: List[str] = field(default_factory=lambda: ["GET", "HEAD"])
    """HTTP methods to apply coalescing to."""

    fingerprint_generator: Optional[Callable[["RequestFingerprint"], str]] = None
    """Custom request fingerprint generator."""

    include_headers: bool = False
    """Whether to include headers in fingerprint."""

    header_keys: List[str] = field(default_factory=list)
    """Headers to include in fingerprint if include_headers is True."""


@dataclass
class RequestFingerprint:
    """Request fingerprint components for generating cache keys."""

    method: str
    url: str
    headers: Optional[Dict[str, str]] = None
    body: Optional[bytes] = None


@dataclass
class StoredResponse(Generic[T]):
    """Stored response for idempotency."""

    value: T
    """The cached response value."""

    cached_at: float
    """When the response was cached (Unix timestamp)."""

    expires_at: float
    """When the cache entry expires (Unix timestamp)."""

    fingerprint: Optional[str] = None
    """Original request fingerprint for validation."""


@dataclass
class InFlightRequest(Generic[T]):
    """In-flight request tracker for singleflight."""

    future: asyncio.Future[T]
    """Future that resolves when the request completes."""

    subscribers: int = 1
    """Number of subscribers waiting for this request."""

    started_at: float = 0
    """When the request was initiated (Unix timestamp)."""


class CacheRequestStore(ABC):
    """Cache request store interface."""

    @abstractmethod
    async def get(self, key: str) -> Optional[StoredResponse]:
        """Get a stored response by idempotency key."""
        pass

    @abstractmethod
    async def set(self, key: str, response: StoredResponse) -> None:
        """Store a response with an idempotency key."""
        pass

    @abstractmethod
    async def has(self, key: str) -> bool:
        """Check if a key exists."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a stored response."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all stored responses."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get current size of store."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the store and release resources."""
        pass


class SingleflightStore(ABC):
    """Singleflight store interface for tracking in-flight requests."""

    @abstractmethod
    def get(self, fingerprint: str) -> Optional[InFlightRequest]:
        """Get an in-flight request by fingerprint."""
        pass

    @abstractmethod
    def set(self, fingerprint: str, request: InFlightRequest) -> None:
        """Register an in-flight request."""
        pass

    @abstractmethod
    def delete(self, fingerprint: str) -> bool:
        """Remove an in-flight request."""
        pass

    @abstractmethod
    def has(self, fingerprint: str) -> bool:
        """Check if a request is in-flight."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Get current number of in-flight requests."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all in-flight requests."""
        pass


@dataclass
class CacheRequestConfig:
    """Combined cache request configuration."""

    idempotency: Optional[IdempotencyConfig] = None
    """Idempotency configuration."""

    singleflight: Optional[SingleflightConfig] = None
    """Singleflight configuration."""

    store: Optional[CacheRequestStore] = None
    """Custom store for idempotency responses."""


@dataclass
class IdempotencyCheckResult(Generic[T]):
    """Result of an idempotency check."""

    cached: bool
    """Whether a cached response was found."""

    key: str
    """The idempotency key used."""

    response: Optional[StoredResponse[T]] = None
    """The cached response if found."""


@dataclass
class SingleflightResult(Generic[T]):
    """Result of a singleflight operation."""

    value: T
    """The result value."""

    shared: bool
    """Whether this was from a shared/coalesced request."""

    subscribers: int
    """Number of requests that shared this result."""


class CacheRequestEventType(str, Enum):
    """Event types for cache request operations."""

    IDEMPOTENCY_HIT = "idempotency:hit"
    IDEMPOTENCY_MISS = "idempotency:miss"
    IDEMPOTENCY_STORE = "idempotency:store"
    IDEMPOTENCY_EXPIRE = "idempotency:expire"
    SINGLEFLIGHT_JOIN = "singleflight:join"
    SINGLEFLIGHT_LEAD = "singleflight:lead"
    SINGLEFLIGHT_COMPLETE = "singleflight:complete"
    SINGLEFLIGHT_ERROR = "singleflight:error"


@dataclass
class CacheRequestEvent:
    """Cache request event."""

    type: CacheRequestEventType
    key: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None


CacheRequestEventListener = Callable[[CacheRequestEvent], None]
"""Event listener type."""
