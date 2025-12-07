"""
Type definitions for cache_dsn
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional, Literal
from abc import ABC, abstractmethod


@dataclass
class ResolvedEndpoint:
    """A resolved endpoint from DNS/service discovery"""

    host: str
    """The resolved IP address or hostname"""

    port: int
    """The port number"""

    healthy: bool = True
    """Whether this endpoint is considered healthy"""

    weight: Optional[int] = None
    """Optional weight for load balancing (higher = more traffic)"""

    priority: Optional[int] = None
    """Optional priority (lower = higher priority)"""

    last_checked: Optional[float] = None
    """Last time this endpoint was checked"""

    metadata: Optional[dict[str, Any]] = None
    """Custom metadata"""


@dataclass
class CachedEntry:
    """A cached DNS entry"""

    dsn: str
    """The original DSN/hostname that was resolved"""

    endpoints: list[ResolvedEndpoint]
    """List of resolved endpoints"""

    resolved_at: float
    """When this entry was resolved"""

    expires_at: float
    """When this entry expires (Unix timestamp)"""

    ttl_seconds: float
    """TTL in seconds"""

    hit_count: int = 0
    """Number of times this entry has been used"""


@dataclass
class ResolutionResult:
    """Result of a resolution operation"""

    endpoints: list[ResolvedEndpoint]
    """The resolved endpoints"""

    from_cache: bool
    """Whether this result came from cache"""

    ttl_remaining_seconds: float
    """Time until cache expires (seconds), or 0 if fresh resolution"""

    resolution_time_seconds: float
    """Resolution time in seconds"""


# Load balancing strategy type
LoadBalanceStrategy = Literal[
    "round-robin",
    "random",
    "weighted",
    "least-connections",
    "power-of-two",
]


@dataclass
class HealthCheckConfig:
    """Health check configuration"""

    enabled: bool = False
    """Whether to enable health checks. Default: False"""

    interval_seconds: float = 30.0
    """Interval between health checks (seconds). Default: 30.0"""

    timeout_seconds: float = 5.0
    """Timeout for health check (seconds). Default: 5.0"""

    unhealthy_threshold: int = 3
    """Number of consecutive failures before marking unhealthy. Default: 3"""

    healthy_threshold: int = 2
    """Number of consecutive successes before marking healthy. Default: 2"""


@dataclass
class DnsCacheConfig:
    """Configuration for the DNS cache resolver"""

    id: str
    """Unique identifier for this resolver instance"""

    default_ttl_seconds: float = 60.0
    """Default TTL for cached entries (seconds). Default: 60.0 (1 minute)"""

    min_ttl_seconds: float = 1.0
    """Minimum TTL (prevents overly aggressive caching). Default: 1.0"""

    max_ttl_seconds: float = 300.0
    """Maximum TTL (prevents stale data). Default: 300.0 (5 minutes)"""

    max_entries: int = 1000
    """Maximum number of cached entries. Default: 1000"""

    respect_dns_ttl: bool = True
    """Whether to respect DNS TTL from response. Default: True"""

    negative_ttl_seconds: float = 30.0
    """Negative cache TTL for failed lookups (seconds). Default: 30.0"""

    stale_while_revalidate: bool = True
    """Whether to enable stale-while-revalidate. Default: True"""

    stale_grace_period_seconds: float = 5.0
    """Grace period for serving stale data while revalidating. Default: 5.0"""

    load_balance_strategy: LoadBalanceStrategy = "round-robin"
    """Load balancing strategy. Default: 'round-robin'"""

    health_check: Optional[HealthCheckConfig] = None
    """Health check configuration"""


@dataclass
class DnsCacheStats:
    """Statistics from the DNS cache"""

    total_entries: int
    """Total number of cached entries"""

    cache_hits: int
    """Total cache hits"""

    cache_misses: int
    """Total cache misses"""

    hit_ratio: float
    """Cache hit ratio (0-1)"""

    stale_hits: int
    """Total stale-while-revalidate hits"""

    avg_resolution_time_seconds: float
    """Average resolution time (seconds)"""

    healthy_endpoints: int
    """Total healthy endpoints across all entries"""

    unhealthy_endpoints: int
    """Total unhealthy endpoints across all entries"""


# Event types
EventType = Literal[
    "cache:hit",
    "cache:miss",
    "cache:stale",
    "cache:expired",
    "cache:evicted",
    "resolve:start",
    "resolve:success",
    "resolve:error",
    "health:check",
    "health:changed",
    "error",
]


@dataclass
class DnsCacheEvent:
    """Event emitted by the DNS cache resolver"""

    type: EventType
    """Event type"""

    data: dict[str, Any] = field(default_factory=dict)
    """Event-specific data"""


# Event listener type
DnsCacheEventListener = Callable[[DnsCacheEvent], None]

# Custom resolver function type
ResolverFunction = Callable[[str], Awaitable[list[ResolvedEndpoint]]]


class DnsCacheStore(ABC):
    """State store interface for DNS cache"""

    @abstractmethod
    async def get(self, key: str) -> Optional[CachedEntry]:
        """Get a cached entry"""
        pass

    @abstractmethod
    async def set(self, key: str, entry: CachedEntry) -> None:
        """Set a cached entry"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a cached entry"""
        pass

    @abstractmethod
    async def has(self, key: str) -> bool:
        """Check if an entry exists"""
        pass

    @abstractmethod
    async def keys(self) -> list[str]:
        """Get all cached keys"""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get the number of cached entries"""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached entries"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the store connection"""
        pass
