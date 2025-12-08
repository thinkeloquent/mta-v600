"""
Tests for fetch_retry executor.

Test coverage includes:
- Statement coverage: All executable statements
- Decision/Branch coverage: All boolean decisions (if/else)
- Loop testing: Zero iterations, one iteration, many iterations
- Path coverage: Success paths, retry paths, failure paths
- State transition testing: Attempt states and transitions
"""

import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock

from fetch_retry.executor import (
    RetryExecutor,
    create_retry_executor,
    retry,
    retry_sync,
    create_retry_wrapper,
)
from fetch_retry.types import RetryConfig, RetryOptions, RetryEvent


class TestRetryExecutor:
    """Tests for RetryExecutor class."""

    class TestConstructor:
        """Tests for constructor."""

        def test_creates_executor_with_default_config(self):
            """Should create executor with default config."""
            executor = RetryExecutor()
            assert executor.config.max_retries == 3
            assert executor.config.base_delay_seconds == 1.0

        def test_creates_executor_with_custom_config(self):
            """Should create executor with custom config."""
            config = RetryConfig(max_retries=5, base_delay_seconds=0.5)
            executor = RetryExecutor(config)
            assert executor.config.max_retries == 5
            assert executor.config.base_delay_seconds == 0.5

        def test_generates_unique_id_if_not_provided(self):
            """Should generate unique ID if not provided."""
            executor = RetryExecutor()
            assert executor.id.startswith("retry-")

        def test_uses_provided_id(self):
            """Should use provided ID."""
            executor = RetryExecutor(executor_id="custom-id")
            assert executor.id == "custom-id"

    class TestExecuteAsync:
        """Tests for async execute method."""

        @pytest.mark.asyncio
        async def test_returns_result_on_immediate_success(self):
            """Should return result on immediate success."""
            executor = RetryExecutor()

            async def success_fn():
                return "success"

            result = await executor.execute(success_fn)

            assert result.result == "success"
            assert result.retries == 0
            assert result.total_time_seconds >= 0
            assert result.delay_time_seconds == 0

        @pytest.mark.asyncio
        async def test_retries_on_retryable_error(self):
            """Should retry on retryable error."""
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            call_count = 0

            async def failing_then_success():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ConnectionError("connection error")
                return "success"

            result = await executor.execute(failing_then_success)

            assert result.result == "success"
            assert result.retries == 1
            assert call_count == 2

        @pytest.mark.asyncio
        async def test_retries_multiple_times(self):
            """Should retry multiple times."""
            config = RetryConfig(max_retries=5, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            call_count = 0

            async def failing_multiple_times():
                nonlocal call_count
                call_count += 1
                if call_count < 4:
                    raise ConnectionError(f"error {call_count}")
                return "success"

            result = await executor.execute(failing_multiple_times)

            assert result.result == "success"
            assert result.retries == 3
            assert call_count == 4

        @pytest.mark.asyncio
        async def test_tracks_delay_time_across_retries(self):
            """Should track delay time across retries."""
            config = RetryConfig(max_retries=3, base_delay_seconds=0.05, jitter_factor=0)
            executor = RetryExecutor(config)
            call_count = 0

            async def failing_once():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ConnectionError("error")
                return "success"

            result = await executor.execute(failing_once)

            assert result.delay_time_seconds > 0

        @pytest.mark.asyncio
        async def test_throws_after_exhausting_retries(self):
            """Should throw after exhausting retries."""
            config = RetryConfig(max_retries=2, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            call_count = 0

            async def always_fails():
                nonlocal call_count
                call_count += 1
                raise ConnectionError("network error")

            with pytest.raises(ConnectionError, match="network error"):
                await executor.execute(always_fails)

            assert call_count == 3  # initial + 2 retries

        @pytest.mark.asyncio
        async def test_throws_immediately_for_non_retryable_errors(self):
            """Should throw immediately for non-retryable errors."""
            config = RetryConfig(max_retries=3)
            executor = RetryExecutor(config)
            call_count = 0

            async def validation_error():
                nonlocal call_count
                call_count += 1
                raise ValueError("validation error")

            with pytest.raises(ValueError, match="validation error"):
                await executor.execute(validation_error)

            assert call_count == 1

        @pytest.mark.asyncio
        async def test_uses_custom_should_retry_predicate(self):
            """Should use custom should_retry predicate."""
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)

            def custom_should_retry(error, attempt):
                return False

            async def network_error():
                raise ConnectionError("network error")

            options = RetryOptions(should_retry=custom_should_retry)

            with pytest.raises(ConnectionError):
                await executor.execute(network_error, options)

        @pytest.mark.asyncio
        async def test_retries_when_custom_should_retry_returns_true(self):
            """Should retry when custom should_retry returns True."""
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            call_count = 0

            def custom_should_retry(error, attempt):
                return True

            async def custom_error_then_success():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ValueError("custom error")
                return "success"

            options = RetryOptions(should_retry=custom_should_retry)
            result = await executor.execute(custom_error_then_success, options)

            assert result.result == "success"
            assert call_count == 2

        @pytest.mark.asyncio
        async def test_uses_max_retries_from_options(self):
            """Should use maxRetries from options."""
            config = RetryConfig(max_retries=1, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            call_count = 0

            async def always_fails():
                nonlocal call_count
                call_count += 1
                raise ConnectionError("network error")

            options = RetryOptions(max_retries=5)

            with pytest.raises(ConnectionError):
                await executor.execute(always_fails, options)

            assert call_count == 6  # initial + 5 overridden retries

    class TestExecuteSync:
        """Tests for sync execute_sync method."""

        def test_returns_result_on_immediate_success(self):
            """Should return result on immediate success."""
            executor = RetryExecutor()

            def success_fn():
                return "success"

            result = executor.execute_sync(success_fn)

            assert result.result == "success"
            assert result.retries == 0

        def test_retries_on_retryable_error(self):
            """Should retry on retryable error."""
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            call_count = 0

            def failing_then_success():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ConnectionError("connection error")
                return "success"

            result = executor.execute_sync(failing_then_success)

            assert result.result == "success"
            assert result.retries == 1

        def test_throws_after_exhausting_retries(self):
            """Should throw after exhausting retries."""
            config = RetryConfig(max_retries=2, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            call_count = 0

            def always_fails():
                nonlocal call_count
                call_count += 1
                raise ConnectionError("network error")

            with pytest.raises(ConnectionError):
                executor.execute_sync(always_fails)

            assert call_count == 3

    class TestEventEmission:
        """Tests for event emission."""

        @pytest.mark.asyncio
        async def test_emits_attempt_start_event(self):
            """Should emit attempt:start event."""
            executor = RetryExecutor()
            events = []
            executor.on(lambda e: events.append(e))

            async def success_fn():
                return "success"

            await executor.execute(success_fn)

            start_events = [e for e in events if e.type == "attempt:start"]
            assert len(start_events) >= 1
            assert start_events[0].attempt == 0

        @pytest.mark.asyncio
        async def test_emits_attempt_success_event(self):
            """Should emit attempt:success event."""
            executor = RetryExecutor()
            events = []
            executor.on(lambda e: events.append(e))

            async def success_fn():
                return "success"

            await executor.execute(success_fn)

            success_events = [e for e in events if e.type == "attempt:success"]
            assert len(success_events) == 1
            assert success_events[0].attempt == 0
            assert "duration_seconds" in success_events[0].data

        @pytest.mark.asyncio
        async def test_emits_attempt_fail_event(self):
            """Should emit attempt:fail event."""
            config = RetryConfig(max_retries=1, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            events = []
            executor.on(lambda e: events.append(e))

            async def validation_error():
                raise ValueError("validation error")

            with pytest.raises(ValueError):
                await executor.execute(validation_error)

            fail_events = [e for e in events if e.type == "attempt:fail"]
            assert len(fail_events) >= 1
            assert fail_events[0].data["will_retry"] is False

        @pytest.mark.asyncio
        async def test_emits_retry_wait_event(self):
            """Should emit retry:wait event."""
            config = RetryConfig(max_retries=2, base_delay_seconds=0.01, jitter_factor=0)
            executor = RetryExecutor(config)
            events = []
            executor.on(lambda e: events.append(e))
            call_count = 0

            async def failing_once():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ConnectionError("error")
                return "success"

            await executor.execute(failing_once)

            wait_events = [e for e in events if e.type == "retry:wait"]
            assert len(wait_events) == 1
            assert "delay_seconds" in wait_events[0].data

        @pytest.mark.asyncio
        async def test_includes_metadata_in_events(self):
            """Should include metadata in events."""
            executor = RetryExecutor()
            events = []
            executor.on(lambda e: events.append(e))

            async def success_fn():
                return "success"

            metadata = {"request_id": "123"}
            options = RetryOptions(metadata=metadata)
            await executor.execute(success_fn, options)

            assert events[0].data.get("metadata") == metadata

        @pytest.mark.asyncio
        async def test_ignores_listener_errors(self):
            """Should ignore listener errors."""
            executor = RetryExecutor()

            def failing_listener(event):
                raise RuntimeError("Listener error")

            executor.on(failing_listener)

            async def success_fn():
                return "success"

            result = await executor.execute(success_fn)
            assert result.result == "success"

    class TestEventListenerManagement:
        """Tests for event listener management."""

        @pytest.mark.asyncio
        async def test_adds_listener_with_on(self):
            """Should add listener with on()."""
            executor = RetryExecutor()
            events = []
            executor.on(lambda e: events.append(e))

            async def success_fn():
                return "success"

            await executor.execute(success_fn)

            assert len(events) > 0

        @pytest.mark.asyncio
        async def test_returns_unsubscribe_function_from_on(self):
            """Should return unsubscribe function from on()."""
            executor = RetryExecutor()
            events = []
            unsubscribe = executor.on(lambda e: events.append(e))

            unsubscribe()

            async def success_fn():
                return "success"

            await executor.execute(success_fn)

            assert len(events) == 0

        @pytest.mark.asyncio
        async def test_removes_listener_with_off(self):
            """Should remove listener with off()."""
            executor = RetryExecutor()
            events = []
            listener = lambda e: events.append(e)
            executor.on(listener)
            executor.off(listener)

            async def success_fn():
                return "success"

            await executor.execute(success_fn)

            assert len(events) == 0


class TestCreateRetryExecutor:
    """Tests for create_retry_executor function."""

    def test_creates_executor_with_config(self):
        """Should create executor with config."""
        config = RetryConfig(max_retries=5)
        executor = create_retry_executor(config)
        assert executor.config.max_retries == 5

    def test_creates_executor_without_config(self):
        """Should create executor without config."""
        executor = create_retry_executor()
        assert executor.config.max_retries == 3


class TestRetryConvenienceFunction:
    """Tests for retry convenience function."""

    @pytest.mark.asyncio
    async def test_retries_function_with_config(self):
        """Should retry function with config."""
        config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
        call_count = 0

        async def failing_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("error")
            return "success"

        result = await retry(failing_once, config)

        assert result.result == "success"
        assert result.retries == 1

    @pytest.mark.asyncio
    async def test_works_without_config(self):
        """Should work without config."""

        async def success_fn():
            return "success"

        result = await retry(success_fn)

        assert result.result == "success"


class TestRetrySyncConvenienceFunction:
    """Tests for retry_sync convenience function."""

    def test_retries_function_with_config(self):
        """Should retry function with config."""
        config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
        call_count = 0

        def failing_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("error")
            return "success"

        result = retry_sync(failing_once, config)

        assert result.result == "success"
        assert result.retries == 1


class TestCreateRetryWrapper:
    """Tests for create_retry_wrapper function."""

    @pytest.mark.asyncio
    async def test_creates_reusable_wrapper(self):
        """Should create reusable wrapper."""
        config = RetryConfig(max_retries=2, base_delay_seconds=0.01, jitter_factor=0)
        with_retry = create_retry_wrapper(config)

        async def fn1():
            return "result1"

        async def fn2():
            return "result2"

        result1 = await with_retry(fn1)
        result2 = await with_retry(fn2)

        assert result1.result == "result1"
        assert result2.result == "result2"

    @pytest.mark.asyncio
    async def test_accepts_per_call_options(self):
        """Should accept per-call options."""
        config = RetryConfig(max_retries=1, base_delay_seconds=0.01, jitter_factor=0)
        with_retry = create_retry_wrapper(config)
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("error")

        options = RetryOptions(max_retries=3)

        with pytest.raises(ConnectionError):
            await with_retry(always_fails, options)

        assert call_count == 4  # initial + 3 overridden retries


class TestEdgeCasesAndBoundaryConditions:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        """Should not retry when max_retries is 0."""
        config = RetryConfig(max_retries=0)
        executor = RetryExecutor(config)
        call_count = 0

        async def network_error():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("error")

        with pytest.raises(ConnectionError):
            await executor.execute(network_error)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_single_retry(self):
        """Should retry exactly once when max_retries is 1."""
        config = RetryConfig(max_retries=1, base_delay_seconds=0.01, jitter_factor=0)
        executor = RetryExecutor(config)
        call_count = 0

        async def network_error():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("error")

        with pytest.raises(ConnectionError):
            await executor.execute(network_error)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_concurrent_executions(self):
        """Should handle multiple concurrent executions independently."""
        import asyncio

        config = RetryConfig(max_retries=2, base_delay_seconds=0.01, jitter_factor=0)
        executor = RetryExecutor(config)

        async def fn1():
            return "result1"

        async def fn2():
            return "result2"

        result1, result2 = await asyncio.gather(
            executor.execute(fn1),
            executor.execute(fn2),
        )

        assert result1.result == "result1"
        assert result2.result == "result2"
