"""
Type definitions for fetch_rate_limiter
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional, TypeVar, Generic, Literal
from abc import ABC, abstractmethod


T = TypeVar("T")


@dataclass
class RateLimitStatus:
    """Rate limit status from external API or internal state"""

    remaining: int
    """Number of requests remaining in current window"""

    reset: float
    """Unix timestamp when the limit resets"""

    limit: Optional[int] = None
    """Total limit for the window"""


@dataclass
class ScheduleOptions:
    """Options for scheduling a request"""

    priority: int = 0
    """Priority level (higher = more priority). Default: 0"""

    metadata: Optional[dict[str, Any]] = None
    """Metadata for logging/debugging"""

    deadline: Optional[float] = None
    """Deadline timestamp - reject if not processed by this time"""


@dataclass
class ScheduleResult(Generic[T]):
    """Result of a scheduled operation"""

    result: T
    """The result of the operation"""

    queue_time: float
    """Time spent waiting in queue (seconds)"""

    execution_time: float
    """Time spent executing (seconds)"""

    retries: int
    """Number of retries attempted"""


@dataclass
class StaticRateLimitConfig:
    """Configuration for static rate limiting"""

    max_requests: int
    """Maximum requests per interval"""

    interval_seconds: float
    """Interval in seconds"""


@dataclass
class DynamicRateLimitConfig:
    """Configuration for dynamic rate limiting"""

    get_rate_limit_status: Callable[[], Awaitable[RateLimitStatus]]
    """Async function to get current rate limit status"""

    fallback: Optional[StaticRateLimitConfig] = None
    """Fallback to static limits when dynamic fails"""


@dataclass
class RetryConfig:
    """Retry configuration"""

    max_retries: int = 3
    """Maximum number of retries. Default: 3"""

    base_delay_seconds: float = 1.0
    """Base delay for exponential backoff (seconds). Default: 1.0"""

    max_delay_seconds: float = 30.0
    """Maximum delay between retries (seconds). Default: 30.0"""

    jitter_factor: float = 0.5
    """Jitter factor (0-1). Default: 0.5"""

    retry_on_errors: list[str] = field(
        default_factory=lambda: ["ConnectionError", "TimeoutError"]
    )
    """Error types that should trigger retry"""

    retry_on_status: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    """HTTP status codes that should trigger retry"""


@dataclass
class RateLimiterConfig:
    """Main rate limiter configuration"""

    id: str
    """Unique identifier for this limiter instance"""

    static: Optional[StaticRateLimitConfig] = None
    """Static rate limit config (mutually exclusive with dynamic)"""

    dynamic: Optional[DynamicRateLimitConfig] = None
    """Dynamic rate limit config (mutually exclusive with static)"""

    max_queue_size: Optional[int] = None
    """Maximum queue size. Default: None (unlimited)"""

    retry: Optional[RetryConfig] = None
    """Retry configuration"""

    concurrency: int = 1
    """Concurrency limit for parallel execution. Default: 1"""


@dataclass
class RateLimiterStats:
    """Statistics from the rate limiter"""

    queue_size: int
    """Current queue size"""

    active_requests: int
    """Number of active/in-flight requests"""

    total_processed: int
    """Total requests processed"""

    total_rejected: int
    """Total requests rejected"""

    avg_queue_time_seconds: float
    """Average queue time (seconds)"""

    avg_execution_time_seconds: float
    """Average execution time (seconds)"""


# Event types
EventType = Literal[
    "rate:limited",
    "request:queued",
    "request:started",
    "request:completed",
    "request:failed",
    "request:requeued",
    "request:expired",
    "error",
]


@dataclass
class RateLimiterEvent:
    """Event emitted by the rate limiter"""

    type: EventType
    """Event type"""

    data: dict[str, Any] = field(default_factory=dict)
    """Event-specific data"""


# Event listener type
RateLimiterEventListener = Callable[[RateLimiterEvent], None]


@dataclass
class QueuedRequest(Generic[T]):
    """Queued request internal structure"""

    id: str
    """Unique request ID"""

    fn: Callable[[], Awaitable[T]]
    """The function to execute"""

    priority: int
    """Priority level"""

    enqueued_at: float
    """Enqueue timestamp"""

    deadline: Optional[float] = None
    """Optional deadline"""

    metadata: Optional[dict[str, Any]] = None
    """Metadata"""


class RateLimitStore(ABC):
    """State store interface for distributed rate limiting"""

    @abstractmethod
    async def get_count(self, key: str) -> int:
        """Get the current request count for the window"""
        pass

    @abstractmethod
    async def increment(self, key: str, ttl_seconds: float) -> int:
        """Increment the count and return new value"""
        pass

    @abstractmethod
    async def get_ttl(self, key: str) -> float:
        """Get the TTL remaining for the key (seconds)"""
        pass

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset the count"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the store connection"""
        pass
