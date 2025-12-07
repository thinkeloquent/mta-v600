"""
Standalone API rate limiter with queue management, priority scheduling, and distributed state support.
"""
from .types import (
    RateLimitStatus,
    ScheduleOptions,
    ScheduleResult,
    StaticRateLimitConfig,
    DynamicRateLimitConfig,
    RetryConfig,
    RateLimiterConfig,
    RateLimiterStats,
    RateLimiterEvent,
    RateLimiterEventListener,
    QueuedRequest,
    RateLimitStore,
)
from .config import (
    DEFAULT_RETRY_CONFIG,
    calculate_backoff_delay,
    is_retryable_error,
    is_retryable_status,
    merge_config,
    generate_request_id,
    async_sleep,
    sync_sleep,
)
from .queue import PriorityQueue
from .stores import MemoryStore, create_memory_store
from .limiter import RateLimiter, create_rate_limiter


__all__ = [
    # Types
    "RateLimitStatus",
    "ScheduleOptions",
    "ScheduleResult",
    "StaticRateLimitConfig",
    "DynamicRateLimitConfig",
    "RetryConfig",
    "RateLimiterConfig",
    "RateLimiterStats",
    "RateLimiterEvent",
    "RateLimiterEventListener",
    "QueuedRequest",
    "RateLimitStore",
    # Config
    "DEFAULT_RETRY_CONFIG",
    "calculate_backoff_delay",
    "is_retryable_error",
    "is_retryable_status",
    "merge_config",
    "generate_request_id",
    "async_sleep",
    "sync_sleep",
    # Queue
    "PriorityQueue",
    # Stores
    "MemoryStore",
    "create_memory_store",
    # Limiter
    "RateLimiter",
    "create_rate_limiter",
]

# Optional Redis store
try:
    from .stores import RedisStore, create_redis_store

    __all__.extend(["RedisStore", "create_redis_store"])
except ImportError:
    pass


__version__ = "1.0.0"
