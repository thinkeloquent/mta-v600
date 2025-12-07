"""
Standalone retry wrapper with exponential backoff and jitter support.
"""
from .types import (
    RetryConfig,
    RetryOptions,
    RetryResult,
    RetryEvent,
    RetryEventListener,
    BackoffStrategy,
    IDEMPOTENT_METHODS,
    NON_IDEMPOTENT_METHODS,
)
from .config import (
    DEFAULT_RETRY_CONFIG,
    calculate_backoff_delay,
    calculate_delay,
    is_retryable_error,
    is_retryable_status,
    is_retryable_method,
    parse_retry_after,
    merge_config,
    async_sleep,
    sync_sleep,
)
from .executor import (
    RetryExecutor,
    create_retry_executor,
    retry,
    retry_sync,
    create_retry_wrapper,
)


__all__ = [
    # Types
    "RetryConfig",
    "RetryOptions",
    "RetryResult",
    "RetryEvent",
    "RetryEventListener",
    "BackoffStrategy",
    "IDEMPOTENT_METHODS",
    "NON_IDEMPOTENT_METHODS",
    # Config
    "DEFAULT_RETRY_CONFIG",
    "calculate_backoff_delay",
    "calculate_delay",
    "is_retryable_error",
    "is_retryable_status",
    "is_retryable_method",
    "parse_retry_after",
    "merge_config",
    "async_sleep",
    "sync_sleep",
    # Executor
    "RetryExecutor",
    "create_retry_executor",
    "retry",
    "retry_sync",
    "create_retry_wrapper",
]


__version__ = "1.0.0"
