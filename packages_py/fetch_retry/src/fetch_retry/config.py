"""
Configuration utilities for fetch_retry
"""
import asyncio
import random
import time
from typing import Optional
from email.utils import parsedate_to_datetime
from .types import RetryConfig, BackoffStrategy


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay_seconds=1.0,
    max_delay_seconds=30.0,
    jitter_factor=0.5,
    retry_on_errors=["ConnectionError", "TimeoutError", "OSError"],
    retry_on_status=[429, 500, 502, 503, 504],
    retry_methods=["GET", "HEAD", "OPTIONS", "PUT", "DELETE"],
    respect_retry_after=True,
)


def calculate_backoff_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate exponential backoff delay with jitter.

    Uses the "Full Jitter" strategy to prevent thundering herd:
    delay = random(0, min(cap, base * 2^attempt))

    Args:
        attempt: The current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    base = config.base_delay_seconds
    max_delay = config.max_delay_seconds
    jitter = config.jitter_factor

    # Calculate exponential delay
    exponential_delay = min(max_delay, base * (2 ** attempt))

    # Apply full jitter
    jitter_amount = random.random() * jitter * exponential_delay
    delay = exponential_delay * (1 - jitter / 2) + jitter_amount

    return min(delay, max_delay)


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay based on strategy.

    Args:
        attempt: The current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    base = config.base_delay_seconds
    max_delay = config.max_delay_seconds
    jitter = config.jitter_factor

    if config.backoff_strategy == BackoffStrategy.CONSTANT:
        base_delay = base
    elif config.backoff_strategy == BackoffStrategy.LINEAR:
        base_delay = min(max_delay, base + config.linear_increment_seconds * attempt)
    else:  # EXPONENTIAL (default)
        base_delay = min(max_delay, base * (2 ** attempt))

    # Apply jitter
    jitter_amount = random.random() * jitter * base_delay
    delay = base_delay * (1 - jitter / 2) + jitter_amount

    return min(delay, max_delay)


def is_retryable_error(error: Exception, config: RetryConfig) -> bool:
    """
    Check if an error should trigger a retry.

    Args:
        error: The error to check
        config: Retry configuration

    Returns:
        Whether the error is retryable
    """
    error_type = type(error).__name__

    # Check error type
    if error_type in config.retry_on_errors:
        return True

    # Check for base exception types
    for retry_type in config.retry_on_errors:
        if retry_type in str(type(error).__mro__):
            return True

    # Check error message for common network issues
    message = str(error).lower()
    retryable_patterns = [
        "network",
        "timeout",
        "timed out",
        "connection",
        "socket",
        "refused",
        "reset",
        "abort",
    ]

    if any(pattern in message for pattern in retryable_patterns):
        return True

    # Check cause chain
    if hasattr(error, "__cause__") and error.__cause__ is not None:
        return is_retryable_error(error.__cause__, config)

    return False


def is_retryable_status(status: int, config: RetryConfig) -> bool:
    """
    Check if an HTTP status code should trigger a retry.

    Args:
        status: The HTTP status code
        config: Retry configuration

    Returns:
        Whether the status is retryable
    """
    return status in config.retry_on_status


def is_retryable_method(method: str, config: RetryConfig) -> bool:
    """
    Check if an HTTP method is safe to retry.

    Args:
        method: The HTTP method
        config: Retry configuration

    Returns:
        Whether the method is retryable
    """
    return method.upper() in config.retry_methods


def parse_retry_after(value: Optional[str]) -> float:
    """
    Parse Retry-After header value.

    The Retry-After header can contain either:
    - A number of seconds to wait
    - An HTTP-date indicating when to retry

    Args:
        value: Retry-After header value

    Returns:
        Wait time in seconds, or 0 if parsing fails
    """
    if not value:
        return 0

    # Try parsing as seconds
    try:
        return float(value)
    except ValueError:
        pass

    # Try parsing as HTTP-date
    try:
        dt = parsedate_to_datetime(value)
        return max(0, dt.timestamp() - time.time())
    except (ValueError, TypeError):
        pass

    return 0


def merge_config(config: Optional[RetryConfig] = None) -> RetryConfig:
    """
    Merge configuration with defaults.

    Args:
        config: User-provided configuration

    Returns:
        Complete configuration with defaults
    """
    if config is None:
        return DEFAULT_RETRY_CONFIG
    return config


async def async_sleep(seconds: float) -> None:
    """
    Sleep for a specified duration (async).

    Args:
        seconds: Duration in seconds
    """
    await asyncio.sleep(seconds)


def sync_sleep(seconds: float) -> None:
    """
    Sleep for a specified duration (sync).

    Args:
        seconds: Duration in seconds
    """
    time.sleep(seconds)
