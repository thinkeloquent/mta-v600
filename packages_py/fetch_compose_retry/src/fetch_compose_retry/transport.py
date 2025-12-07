"""
Retry transport wrapper for httpx
"""
import asyncio
import time
from typing import Optional, Callable, Any
from email.utils import parsedate_to_datetime

import httpx

from fetch_retry import (
    RetryConfig,
    RetryExecutor,
    calculate_backoff_delay,
    is_retryable_status,
    is_retryable_method,
    parse_retry_after,
    merge_config,
)


class RetryTransport(httpx.AsyncBaseTransport):
    """
    Retry transport wrapper for httpx.

    Wraps another transport and applies retry logic to all requests.
    Implements the "Transport Wrapping" pattern for HTTPX composition.

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = RetryTransport(base, max_retries=3)
        client = httpx.AsyncClient(transport=transport)
    """

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        max_retries: Optional[int] = None,
        config: Optional[RetryConfig] = None,
        respect_retry_after: bool = True,
        on_retry: Optional[Callable[[Exception, int, float], None]] = None,
        on_success: Optional[Callable[[int, float], None]] = None,
    ) -> None:
        """
        Create a new RetryTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            max_retries: Maximum retries (simple config)
            config: Custom retry config (alternative to max_retries)
            respect_retry_after: Whether to respect Retry-After headers. Default: True
            on_retry: Callback before each retry attempt
            on_success: Callback on success
        """
        self._inner = inner
        self._respect_retry_after = respect_retry_after
        self._on_retry = on_retry
        self._on_success = on_success

        # Build retry config
        if config:
            self._config = config
        elif max_retries is not None:
            self._config = RetryConfig(max_retries=max_retries)
        else:
            self._config = merge_config(None)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async HTTP request with retry logic"""

        # Check if this method should be retried
        if not is_retryable_method(request.method, self._config):
            return await self._inner.handle_async_request(request)

        max_retries = self._config.max_retries
        attempt = 0
        start_time = time.monotonic()
        last_error: Optional[Exception] = None

        while attempt <= max_retries:
            try:
                response = await self._inner.handle_async_request(request)

                # Check if we should retry based on status code
                if is_retryable_status(response.status_code, self._config) and attempt < max_retries:
                    # Get retry delay
                    if self._respect_retry_after and response.status_code == 429:
                        retry_after = response.headers.get("retry-after")
                        delay = parse_retry_after(retry_after) if retry_after else 0
                        if delay == 0:
                            delay = calculate_backoff_delay(attempt, self._config)
                    else:
                        delay = calculate_backoff_delay(attempt, self._config)

                    if self._on_retry:
                        error = Exception(f"HTTP {response.status_code}")
                        self._on_retry(error, attempt + 1, delay)

                    await asyncio.sleep(delay)
                    attempt += 1
                    continue

                # Success
                if self._on_success:
                    self._on_success(attempt, time.monotonic() - start_time)

                return response

            except Exception as error:
                last_error = error

                # Check if we should retry this error
                should_retry = self._should_retry_error(error, attempt, max_retries)

                if not should_retry:
                    raise error

                # Calculate delay
                delay = calculate_backoff_delay(attempt, self._config)

                if self._on_retry:
                    self._on_retry(error, attempt + 1, delay)

                await asyncio.sleep(delay)
                attempt += 1

        # Exhausted retries
        if last_error:
            raise last_error
        raise RuntimeError("Retry failed")

    def _should_retry_error(
        self,
        error: Exception,
        attempt: int,
        max_retries: int,
    ) -> bool:
        """Determine if we should retry after an error."""
        if attempt >= max_retries:
            return False

        # Check for network-related errors
        error_type = type(error).__name__
        if error_type in self._config.retry_on_errors:
            return True

        # Check error message
        message = str(error).lower()
        retryable_patterns = [
            "network",
            "timeout",
            "connection",
            "socket",
            "refused",
            "reset",
        ]

        return any(pattern in message for pattern in retryable_patterns)

    async def aclose(self) -> None:
        """Close the transport"""
        await self._inner.aclose()


class SyncRetryTransport(httpx.BaseTransport):
    """
    Synchronous retry transport wrapper for httpx.

    Note: Uses time.sleep for delays in sync context.
    For async applications, use RetryTransport instead.
    """

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        max_retries: Optional[int] = None,
        config: Optional[RetryConfig] = None,
        respect_retry_after: bool = True,
        on_retry: Optional[Callable[[Exception, int, float], None]] = None,
        on_success: Optional[Callable[[int, float], None]] = None,
    ) -> None:
        """
        Create a new SyncRetryTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            max_retries: Maximum retries (simple config)
            config: Custom retry config (alternative to max_retries)
            respect_retry_after: Whether to respect Retry-After headers. Default: True
            on_retry: Callback before each retry attempt
            on_success: Callback on success
        """
        self._inner = inner
        self._respect_retry_after = respect_retry_after
        self._on_retry = on_retry
        self._on_success = on_success

        # Build retry config
        if config:
            self._config = config
        elif max_retries is not None:
            self._config = RetryConfig(max_retries=max_retries)
        else:
            self._config = merge_config(None)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a sync HTTP request with retry logic"""

        # Check if this method should be retried
        if not is_retryable_method(request.method, self._config):
            return self._inner.handle_request(request)

        max_retries = self._config.max_retries
        attempt = 0
        start_time = time.monotonic()
        last_error: Optional[Exception] = None

        while attempt <= max_retries:
            try:
                response = self._inner.handle_request(request)

                # Check if we should retry based on status code
                if is_retryable_status(response.status_code, self._config) and attempt < max_retries:
                    # Get retry delay
                    if self._respect_retry_after and response.status_code == 429:
                        retry_after = response.headers.get("retry-after")
                        delay = parse_retry_after(retry_after) if retry_after else 0
                        if delay == 0:
                            delay = calculate_backoff_delay(attempt, self._config)
                    else:
                        delay = calculate_backoff_delay(attempt, self._config)

                    if self._on_retry:
                        error = Exception(f"HTTP {response.status_code}")
                        self._on_retry(error, attempt + 1, delay)

                    time.sleep(delay)
                    attempt += 1
                    continue

                # Success
                if self._on_success:
                    self._on_success(attempt, time.monotonic() - start_time)

                return response

            except Exception as error:
                last_error = error

                # Check if we should retry this error
                should_retry = self._should_retry_error(error, attempt, max_retries)

                if not should_retry:
                    raise error

                # Calculate delay
                delay = calculate_backoff_delay(attempt, self._config)

                if self._on_retry:
                    self._on_retry(error, attempt + 1, delay)

                time.sleep(delay)
                attempt += 1

        # Exhausted retries
        if last_error:
            raise last_error
        raise RuntimeError("Retry failed")

    def _should_retry_error(
        self,
        error: Exception,
        attempt: int,
        max_retries: int,
    ) -> bool:
        """Determine if we should retry after an error."""
        if attempt >= max_retries:
            return False

        # Check for network-related errors
        error_type = type(error).__name__
        if error_type in self._config.retry_on_errors:
            return True

        # Check error message
        message = str(error).lower()
        retryable_patterns = [
            "network",
            "timeout",
            "connection",
            "socket",
            "refused",
            "reset",
        ]

        return any(pattern in message for pattern in retryable_patterns)

    def close(self) -> None:
        """Close the transport"""
        self._inner.close()
