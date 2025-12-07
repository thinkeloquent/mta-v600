"""
Retry transport wrapper for httpx's compose pattern.
"""
from fetch_retry import (
    RetryConfig,
    RetryResult,
    RetryEvent,
    RetryOptions,
    BackoffStrategy,
)
from .transport import RetryTransport, SyncRetryTransport
from .factory import (
    compose_transport,
    compose_sync_transport,
    create_retry_client,
    create_retry_sync_client,
    create_api_retry_transport,
    RETRY_PRESETS,
)


__all__ = [
    # Re-exported types from base package
    "RetryConfig",
    "RetryResult",
    "RetryEvent",
    "RetryOptions",
    "BackoffStrategy",
    # Transport wrappers
    "RetryTransport",
    "SyncRetryTransport",
    # Factory functions
    "compose_transport",
    "compose_sync_transport",
    "create_retry_client",
    "create_retry_sync_client",
    "create_api_retry_transport",
    "RETRY_PRESETS",
]

__version__ = "1.0.0"
