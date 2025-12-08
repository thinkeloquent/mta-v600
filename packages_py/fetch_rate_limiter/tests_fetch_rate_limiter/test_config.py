"""
Tests for config utilities

Coverage includes:
- calculate_backoff_delay with various inputs
- is_retryable_error with different error types
- is_retryable_status with various status codes
- merge_config with partial configs
- generate_request_id uniqueness
"""

import pytest
import asyncio
from unittest.mock import patch
from fetch_rate_limiter.config import (
    calculate_backoff_delay,
    is_retryable_error,
    is_retryable_status,
    merge_config,
    generate_request_id,
    async_sleep,
    sync_sleep,
    DEFAULT_RETRY_CONFIG,
)
from fetch_rate_limiter.types import RetryConfig, RateLimiterConfig, StaticRateLimitConfig


class TestCalculateBackoffDelay:
    """Tests for calculate_backoff_delay function."""

    def test_return_base_delay_for_attempt_0_no_jitter(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.0,
        )
        delay = calculate_backoff_delay(0, config)
        assert delay == 1.0

    def test_double_delay_for_each_attempt_exponential(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.0,
        )

        delays = [calculate_backoff_delay(i, config) for i in range(4)]

        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
        assert delays[3] == 8.0

    def test_cap_delay_at_max_delay(self):
        config = RetryConfig(
            max_retries=10,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.0,
        )
        delay = calculate_backoff_delay(10, config)
        assert delay == 30.0

    def test_apply_jitter_within_expected_range(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.5,
        )

        samples = [calculate_backoff_delay(0, config) for _ in range(100)]

        min_delay = min(samples)
        max_delay = max(samples)

        assert min_delay >= 0.5
        assert max_delay <= 1.5

    def test_handle_edge_case_attempt_0(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.0,
        )
        delay = calculate_backoff_delay(0, config)
        assert delay == 1.0

    def test_handle_edge_case_very_large_attempt(self):
        config = RetryConfig(
            max_retries=100,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.0,
        )
        delay = calculate_backoff_delay(100, config)
        assert delay == 30.0

    def test_never_return_negative_delay(self):
        for i in range(100):
            delay = calculate_backoff_delay(i, DEFAULT_RETRY_CONFIG)
            assert delay >= 0


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_return_true_for_matching_error_type(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.5,
            retry_on_errors=["ConnectionError", "TimeoutError"],
        )
        error = ConnectionError("Connection reset")
        assert is_retryable_error(error, config) is True

    def test_return_false_for_nonmatching_error(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.5,
            retry_on_errors=["ConnectionError", "TimeoutError"],
        )
        error = ValueError("Invalid value")
        assert is_retryable_error(error, config) is False

    def test_return_true_for_network_related_messages(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.5,
            retry_on_errors=[],
        )
        network_errors = [
            Exception("Network failure"),
            Exception("Request timeout"),
            Exception("Connection refused"),
            Exception("Socket error"),
        ]

        for error in network_errors:
            assert is_retryable_error(error, config) is True

    def test_return_false_for_nonretryable_errors(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.5,
            retry_on_errors=[],
        )
        error = Exception("Invalid JSON")
        assert is_retryable_error(error, config) is False


class TestIsRetryableStatus:
    """Tests for is_retryable_status function."""

    def test_return_true_for_retryable_status_codes(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.5,
            retry_on_status=[429, 500, 502, 503, 504],
        )

        assert is_retryable_status(429, config) is True
        assert is_retryable_status(500, config) is True
        assert is_retryable_status(502, config) is True
        assert is_retryable_status(503, config) is True
        assert is_retryable_status(504, config) is True

    def test_return_false_for_nonretryable_status_codes(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.5,
            retry_on_status=[429, 500, 502, 503, 504],
        )

        assert is_retryable_status(200, config) is False
        assert is_retryable_status(201, config) is False
        assert is_retryable_status(400, config) is False
        assert is_retryable_status(401, config) is False
        assert is_retryable_status(403, config) is False
        assert is_retryable_status(404, config) is False

    def test_handle_boundary_status_codes(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0.5,
            retry_on_status=[429, 500, 502, 503, 504],
        )

        assert is_retryable_status(0, config) is False
        assert is_retryable_status(-1, config) is False
        assert is_retryable_status(999, config) is False


