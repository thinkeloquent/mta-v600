"""
Tests for fetch_retry configuration utilities.

Test coverage includes:
- Statement coverage: All executable statements
- Decision/Branch coverage: All boolean decisions (if/else, switch)
- Condition coverage: All individual conditions in compound expressions
- Boundary value testing: Edge cases and limits
- Equivalence partitioning: Representative values from each class
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from email.utils import format_datetime
from datetime import datetime, timezone

from fetch_retry.config import (
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
from fetch_retry.types import RetryConfig, BackoffStrategy


class TestDefaultRetryConfig:
    """Tests for DEFAULT_RETRY_CONFIG."""

    def test_has_expected_default_values(self):
        """Should have expected default values."""
        assert DEFAULT_RETRY_CONFIG.max_retries == 3
        assert DEFAULT_RETRY_CONFIG.base_delay_seconds == 1.0
        assert DEFAULT_RETRY_CONFIG.max_delay_seconds == 30.0
        assert DEFAULT_RETRY_CONFIG.jitter_factor == 0.5
        assert DEFAULT_RETRY_CONFIG.respect_retry_after is True

    def test_includes_standard_retryable_error_types(self):
        """Should include standard retryable error types."""
        assert "ConnectionError" in DEFAULT_RETRY_CONFIG.retry_on_errors
        assert "TimeoutError" in DEFAULT_RETRY_CONFIG.retry_on_errors
        assert "OSError" in DEFAULT_RETRY_CONFIG.retry_on_errors

    def test_includes_standard_retryable_status_codes(self):
        """Should include standard retryable status codes."""
        assert DEFAULT_RETRY_CONFIG.retry_on_status == [429, 500, 502, 503, 504]

    def test_includes_idempotent_http_methods(self):
        """Should include idempotent HTTP methods."""
        assert DEFAULT_RETRY_CONFIG.retry_methods == ["GET", "HEAD", "OPTIONS", "PUT", "DELETE"]


class TestCalculateBackoffDelay:
    """Tests for calculate_backoff_delay function."""

    @patch('random.random', return_value=0.5)
    def test_calculates_base_delay_for_attempt_0(self, mock_random):
        """Should calculate base delay for attempt 0."""
        config = RetryConfig(base_delay_seconds=1.0, max_delay_seconds=30.0, jitter_factor=0)
        delay = calculate_backoff_delay(0, config)
        assert delay == 1.0  # base * 2^0 = 1.0

    @patch('random.random', return_value=0.5)
    def test_doubles_delay_for_each_attempt(self, mock_random):
        """Should double delay for each attempt."""
        config = RetryConfig(base_delay_seconds=1.0, max_delay_seconds=30.0, jitter_factor=0)

        assert calculate_backoff_delay(0, config) == 1.0  # base * 2^0
        assert calculate_backoff_delay(1, config) == 2.0  # base * 2^1
        assert calculate_backoff_delay(2, config) == 4.0  # base * 2^2
        assert calculate_backoff_delay(3, config) == 8.0  # base * 2^3

    @patch('random.random', return_value=0.5)
    def test_caps_delay_at_max_delay(self, mock_random):
        """Should cap delay at max_delay_seconds."""
        config = RetryConfig(base_delay_seconds=1.0, max_delay_seconds=5.0, jitter_factor=0)
        delay = calculate_backoff_delay(10, config)  # 2^10 * 1 would be 1024
        assert delay == 5.0

    @patch('random.random', return_value=0.5)
    def test_applies_jitter_factor(self, mock_random):
        """Should apply jitter factor (full jitter strategy)."""
        config = RetryConfig(base_delay_seconds=1.0, max_delay_seconds=30.0, jitter_factor=0.5)
        delay = calculate_backoff_delay(0, config)
        # With random = 0.5 and jitterFactor = 0.5:
        # exponential_delay = 1.0
        # jitter = 0.5 * 0.5 * 1.0 = 0.25
        # delay = 1.0 * (1 - 0.5/2) + 0.25 = 1.0 * 0.75 + 0.25 = 1.0
        assert delay == 1.0

    @patch('random.random', return_value=0.999)
    def test_no_jitter_when_jitter_factor_is_zero(self, mock_random):
        """Should have no jitter when jitter_factor is 0."""
        config = RetryConfig(base_delay_seconds=1.0, max_delay_seconds=30.0, jitter_factor=0)
        delay = calculate_backoff_delay(0, config)
        assert delay == 1.0

    def test_handles_attempt_zero(self):
        """Should handle attempt 0."""
        delay = calculate_backoff_delay(0, DEFAULT_RETRY_CONFIG)
        assert delay > 0

    def test_handles_very_large_attempt_numbers(self):
        """Should handle very large attempt numbers."""
        delay = calculate_backoff_delay(100, DEFAULT_RETRY_CONFIG)
        assert delay <= DEFAULT_RETRY_CONFIG.max_delay_seconds

    def test_handles_zero_base_delay(self):
        """Should handle zero base_delay_seconds."""
        config = RetryConfig(base_delay_seconds=0, max_delay_seconds=1.0, jitter_factor=0.5)
        delay = calculate_backoff_delay(0, config)
        assert delay == 0


class TestCalculateDelay:
    """Tests for calculate_delay function (strategy-based)."""

    @patch('random.random', return_value=0.5)
    def test_exponential_strategy_default(self, mock_random):
        """Should use exponential backoff by default."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
        )
        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0

    @patch('random.random', return_value=0.5)
    def test_constant_strategy(self, mock_random):
        """Should return constant delay regardless of attempt."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0,
            backoff_strategy=BackoffStrategy.CONSTANT,
        )
        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 1.0
        assert calculate_delay(5, config) == 1.0

    @patch('random.random', return_value=0.5)
    def test_linear_strategy(self, mock_random):
        """Should increase delay linearly."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
            jitter_factor=0,
            backoff_strategy=BackoffStrategy.LINEAR,
            linear_increment_seconds=0.5,
        )
        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 1.5
        assert calculate_delay(2, config) == 2.0

    @patch('random.random', return_value=0.5)
    def test_linear_strategy_caps_at_max_delay(self, mock_random):
        """Should cap linear delay at max_delay_seconds."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=2.0,
            jitter_factor=0,
            backoff_strategy=BackoffStrategy.LINEAR,
            linear_increment_seconds=5.0,
        )
        assert calculate_delay(5, config) == 2.0


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_returns_true_for_connection_error(self):
        """Should return True for ConnectionError."""
        error = ConnectionError("Connection refused")
        assert is_retryable_error(error, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_timeout_error(self):
        """Should return True for TimeoutError."""
        error = TimeoutError("Request timed out")
        assert is_retryable_error(error, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_os_error(self):
        """Should return True for OSError."""
        error = OSError("Network unreachable")
        assert is_retryable_error(error, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_network_error_message(self):
        """Should return True for network-related error messages."""
        error = Exception("network error occurred")
        assert is_retryable_error(error, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_timeout_error_message(self):
        """Should return True for timeout error messages."""
        error = Exception("request timed out")
        assert is_retryable_error(error, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_connection_error_message(self):
        """Should return True for connection error messages."""
        error = Exception("connection failed")
        assert is_retryable_error(error, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_socket_error_message(self):
        """Should return True for socket error messages."""
        error = Exception("socket hang up")
        assert is_retryable_error(error, DEFAULT_RETRY_CONFIG) is True

    def test_is_case_insensitive(self):
        """Should be case-insensitive for error messages."""
        assert is_retryable_error(Exception("NETWORK ERROR"), DEFAULT_RETRY_CONFIG) is True
        assert is_retryable_error(Exception("Connection TIMEOUT"), DEFAULT_RETRY_CONFIG) is True

    def test_returns_false_for_non_retryable_messages(self):
        """Should return False for non-retryable messages."""
        error = Exception("validation error")
        assert is_retryable_error(error, DEFAULT_RETRY_CONFIG) is False

    def test_checks_error_cause_chain(self):
        """Should check error cause chain."""
        inner_error = ConnectionError("connection lost")
        outer_error = Exception("wrapper error")
        outer_error.__cause__ = inner_error
        assert is_retryable_error(outer_error, DEFAULT_RETRY_CONFIG) is True

    def test_recurses_through_nested_causes(self):
        """Should recurse through nested causes."""
        inner = Exception("network error")
        middle = Exception("middle")
        middle.__cause__ = inner
        outer = Exception("outer")
        outer.__cause__ = middle
        assert is_retryable_error(outer, DEFAULT_RETRY_CONFIG) is True

    def test_uses_custom_retry_on_errors_list(self):
        """Should use custom retry_on_errors list."""
        config = RetryConfig(retry_on_errors=["CustomError"])

        class CustomError(Exception):
            pass

        assert is_retryable_error(CustomError("test"), config) is True


class TestIsRetryableStatus:
    """Tests for is_retryable_status function."""

    def test_returns_true_for_429(self):
        """Should return True for 429 Too Many Requests."""
        assert is_retryable_status(429, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_500(self):
        """Should return True for 500 Internal Server Error."""
        assert is_retryable_status(500, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_502(self):
        """Should return True for 502 Bad Gateway."""
        assert is_retryable_status(502, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_503(self):
        """Should return True for 503 Service Unavailable."""
        assert is_retryable_status(503, DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_504(self):
        """Should return True for 504 Gateway Timeout."""
        assert is_retryable_status(504, DEFAULT_RETRY_CONFIG) is True

    def test_returns_false_for_200(self):
        """Should return False for 200 OK."""
        assert is_retryable_status(200, DEFAULT_RETRY_CONFIG) is False

    def test_returns_false_for_400(self):
        """Should return False for 400 Bad Request."""
        assert is_retryable_status(400, DEFAULT_RETRY_CONFIG) is False

    def test_returns_false_for_401(self):
        """Should return False for 401 Unauthorized."""
        assert is_retryable_status(401, DEFAULT_RETRY_CONFIG) is False

    def test_returns_false_for_403(self):
        """Should return False for 403 Forbidden."""
        assert is_retryable_status(403, DEFAULT_RETRY_CONFIG) is False

    def test_returns_false_for_404(self):
        """Should return False for 404 Not Found."""
        assert is_retryable_status(404, DEFAULT_RETRY_CONFIG) is False

    def test_uses_custom_retry_on_status_list(self):
        """Should use custom retry_on_status list."""
        config = RetryConfig(retry_on_status=[418, 503])
        assert is_retryable_status(418, config) is True
        assert is_retryable_status(503, config) is True
        assert is_retryable_status(429, config) is False


class TestIsRetryableMethod:
    """Tests for is_retryable_method function."""

    def test_returns_true_for_get(self):
        """Should return True for GET."""
        assert is_retryable_method("GET", DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_head(self):
        """Should return True for HEAD."""
        assert is_retryable_method("HEAD", DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_options(self):
        """Should return True for OPTIONS."""
        assert is_retryable_method("OPTIONS", DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_put(self):
        """Should return True for PUT."""
        assert is_retryable_method("PUT", DEFAULT_RETRY_CONFIG) is True

    def test_returns_true_for_delete(self):
        """Should return True for DELETE."""
        assert is_retryable_method("DELETE", DEFAULT_RETRY_CONFIG) is True

    def test_returns_false_for_post(self):
        """Should return False for POST."""
        assert is_retryable_method("POST", DEFAULT_RETRY_CONFIG) is False

    def test_returns_false_for_patch(self):
        """Should return False for PATCH."""
        assert is_retryable_method("PATCH", DEFAULT_RETRY_CONFIG) is False

    def test_is_case_insensitive(self):
        """Should be case-insensitive."""
        assert is_retryable_method("get", DEFAULT_RETRY_CONFIG) is True
        assert is_retryable_method("Get", DEFAULT_RETRY_CONFIG) is True
        assert is_retryable_method("GET", DEFAULT_RETRY_CONFIG) is True

    def test_uses_custom_retry_methods_list(self):
        """Should use custom retry_methods list."""
        config = RetryConfig(retry_methods=["POST"])
        assert is_retryable_method("POST", config) is True
        assert is_retryable_method("GET", config) is False


class TestParseRetryAfter:
    """Tests for parse_retry_after function."""

    def test_returns_zero_for_none(self):
        """Should return 0 for None."""
        assert parse_retry_after(None) == 0

    def test_returns_zero_for_empty_string(self):
        """Should return 0 for empty string."""
        assert parse_retry_after("") == 0

    def test_parses_integer_seconds(self):
        """Should parse integer seconds."""
        assert parse_retry_after("10") == 10.0

    def test_parses_zero_seconds(self):
        """Should parse zero seconds."""
        assert parse_retry_after("0") == 0

    def test_parses_float_seconds(self):
        """Should parse float seconds."""
        assert parse_retry_after("3.5") == 3.5

    def test_parses_large_values(self):
        """Should parse large values."""
        assert parse_retry_after("3600") == 3600.0

    def test_parses_http_date_format(self):
        """Should parse HTTP-date format."""
        future_date = datetime.now(timezone.utc).replace(microsecond=0)
        # Add 10 seconds
        from datetime import timedelta
        future_date = future_date + timedelta(seconds=10)
        http_date = format_datetime(future_date, usegmt=True)
        delay = parse_retry_after(http_date)
        assert delay > 0
        assert delay <= 10

    def test_returns_zero_for_past_dates(self):
        """Should return 0 for past dates."""
        past_date = datetime.now(timezone.utc).replace(microsecond=0)
        from datetime import timedelta
        past_date = past_date - timedelta(seconds=10)
        http_date = format_datetime(past_date, usegmt=True)
        assert parse_retry_after(http_date) == 0

    def test_returns_zero_for_invalid_string(self):
        """Should return 0 for invalid string."""
        assert parse_retry_after("invalid") == 0


class TestMergeConfig:
    """Tests for merge_config function."""

    def test_returns_defaults_when_no_config_provided(self):
        """Should return defaults when no config provided."""
        merged = merge_config(None)
        assert merged == DEFAULT_RETRY_CONFIG

    def test_returns_provided_config(self):
        """Should return provided config."""
        custom_config = RetryConfig(max_retries=5)
        merged = merge_config(custom_config)
        assert merged.max_retries == 5


class TestAsyncSleep:
    """Tests for async_sleep function."""

    @pytest.mark.asyncio
    async def test_sleeps_for_specified_duration(self):
        """Should sleep for approximately the specified duration."""
        start = time.monotonic()
        await async_sleep(0.1)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.1


class TestSyncSleep:
    """Tests for sync_sleep function."""

    def test_sleeps_for_specified_duration(self):
        """Should sleep for approximately the specified duration."""
        start = time.monotonic()
        sync_sleep(0.1)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.1
