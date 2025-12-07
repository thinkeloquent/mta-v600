"""
Main retry executor implementation
"""
import time
from typing import TypeVar, Callable, Awaitable, Optional

from .types import (
    RetryConfig,
    RetryOptions,
    RetryResult,
    RetryEvent,
    RetryEventListener,
)
from .config import (
    merge_config,
    calculate_backoff_delay,
    is_retryable_error,
    async_sleep,
    sync_sleep,
)


T = TypeVar("T")


class RetryExecutor:
    """
    Retry Executor

    Provides retry logic with:
    - Configurable max retries
    - Exponential backoff with jitter
    - Error filtering
    - Event emission for observability
    """

    def __init__(self, config: Optional[RetryConfig] = None, executor_id: Optional[str] = None):
        """
        Create a new RetryExecutor.

        Args:
            config: Retry configuration
            executor_id: Optional unique identifier
        """
        self._config = merge_config(config)
        self._id = executor_id or f"retry-{int(time.time() * 1000)}"
        self._listeners: list[RetryEventListener] = []

    def _emit(self, event: RetryEvent) -> None:
        """Emit an event to all listeners."""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass  # Ignore listener errors

    async def execute(
        self,
        fn: Callable[[], Awaitable[T]],
        options: Optional[RetryOptions] = None,
    ) -> RetryResult[T]:
        """
        Execute a function with retry logic.

        Args:
            fn: Async function to execute
            options: Retry options for this execution

        Returns:
            Result with retry metadata

        Example:
            executor = RetryExecutor(RetryConfig(max_retries=3))
            result = await executor.execute(async_fetch_data)
        """
        opts = options or RetryOptions()
        max_retries = opts.max_retries if opts.max_retries is not None else self._config.max_retries

        start_time = time.monotonic()
        delay_time = 0.0
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= max_retries:
            self._emit(RetryEvent(
                type="attempt:start",
                attempt=attempt,
                data={"metadata": opts.metadata} if opts.metadata else {},
            ))

            attempt_start = time.monotonic()

            try:
                result = await fn()
                duration = time.monotonic() - attempt_start

                self._emit(RetryEvent(
                    type="attempt:success",
                    attempt=attempt,
                    data={
                        "duration_seconds": duration,
                        "metadata": opts.metadata,
                    },
                ))

                return RetryResult(
                    result=result,
                    retries=attempt,
                    total_time_seconds=time.monotonic() - start_time,
                    delay_time_seconds=delay_time,
                )
            except Exception as error:
                last_error = error
                will_retry = self._should_retry_attempt(
                    error, attempt, max_retries, opts.should_retry
                )

                self._emit(RetryEvent(
                    type="attempt:fail",
                    attempt=attempt,
                    data={
                        "error": str(error),
                        "will_retry": will_retry,
                        "metadata": opts.metadata,
                    },
                ))

                if not will_retry:
                    raise error

                # Calculate and apply backoff delay
                delay = calculate_backoff_delay(attempt, self._config)
                delay_time += delay

                self._emit(RetryEvent(
                    type="retry:wait",
                    attempt=attempt,
                    data={
                        "delay_seconds": delay,
                        "metadata": opts.metadata,
                    },
                ))

                await async_sleep(delay)
                attempt += 1

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise RuntimeError("Retry failed")

    def execute_sync(
        self,
        fn: Callable[[], T],
        options: Optional[RetryOptions] = None,
    ) -> RetryResult[T]:
        """
        Execute a synchronous function with retry logic.

        Args:
            fn: Sync function to execute
            options: Retry options for this execution

        Returns:
            Result with retry metadata
        """
        opts = options or RetryOptions()
        max_retries = opts.max_retries if opts.max_retries is not None else self._config.max_retries

        start_time = time.monotonic()
        delay_time = 0.0
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= max_retries:
            self._emit(RetryEvent(
                type="attempt:start",
                attempt=attempt,
                data={"metadata": opts.metadata} if opts.metadata else {},
            ))

            attempt_start = time.monotonic()

            try:
                result = fn()
                duration = time.monotonic() - attempt_start

                self._emit(RetryEvent(
                    type="attempt:success",
                    attempt=attempt,
                    data={
                        "duration_seconds": duration,
                        "metadata": opts.metadata,
                    },
                ))

                return RetryResult(
                    result=result,
                    retries=attempt,
                    total_time_seconds=time.monotonic() - start_time,
                    delay_time_seconds=delay_time,
                )
            except Exception as error:
                last_error = error
                will_retry = self._should_retry_attempt(
                    error, attempt, max_retries, opts.should_retry
                )

                self._emit(RetryEvent(
                    type="attempt:fail",
                    attempt=attempt,
                    data={
                        "error": str(error),
                        "will_retry": will_retry,
                        "metadata": opts.metadata,
                    },
                ))

                if not will_retry:
                    raise error

                # Calculate and apply backoff delay
                delay = calculate_backoff_delay(attempt, self._config)
                delay_time += delay

                self._emit(RetryEvent(
                    type="retry:wait",
                    attempt=attempt,
                    data={
                        "delay_seconds": delay,
                        "metadata": opts.metadata,
                    },
                ))

                sync_sleep(delay)
                attempt += 1

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise RuntimeError("Retry failed")

    def _should_retry_attempt(
        self,
        error: Exception,
        attempt: int,
        max_retries: int,
        custom_should_retry: Optional[Callable[[Exception, int], bool]] = None,
    ) -> bool:
        """Determine if we should retry after a failure."""
        # Check if we've exhausted retries
        if attempt >= max_retries:
            return False

        # Check custom predicate first
        if custom_should_retry is not None:
            try:
                return custom_should_retry(error, attempt)
            except Exception:
                pass  # Fall through to default

        # Check if error is retryable
        return is_retryable_error(error, self._config)

    def on(self, listener: RetryEventListener) -> Callable[[], None]:
        """
        Add an event listener.

        Args:
            listener: Event listener function

        Returns:
            Function to remove the listener
        """
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener) if listener in self._listeners else None

    def off(self, listener: RetryEventListener) -> None:
        """Remove an event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    @property
    def id(self) -> str:
        """Get the executor ID."""
        return self._id

    @property
    def config(self) -> RetryConfig:
        """Get the current configuration."""
        return self._config


def create_retry_executor(
    config: Optional[RetryConfig] = None,
    executor_id: Optional[str] = None,
) -> RetryExecutor:
    """Create a new retry executor."""
    return RetryExecutor(config, executor_id)


async def retry(
    fn: Callable[[], Awaitable[T]],
    config: Optional[RetryConfig] = None,
    options: Optional[RetryOptions] = None,
) -> RetryResult[T]:
    """
    Execute a function with retry logic (convenience function).

    Args:
        fn: Async function to execute
        config: Retry configuration
        options: Retry options

    Returns:
        Result with retry metadata

    Example:
        result = await retry(
            async_fetch_data,
            RetryConfig(max_retries=3),
        )
    """
    executor = RetryExecutor(config)
    return await executor.execute(fn, options)


def retry_sync(
    fn: Callable[[], T],
    config: Optional[RetryConfig] = None,
    options: Optional[RetryOptions] = None,
) -> RetryResult[T]:
    """
    Execute a sync function with retry logic (convenience function).

    Args:
        fn: Sync function to execute
        config: Retry configuration
        options: Retry options

    Returns:
        Result with retry metadata
    """
    executor = RetryExecutor(config)
    return executor.execute_sync(fn, options)


def create_retry_wrapper(
    config: Optional[RetryConfig] = None,
) -> Callable[[Callable[[], Awaitable[T]], Optional[RetryOptions]], Awaitable[RetryResult[T]]]:
    """
    Create a retry wrapper function.

    Args:
        config: Retry configuration

    Returns:
        Function that wraps operations with retry logic

    Example:
        with_retry = create_retry_wrapper(RetryConfig(max_retries=3))
        result = await with_retry(async_fetch_data)
    """
    executor = RetryExecutor(config)

    async def wrapper(
        fn: Callable[[], Awaitable[T]],
        options: Optional[RetryOptions] = None,
    ) -> RetryResult[T]:
        return await executor.execute(fn, options)

    return wrapper