class TestMergeConfig:
    """Tests for merge_config function."""

    def test_merge_with_defaults(self):
        config = RateLimiterConfig(
            id="test",
            static=StaticRateLimitConfig(max_requests=100, interval_seconds=1.0),
        )

        merged = merge_config(config)

        assert merged.id == "test"
        assert merged.retry is not None
        assert merged.retry.max_retries == DEFAULT_RETRY_CONFIG.max_retries

    def test_preserve_user_provided_values(self):
        config = RateLimiterConfig(
            id="test",
            max_queue_size=50,
            concurrency=5,
            static=StaticRateLimitConfig(max_requests=10, interval_seconds=1.0),
        )

        merged = merge_config(config)

        assert merged.max_queue_size == 50
        assert merged.concurrency == 5

    def test_merge_retry_config_with_defaults(self):
        config = RateLimiterConfig(
            id="test",
            retry=RetryConfig(
                max_retries=5,
                base_delay_seconds=2.0,
                max_delay_seconds=60.0,
                jitter_factor=0.3,
            ),
        )

        merged = merge_config(config)

        assert merged.retry.max_retries == 5
        assert merged.retry.base_delay_seconds == 2.0

    def test_handle_empty_config(self):
        config = RateLimiterConfig(id="test")
        merged = merge_config(config)

        assert merged.id == "test"
        assert merged.retry == DEFAULT_RETRY_CONFIG


class TestGenerateRequestId:
    """Tests for generate_request_id function."""

    def test_generate_unique_ids(self):
        ids = set()
        for _ in range(1000):
            ids.add(generate_request_id())
        assert len(ids) == 1000

    def test_start_with_req_prefix(self):
        request_id = generate_request_id()
        assert request_id.startswith("req_")

    def test_contain_timestamp_and_random_component(self):
        request_id = generate_request_id()
        parts = request_id.split("_")
        assert len(parts) >= 2
        assert parts[0] == "req"

    def test_generate_ids_of_consistent_length(self):
        ids = [generate_request_id() for _ in range(100)]
        lengths = set(len(id) for id in ids)

        # All IDs should be roughly the same length (±2 chars)
        assert len(lengths) <= 3


class TestAsyncSleep:
    """Tests for async_sleep function."""

    @pytest.mark.asyncio
    async def test_sleep_for_specified_duration(self):
        import time

        start = time.time()
        await async_sleep(0.1)
        elapsed = time.time() - start

        assert elapsed >= 0.09
        assert elapsed < 0.2

    @pytest.mark.asyncio
    async def test_handle_zero_delay(self):
        await async_sleep(0)


class TestSyncSleep:
    """Tests for sync_sleep function."""

    def test_sleep_for_specified_duration(self):
        import time

        start = time.time()
        sync_sleep(0.1)
        elapsed = time.time() - start

        assert elapsed >= 0.09
        assert elapsed < 0.2


class TestDefaultRetryConfig:
    """Tests for DEFAULT_RETRY_CONFIG."""

    def test_has_sensible_defaults(self):
        assert DEFAULT_RETRY_CONFIG.max_retries == 3
        assert DEFAULT_RETRY_CONFIG.base_delay_seconds == 1.0
        assert DEFAULT_RETRY_CONFIG.max_delay_seconds == 30.0
        assert DEFAULT_RETRY_CONFIG.jitter_factor == 0.5
        assert "ConnectionError" in DEFAULT_RETRY_CONFIG.retry_on_errors
        assert 429 in DEFAULT_RETRY_CONFIG.retry_on_status
