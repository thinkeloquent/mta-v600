"""
Type definitions for fetch_retry
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional, TypeVar, Generic, Literal, Union
from enum import Enum


T = TypeVar("T")


class BackoffStrategy(str, Enum):
    """Backoff strategy type"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


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
    """Jitter factor (0-1) for Full Jitter strategy. Default: 0.5"""

    retry_on_errors: list[str] = field(
        default_factory=lambda: ["ConnectionError", "TimeoutError", "OSError"]
    )
    """Error types that should trigger retry"""

    retry_on_status: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    """HTTP status codes that should trigger retry"""

    retry_methods: list[str] = field(
        default_factory=lambda: ["GET", "HEAD", "OPTIONS", "PUT", "DELETE"]
    )
    """HTTP methods that are safe to retry (idempotent methods)"""

    respect_retry_after: bool = True
    """Whether to respect Retry-After header. Default: True"""

    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    """Backoff strategy. Default: exponential"""

    linear_increment_seconds: float = 1.0
    """Linear increment for linear backoff (seconds). Default: 1.0"""


@dataclass
class RetryOptions:
    """Options for individual retry operations"""

    max_retries: Optional[int] = None
    """Override max retries for this operation"""

    metadata: Optional[dict[str, Any]] = None
    """Metadata for logging/debugging"""

    should_retry: Optional[Callable[[Exception, int], bool]] = None
    """Custom should-retry predicate for this operation"""


@dataclass
class RetryResult(Generic[T]):
    """Result of a retried operation"""

    result: T
    """The result of the operation"""

    retries: int
    """Number of retries attempted (0 if succeeded on first try)"""

    total_time_seconds: float
    """Total time spent including retries (seconds)"""

    delay_time_seconds: float
    """Time spent in backoff delays (seconds)"""


# Event types
EventType = Literal[
    "attempt:start",
    "attempt:success",
    "attempt:fail",
    "retry:wait",
    "retry:abort",
]


@dataclass
class RetryEvent:
    """Event emitted by the retry executor"""

    type: EventType
    """Event type"""

    attempt: int
    """Current attempt number"""

    data: dict[str, Any] = field(default_factory=dict)
    """Event-specific data"""


# Event listener type
RetryEventListener = Callable[[RetryEvent], None]


# Idempotent HTTP methods that are safe to retry
IDEMPOTENT_METHODS = ["GET", "HEAD", "OPTIONS", "PUT", "DELETE", "TRACE"]

# Non-idempotent methods that require special consideration for retry
NON_IDEMPOTENT_METHODS = ["POST", "PATCH"]
