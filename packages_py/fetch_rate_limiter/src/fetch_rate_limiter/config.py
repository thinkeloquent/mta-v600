"""
Configuration utilities for fetch_rate_limiter
"""
import asyncio
import random
import time
from typing import Optional
from .types import RetryConfig, RateLimiterConfig


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay_seconds=1.0,
    max_delay_seconds=30.0,
    jitter_factor=0.5,
    retry_on_errors=["ConnectionError", "TimeoutError", "OSError"],
    retry_on_status=[429, 500, 502, 503, 504],
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
    if any(
        term in message
        for term in ["network", "timeout", "connection", "socket", "refused"]
    ):
        return True

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


def merge_config(config: RateLimiterConfig) -> RateLimiterConfig:
    """
    Merge configuration with defaults.

    Args:
        config: User-provided configuration

    Returns:
        Complete configuration with defaults
    """
    if config.retry is None:
        config.retry = DEFAULT_RETRY_CONFIG
    else:
        # Merge with defaults for missing fields
        config.retry = RetryConfig(
            max_retries=config.retry.max_retries,
            base_delay_seconds=config.retry.base_delay_seconds,
            max_delay_seconds=config.retry.max_delay_seconds,
            jitter_factor=config.retry.jitter_factor,
            retry_on_errors=config.retry.retry_on_errors or DEFAULT_RETRY_CONFIG.retry_on_errors,
            retry_on_status=config.retry.retry_on_status or DEFAULT_RETRY_CONFIG.retry_on_status,
        )

    return config


def generate_request_id() -> str:
    """Generate a unique request ID"""
    import secrets

    return f"req_{int(time.time() * 1000)}_{secrets.token_hex(4)}"


async def async_sleep(seconds: float) -> None:
    """
    Sleep for a specified duration.

    Args:
        seconds: Duration in seconds
    """
    await asyncio.sleep(seconds)


def sync_sleep(seconds: float) -> None:
    """
    Sleep for a specified duration (synchronous).

    Args:
        seconds: Duration in seconds
    """
    time.sleep(seconds)
