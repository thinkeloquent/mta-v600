"""
Rate limiter transport wrapper for httpx's compose pattern.
"""
from fetch_rate_limiter import (
    RateLimiterConfig,
    RateLimiterStats,
    RateLimiterEvent,
    StaticRateLimitConfig,
    DynamicRateLimitConfig,
    RetryConfig,
    RateLimitStore,
)
from .transport import RateLimitTransport, SyncRateLimitTransport
from .factory import (
    compose_transport,
    compose_sync_transport,
    create_rate_limited_client,
    create_rate_limited_sync_client,
    create_api_rate_limiter,
)


__all__ = [
    # Re-exported types from base package
    "RateLimiterConfig",
    "RateLimiterStats",
    "RateLimiterEvent",
    "StaticRateLimitConfig",
    "DynamicRateLimitConfig",
    "RetryConfig",
    "RateLimitStore",
    # Transport wrappers
    "RateLimitTransport",
    "SyncRateLimitTransport",
    # Factory functions
    "compose_transport",
    "compose_sync_transport",
    "create_rate_limited_client",
    "create_rate_limited_sync_client",
    "create_api_rate_limiter",
]

__version__ = "1.0.0"
